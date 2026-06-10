"""
Orchestration layer — assembles the full analysis pipeline.
"""
from dataclasses import dataclass

from app.core.strength import (
    LeagueAverages,
    TeamStrength,
    calc_lambda,
    calc_xg_lambda,
    blend_lambda,
)
from app.core.matrix import ScoreMatrix
from app.core.markets import MatchMarkets, calc_markets
from app.core.odds import FairOdds, calc_fair_odds, calc_value, ValueResult


@dataclass
class TeamInput:
    # Goals-based
    home_goals_scored_avg: float      # avg goals scored at home (or away)
    home_goals_conceded_avg: float
    away_goals_scored_avg: float
    away_goals_conceded_avg: float
    # xG-based (optional)
    home_xg_scored_avg: float | None = None
    home_xg_conceded_avg: float | None = None
    away_xg_scored_avg: float | None = None
    away_xg_conceded_avg: float | None = None
    # Player impact modifiers (1.0 = no change)
    home_player_modifier: float = 1.0
    away_player_modifier: float = 1.0


@dataclass
class MatchAnalysis:
    lambda_home: float
    lambda_away: float
    matrix: ScoreMatrix
    markets: MatchMarkets
    fair_odds: FairOdds
    top_scores: list[tuple[int, int, float]]


def analyse_match(
    home: TeamInput,
    league: LeagueAverages,
    xg_weight: float = 0.4,
) -> MatchAnalysis:
    # ── Home attack strength ────────────────────────────────────────────────
    from app.core.strength import calc_team_strength

    home_strength = calc_team_strength(
        goals_scored_avg=home.home_goals_scored_avg,
        goals_conceded_avg=home.home_goals_conceded_avg,
        league_scored_avg=league.home_goals_avg,
        league_conceded_avg=league.away_goals_avg,
    )
    away_strength = calc_team_strength(
        goals_scored_avg=home.away_goals_scored_avg,
        goals_conceded_avg=home.away_goals_conceded_avg,
        league_scored_avg=league.away_goals_avg,
        league_conceded_avg=league.home_goals_avg,
    )

    # ── Raw-goals lambda ────────────────────────────────────────────────────
    raw_lambda_home = calc_lambda(
        home_strength.attack,
        away_strength.defense,
        league.home_goals_avg,
        home.home_player_modifier,
    )
    raw_lambda_away = calc_lambda(
        away_strength.attack,
        home_strength.defense,
        league.away_goals_avg,
        home.away_player_modifier,
    )

    # ── xG lambda (if available) ────────────────────────────────────────────
    xg_lambda_home: float | None = None
    xg_lambda_away: float | None = None

    if (
        home.home_xg_scored_avg is not None
        and home.away_xg_conceded_avg is not None
        and league.home_xg_avg is not None
    ):
        home_xg_strength = calc_team_strength(
            goals_scored_avg=home.home_xg_scored_avg,
            goals_conceded_avg=home.home_xg_conceded_avg or 0,
            league_scored_avg=league.home_xg_avg,
            league_conceded_avg=league.away_xg_avg or league.home_xg_avg,
        )
        away_xg_strength = calc_team_strength(
            goals_scored_avg=home.away_xg_scored_avg or 0,
            goals_conceded_avg=home.away_xg_conceded_avg,
            league_scored_avg=league.away_xg_avg or league.home_xg_avg,
            league_conceded_avg=league.home_xg_avg,
        )
        xg_lambda_home = calc_xg_lambda(
            home_xg_strength.attack,
            away_xg_strength.defense,
            league.home_xg_avg,
            home.home_player_modifier,
        )
        xg_lambda_away = calc_xg_lambda(
            away_xg_strength.attack,
            home_xg_strength.defense,
            league.away_xg_avg or league.home_xg_avg,
            home.away_player_modifier,
        )

    lambda_home = blend_lambda(raw_lambda_home, xg_lambda_home, xg_weight)
    lambda_away = blend_lambda(raw_lambda_away, xg_lambda_away, xg_weight)

    matrix = ScoreMatrix(lambda_home=lambda_home, lambda_away=lambda_away)
    markets = calc_markets(matrix)
    fair_odds = calc_fair_odds(markets)

    return MatchAnalysis(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        matrix=matrix,
        markets=markets,
        fair_odds=fair_odds,
        top_scores=matrix.top_scores(10),
    )
