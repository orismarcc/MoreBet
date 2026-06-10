from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.football_data import (
    SUPPORTED_LEAGUES,
    fetch_upcoming_fixtures,
)

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


class UpcomingFixture(BaseModel):
    fixture_id: int
    match_date: str
    status: str
    venue: str | None
    league_id: int
    league_name: str
    league_country: str
    league_logo: str | None
    round: str | None
    home_team_api_id: int
    home_team_name: str
    home_team_logo: str | None
    away_team_api_id: int
    away_team_name: str
    away_team_logo: str | None
    # Internal DB ids for analysis (None if team not in DB)
    home_db_id: int | None = None
    away_db_id: int | None = None


@router.get("/upcoming", response_model=list[UpcomingFixture])
async def upcoming_fixtures(
    days: int = Query(default=7, ge=1, le=14),
    league_ids: str = Query(default="", description="Comma-separated league api_ids, empty = all"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.orm import Team

    ids_to_fetch = []
    if league_ids:
        requested = [int(x) for x in league_ids.split(",") if x.strip().isdigit()]
        ids_to_fetch = [i for i in requested if i in SUPPORTED_LEAGUES]
    else:
        ids_to_fetch = list(SUPPORTED_LEAGUES.keys())

    all_fixtures: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for league_id in ids_to_fetch:
            try:
                fixtures = await fetch_upcoming_fixtures(client, league_id, days)
                all_fixtures.extend(fixtures)
            except Exception:
                continue  # skip leagues that fail (API quota etc.)

    # Enrich with DB team ids so frontend can trigger analysis directly
    result = []
    for f in all_fixtures:
        home_team = db.query(Team).filter(Team.api_id == f["home_team_api_id"]).first()
        away_team = db.query(Team).filter(Team.api_id == f["away_team_api_id"]).first()
        result.append(UpcomingFixture(
            **f,
            home_db_id=home_team.id if home_team else None,
            away_db_id=away_team.id if away_team else None,
        ))

    return sorted(result, key=lambda x: x.match_date)
