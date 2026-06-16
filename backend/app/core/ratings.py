"""
Opponent-adjusted attack/defence ratings (strength of schedule).

Raw goal averages lie when teams play unequal opposition: a minnow that only
faces other minnows looks defensively elite, and a giant that only plays other
giants looks offensively average. Normalising against a single field average —
as the base Poisson model does for domestic leagues — cannot see this, which is
why pre-tournament World Cup seeding produced absurd lines (Spain vs Cape Verde
priced near 50/50).

This solves attack[t] and defence[t] jointly so each team's rating reflects the
quality of the opponents it actually faced. It's an iterative fixed-point of the
same bivariate-Poisson factorisation Dixon-Coles fit by MLE — simpler to run,
robust, and self-regularising via a prior of K games against an average side.

Output convention: rating 1.0 == league-average. A team's expected goals
against an average opponent is ``attack * mu`` (scored) / ``defence * mu``
(conceded), where ``mu`` is the mean goals per team per game over all games fed
in. Feed those into the existing engine with the tournament league average set
to ``mu`` and the result is opponent-adjusted lambdas.
"""
from dataclasses import dataclass


@dataclass
class TeamRating:
    attack: float    # 1.0 = average attack; >1 scores more than average
    defense: float   # 1.0 = average defence; >1 concedes more than average (worse)
    games: int


def compute_ratings(
    games: list[tuple[object, object, int, int]],
    k: float = 0.5,
    iterations: int = 60,
) -> tuple[dict[object, TeamRating], float]:
    """
    games: list of (team_key, opponent_key, goals_for, goals_against), each
    real match appearing ONCE (dedup before calling). Keys must be stable and
    hashable — use provider ids, never display names.

    Returns ({key: TeamRating}, mu). Empty input → ({}, 0.0).
    """
    if not games:
        return {}, 0.0

    keys: set[object] = set()
    for a, b, _gf, _ga in games:
        keys.add(a)
        keys.add(b)

    total_goals = sum(gf + ga for _a, _b, gf, ga in games)
    mu = total_goals / (2 * len(games))
    if mu <= 0:
        return {key: TeamRating(1.0, 1.0, 0) for key in keys}, 0.0

    scored: dict[object, float] = {key: 0.0 for key in keys}
    conceded: dict[object, float] = {key: 0.0 for key in keys}
    opponents: dict[object, list[object]] = {key: [] for key in keys}
    for a, b, gf, ga in games:
        scored[a] += gf
        conceded[a] += ga
        opponents[a].append(b)
        scored[b] += ga
        conceded[b] += gf
        opponents[b].append(a)

    atk: dict[object, float] = {key: 1.0 for key in keys}
    dfn: dict[object, float] = {key: 1.0 for key in keys}
    prior = k * mu

    for _ in range(iterations):
        new_atk: dict[object, float] = {}
        new_dfn: dict[object, float] = {}
        for key in keys:
            # Expected goals if this team were exactly average, given the
            # defences/attacks it actually faced.
            exp_scored = sum(dfn[o] * mu for o in opponents[key])
            exp_conceded = sum(atk[o] * mu for o in opponents[key])
            # Prior of k games vs an average side keeps thin samples sane.
            new_atk[key] = (scored[key] + prior) / (exp_scored + prior)
            new_dfn[key] = (conceded[key] + prior) / (exp_conceded + prior)
        # Re-anchor so the average rating stays 1.0 (identifiability).
        mean_atk = sum(new_atk.values()) / len(new_atk)
        mean_dfn = sum(new_dfn.values()) / len(new_dfn)
        atk = {key: v / mean_atk for key, v in new_atk.items()}
        dfn = {key: v / mean_dfn for key, v in new_dfn.items()}

    return (
        {key: TeamRating(atk[key], dfn[key], len(opponents[key])) for key in keys},
        mu,
    )


def team_split_inputs(rating: TeamRating, mu_home: float, mu_away: float) -> dict:
    """Map an opponent-adjusted rating to the home/away split goal inputs the
    engine expects, carrying home advantage via the league's home/away means.

    With these on the team row and league averages set to (mu_home, mu_away),
    the engine reproduces the rating lambdas exactly:
        λ_home = atk_home · def_away · mu_home
        λ_away = atk_away · def_home · mu_away
    (verified against the engine's split normalisation). Venue advantage lives
    in mu_home vs mu_away; opponent strength lives in the rating.
    """
    return {
        "home_goals_scored": rating.attack * mu_home,
        "home_goals_conceded": rating.defense * mu_away,
        "away_goals_scored": rating.attack * mu_away,
        "away_goals_conceded": rating.defense * mu_home,
    }


def seed_from_matches(
    matches: list[tuple[object, object, int, int]],
    k: float = 8.0,
) -> tuple[dict[object, TeamRating], float, float]:
    """Opponent-adjusted ratings for a round-robin league plus its home/away
    goal means. `matches` = (home_key, away_key, home_goals, away_goals), each
    real match once. Returns (ratings, mu_home, mu_away). Empty → ({}, 0, 0).

    k defaults to 8 (vs 0.5 for tournaments): a domestic field is far more
    homogeneous and the recent-form signal is noisier, so a heavier prior toward
    the league mean calibrates best (matches the validated backtest sweep).
    """
    if not matches:
        return {}, 0.0, 0.0
    ratings, _mu = compute_ratings(
        [(h, a, hg, ag) for h, a, hg, ag in matches], k=k
    )
    n = len(matches)
    mu_home = sum(hg for _h, _a, hg, _ag in matches) / n
    mu_away = sum(ag for _h, _a, _hg, ag in matches) / n
    return ratings, mu_home, mu_away
