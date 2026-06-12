import functools

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
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
from app.services.football_data import FD_LEAGUES, fetch_head_to_head
from app.services.espn import fetch_match_details

router = APIRouter(prefix="/matches", tags=["matches"])


class H2HMatch(BaseModel):
    match_id: int
    date: str
    competition: str | None
    competition_code: str | None
    home_api_id: int
    home_name: str
    home_crest: str | None
    away_api_id: int
    away_name: str
    away_crest: str | None
    home_goals: int
    away_goals: int


class GoalEvent(BaseModel):
    minute: str
    side: str            # "home" | "away"
    player: str | None
    text: str


class StatLabel(BaseModel):
    key: str
    label: str
    suffix: str


class MatchDetails(BaseModel):
    found: bool
    reason: str | None = None
    source: str | None = None
    stat_labels: list[StatLabel] = []
    home_stats: dict[str, str | None] = {}
    away_stats: dict[str, str | None] = {}
    goals: list[GoalEvent] = []


@router.get("/h2h", response_model=list[H2HMatch])
async def head_to_head(
    home_api_id: int = Query(...),
    away_api_id: int = Query(...),
    limit: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Last direct meetings between two teams (provider team api ids)."""
    hint: str | None = None
    team = db.query(Team).filter(Team.api_id == home_api_id).first()
    if team:
        league = db.query(League).filter(League.id == team.league_id).first()
        if league and league.api_id in FD_LEAGUES:
            hint = FD_LEAGUES[league.api_id][0]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await fetch_head_to_head(
                client, home_api_id, away_api_id, limit, league_hint=hint
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")


@router.get("/details", response_model=MatchDetails)
async def match_details(
    date: str = Query(..., description="ISO datetime of the match"),
    home: str = Query(..., min_length=2, max_length=80),
    away: str = Query(..., min_length=2, max_length=80),
    competition_code: str | None = Query(default=None, max_length=10),
):
    """Detailed statistics (possession, shots, corners, goal timeline) for a
    played match — best effort via the public stats source."""
    return await fetch_match_details(competition_code, date, home, away)


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
        raise HTTPException(
            status_code=400,
            detail="Análise disponível apenas entre times da mesma liga — o modelo "
                   "normaliza as forças pelas médias da liga em comum.",
        )

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
        kelly_pct=result.kelly_pct,
        quarter_kelly_pct=round(result.kelly_pct * 0.25, 4),
        verdict=verdict,
    )
