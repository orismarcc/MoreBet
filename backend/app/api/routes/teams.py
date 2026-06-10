import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import Team
from app.models.schemas import TeamOut, PlayerOut
from app.services.football_data import fetch_team_recent_matches

router = APIRouter(prefix="/teams", tags=["teams"])


class RecentMatch(BaseModel):
    match_id: int
    date: str
    competition: str | None
    competition_code: str | None
    competition_emblem: str | None
    is_home: bool
    opponent: str
    opponent_short: str | None
    opponent_crest: str | None
    goals_for: int
    goals_against: int
    result: str


class RecentSummary(BaseModel):
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    avg_goals_for: float
    avg_goals_against: float
    over_25_pct: int
    btts_pct: int
    clean_sheets: int
    failed_to_score: int
    ppg: float
    form: str


class RecentForm(BaseModel):
    summary: RecentSummary
    matches: list[RecentMatch]


@router.get("/league/{league_id}", response_model=list[TeamOut])
def list_teams_by_league(league_id: int, db: Session = Depends(get_db)):
    teams = db.query(Team).filter(Team.league_id == league_id).order_by(Team.name).all()
    if not teams:
        raise HTTPException(status_code=404, detail="No teams found for this league")
    return teams


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/players", response_model=list[PlayerOut])
def get_team_players(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return sorted(team.players, key=lambda p: p.goal_contribution_pct, reverse=True)


@router.get("/{team_id}/recent", response_model=RecentForm)
async def get_team_recent(
    team_id: int,
    limit: int = Query(default=6, ge=1, le=15),
    db: Session = Depends(get_db),
):
    """Recent finished matches + aggregated form summary for a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await fetch_team_recent_matches(client, team.api_id, limit)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
