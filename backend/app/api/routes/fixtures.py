import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.football_data import (
    SUPPORTED_LEAGUES,
    fetch_upcoming_fixtures,
)

logger = logging.getLogger(__name__)

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

    if league_ids:
        requested = [int(x) for x in league_ids.split(",") if x.strip().isdigit()]
        ids_to_fetch = [i for i in requested if i in SUPPORTED_LEAGUES]
    else:
        ids_to_fetch = list(SUPPORTED_LEAGUES.keys())

    # Fan-out the league fetches concurrently — capped at 4 in flight so we
    # don't hammer the rate limit. Each individual call already retries on 429
    # via the HTTP layer.
    sem = asyncio.Semaphore(4)

    async def _fetch(client: httpx.AsyncClient, league_id: int) -> list[dict]:
        async with sem:
            try:
                return await fetch_upcoming_fixtures(client, league_id, days)
            except Exception as exc:
                logger.warning("upcoming_fixtures(%s) failed: %s", league_id, exc)
                return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        per_league = await asyncio.gather(*(_fetch(client, lid) for lid in ids_to_fetch))

    all_fixtures: list[dict] = [f for batch in per_league for f in batch]

    # Single batched query to map api_id -> internal db id for every team that
    # appears in any fixture (replaces the previous N+1 pattern).
    team_api_ids = {f["home_team_api_id"] for f in all_fixtures} | {
        f["away_team_api_id"] for f in all_fixtures
    }
    db_id_by_api_id: dict[int, int] = {}
    if team_api_ids:
        rows = db.query(Team.api_id, Team.id).filter(Team.api_id.in_(team_api_ids)).all()
        db_id_by_api_id = {api_id: db_id for api_id, db_id in rows}

    result = [
        UpcomingFixture(
            **f,
            home_db_id=db_id_by_api_id.get(f["home_team_api_id"]),
            away_db_id=db_id_by_api_id.get(f["away_team_api_id"]),
        )
        for f in all_fixtures
    ]

    return sorted(result, key=lambda x: x.match_date)
