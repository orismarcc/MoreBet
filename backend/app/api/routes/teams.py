from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import Team
from app.models.schemas import TeamOut, PlayerOut

router = APIRouter(prefix="/teams", tags=["teams"])


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
