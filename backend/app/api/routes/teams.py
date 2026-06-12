import logging
import unicodedata

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import League, Team
from app.models.schemas import TeamOut, PlayerOut
from app.services.football_data import (
    fetch_team_recent_matches,
    fetch_team_upcoming_matches,
    fetch_wc_participants,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["teams"])


def _fold(s: str) -> str:
    """Lowercase + strip accents so 'atletico' matches 'Atlético'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


class TeamSearchResult(BaseModel):
    kind: str                  # "club" (in DB, analysable) | "national"
    db_id: int | None = None   # present for clubs
    api_id: int
    name: str
    short_name: str | None = None
    crest: str | None = None
    context: str               # e.g. "Premier League · England" / "Copa do Mundo FIFA"


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
    over_15_pct: int
    over_25_pct: int
    btts_pct: int
    clean_sheets: int
    failed_to_score: int
    ppg: float
    form: str


class UpcomingTeamMatch(BaseModel):
    match_id: int
    date: str
    competition: str | None
    competition_emblem: str | None
    is_home: bool
    opponent: str
    opponent_crest: str | None


class RecentForm(BaseModel):
    summary: RecentSummary
    matches: list[RecentMatch]
    upcoming: list[UpcomingTeamMatch] = []


@router.get("/search", response_model=list[TeamSearchResult])
async def search_teams(
    q: str = Query(min_length=2, max_length=60),
    db: Session = Depends(get_db),
):
    """Accent-insensitive search across club teams (DB) and World Cup national
    teams (live schedule, cached). Clubs come first — they're analysable."""
    needle = _fold(q)

    # Clubs: the whole table is ~170 rows, so filtering in Python lets the
    # match be accent-insensitive without DB extensions.
    rows = (
        db.query(Team, League)
        .join(League, Team.league_id == League.id)
        .order_by(Team.name)
        .all()
    )
    results: list[TeamSearchResult] = []
    club_api_ids: set[int] = set()
    for team, league in rows:
        if needle in _fold(team.name):
            club_api_ids.add(team.api_id)
            results.append(TeamSearchResult(
                kind="club",
                db_id=team.id,
                api_id=team.api_id,
                name=team.name,
                short_name=team.short_name,
                crest=team.logo_url,
                context=f"{league.name} · {league.country}",
            ))

    # National teams from the current World Cup edition (best-effort).
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            nationals = await fetch_wc_participants(client)
        for t in nationals:
            if t["api_id"] in club_api_ids:
                continue
            if needle in _fold(t["name"]) or needle in _fold(t.get("short_name") or ""):
                results.append(TeamSearchResult(
                    kind="national",
                    api_id=t["api_id"],
                    name=t["name"],
                    short_name=t["short_name"],
                    crest=t["crest"],
                    context="Copa do Mundo FIFA 2026",
                ))
    except Exception as exc:
        logger.warning("WC participants lookup failed during search: %s", exc)

    return results[:24]


async def _recent_payload(api_id: int, limit: int, include_upcoming: bool) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = await fetch_team_recent_matches(client, api_id, limit)
        if include_upcoming:
            try:
                payload["upcoming"] = await fetch_team_upcoming_matches(client, api_id)
            except httpx.HTTPError:
                payload["upcoming"] = []
        return payload


@router.get("/api/{api_id}/recent", response_model=RecentForm)
async def get_recent_by_api_id(
    api_id: int,
    limit: int = Query(default=6, ge=1, le=15),
    upcoming: bool = Query(default=False),
):
    """Recent form straight from the data provider, keyed by the provider's
    team id — used for national teams that have no row in our DB."""
    try:
        return await _recent_payload(api_id, limit, upcoming)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")


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
    upcoming: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Recent finished matches + aggregated form summary for a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    try:
        return await _recent_payload(team.api_id, limit, upcoming)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
