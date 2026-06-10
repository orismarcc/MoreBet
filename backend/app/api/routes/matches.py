import functools

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import Team, League
from app.models.schemas import (
    CalculateMatchIn,
    MatchAnalysisOut,
    MarketsOut,
    FairOddsOut,
    ScoreProb,
    TeamOut,
    ValueCheckIn,
    ValueCheckOut,
)
from app.core.engine import TeamInput, analyse_match
from app.core.strength import LeagueAverages
from app.core.odds import calc_value

router = APIRouter(prefix="/matches", tags=["matches"])


def _player_modifier(absent_players: list, team_total_contribution: float = 1.0) -> float:
    """
    Reduce team attack lambda based on absent players' goal contribution.
    If key player contributed 30% of goals, modifier = 1 - 0.30 = 0.70.
    Minimum modifier capped at 0.50 to avoid extreme values.
    """
    total_impact = sum(p.goal_contribution_pct for p in absent_players)
    return max(1.0 - total_impact, 0.50)


@router.post("/calculate", response_model=MatchAnalysisOut)
def calculate_match(payload: CalculateMatchIn, db: Session = Depends(get_db)):
    home_team = db.query(Team).filter(Team.id == payload.home_team_id).first()
    away_team = db.query(Team).filter(Team.id == payload.away_team_id).first()

    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="One or both teams not found")
    if home_team.league_id != away_team.league_id:
        raise HTTPException(status_code=400, detail="Teams must belong to the same league")

    league = db.query(League).filter(League.id == home_team.league_id).first()
    if not league or not league.home_goals_avg:
        raise HTTPException(
            status_code=422,
            detail="League averages not available — run a data refresh first",
        )

    home_modifier = _player_modifier(payload.absent_home)
    away_modifier = _player_modifier(payload.absent_away)

    team_input = TeamInput(
        home_goals_scored_avg=home_team.home_goals_scored,
        home_goals_conceded_avg=home_team.home_goals_conceded,
        away_goals_scored_avg=away_team.away_goals_scored,
        away_goals_conceded_avg=away_team.away_goals_conceded,
        home_xg_scored_avg=home_team.home_xg_scored,
        home_xg_conceded_avg=home_team.home_xg_conceded,
        away_xg_scored_avg=away_team.away_xg_scored,
        away_xg_conceded_avg=away_team.away_xg_conceded,
        home_player_modifier=home_modifier,
        away_player_modifier=away_modifier,
    )

    league_avgs = LeagueAverages(
        home_goals_avg=league.home_goals_avg,
        away_goals_avg=league.away_goals_avg,
        home_xg_avg=league.home_xg_avg,
        away_xg_avg=league.away_xg_avg,
    )

    result = analyse_match(team_input, league_avgs, xg_weight=payload.xg_weight)

    top_scores = [
        ScoreProb(home=h, away=a, prob=round(p, 6))
        for h, a, p in result.top_scores
    ]

    return MatchAnalysisOut(
        lambda_home=round(result.lambda_home, 4),
        lambda_away=round(result.lambda_away, 4),
        home_modifier=home_modifier,
        away_modifier=away_modifier,
        markets=MarketsOut(**result.markets.__dict__),
        fair_odds=FairOddsOut(**result.fair_odds.__dict__),
        top_scores=top_scores,
        home_team=TeamOut.model_validate(home_team),
        away_team=TeamOut.model_validate(away_team),
    )


@router.post("/value", response_model=ValueCheckOut)
def check_value(payload: ValueCheckIn):
    result = calc_value(payload.market, payload.fair_odds, payload.bookie_odds)
    if result.ev_pct > 5:
        verdict = f"VALOR ENCONTRADO! EV de +{result.ev_pct:.1f}%"
    elif result.ev_pct > 0:
        verdict = f"Valor marginal (+{result.ev_pct:.1f}%). Aposte com cautela."
    elif result.ev_pct == 0:
        verdict = "Odd justa. Sem vantagem matemática."
    else:
        verdict = f"Sem valor. Casa com margem de {abs(result.ev_pct):.1f}%."

    return ValueCheckOut(
        market=result.market,
        fair_odds=result.fair_odds,
        bookie_odds=result.bookie_odds,
        ev_pct=result.ev_pct,
        has_value=result.has_value,
        verdict=verdict,
    )
