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
# many games. k=8 won a walk-forward backtest sweep (k ∈ 4..12) over PL, La
# Liga, Ligue 1 and Brasileirão (~2.8k matches): best 1X2 Brier/log-loss and
# near-perfect top-bucket calibration (predicted 74.6% vs observed 74.2%).
# k=6 was overconfident at the top (75.3%→72.9%); k=10 flips to underconfident.
SHRINKAGE_GAMES = 8.0


def shrink_avg(
    team_avg: float,
    games_played: int | None,
    league_avg: float,
    k: float | None = None,
) -> float:
    """
    Shrink a team's per-game average toward the league average (regression to
    the mean). Counters the multiplicative model's overconfidence at the
    extremes: small samples and outlier rates get pulled toward league-typical
    values, larger samples keep most of their own signal.

    Returns team_avg untouched when games_played is unknown (None) so callers
    without sample sizes keep the historical behaviour.
    """
    if k is None:
        # Resolved at call time so calibration sweeps can tune the module
        # constant without stale function defaults.
        k = SHRINKAGE_GAMES
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
