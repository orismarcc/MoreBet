from dataclasses import dataclass


@dataclass
class LeagueAverages:
    home_goals_avg: float  # MGM — média gols mandante
    away_goals_avg: float  # MGV — média gols visitante
    home_xg_avg: float | None = None
    away_xg_avg: float | None = None


@dataclass
class TeamStrength:
    attack: float   # força de ataque normalizada
    defense: float  # força de defesa normalizada


# Bayesian prior weight: a team's average only fully "speaks for itself" after
# many games. With k=6, a team with 6 games sits halfway between its own rate
# and the league average; with 18 games its own rate dominates (75%). Chosen so
# the most defensive realistic matchup prices 0-0 under ~25%, in line with how
# bookmakers cap that scoreline.
SHRINKAGE_GAMES = 6.0


def shrink_avg(
    team_avg: float,
    games_played: int | None,
    league_avg: float,
    k: float = SHRINKAGE_GAMES,
) -> float:
    """
    Shrink a team's per-game average toward the league average (regression to
    the mean). Counters the multiplicative model's overconfidence at the
    extremes: small samples and outlier rates get pulled toward league-typical
    values, larger samples keep most of their own signal.

    Returns team_avg untouched when games_played is unknown (None) so callers
    without sample sizes keep the historical behaviour.
    """
    if games_played is None or league_avg <= 0:
        return team_avg
    return (team_avg * games_played + league_avg * k) / (games_played + k)


def calc_team_strength(
    goals_scored_avg: float,
    goals_conceded_avg: float,
    league_scored_avg: float,
    league_conceded_avg: float,
) -> TeamStrength:
    """
    Normalise a team's scoring and conceding rates against league averages.

    attack  = team_scored_avg  / league_scored_avg
    defense = team_conceded_avg / league_conceded_avg
    """
    attack = goals_scored_avg / league_scored_avg if league_scored_avg > 0 else 1.0
    defense = goals_conceded_avg / league_conceded_avg if league_conceded_avg > 0 else 1.0
    return TeamStrength(attack=attack, defense=defense)


def calc_lambda(
    home_attack: float,
    away_defense: float,
    league_home_avg: float,
    player_modifier: float = 1.0,
) -> float:
    """
    Expected goals for home team:
      λ_home = home_attack × away_defense × MGM × player_modifier
    """
    return home_attack * away_defense * league_home_avg * player_modifier


def calc_xg_lambda(
    home_xg_attack: float,
    away_xg_defense: float,
    league_home_xg_avg: float,
    player_modifier: float = 1.0,
) -> float:
    """Same as calc_lambda but using xG-based strengths."""
    return home_xg_attack * away_xg_defense * league_home_xg_avg * player_modifier


def blend_lambda(
    raw_lambda: float,
    xg_lambda: float | None,
    xg_weight: float = 0.4,
) -> float:
    """
    Blend raw-goals lambda with xG lambda.
    xG gets 40% weight when available — reduces noise from lucky/unlucky finishes.
    """
    if xg_lambda is None:
        return raw_lambda
    return (1 - xg_weight) * raw_lambda + xg_weight * xg_lambda
