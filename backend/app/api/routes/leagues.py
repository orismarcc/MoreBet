import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.backtest import run_backtest
from app.db.database import get_db
from app.models.orm import League
from app.models.schemas import LeagueOut
from app.models.orm import Team
from app.services.football_data import FD_LEAGUES, fetch_league_finished_matches, fetch_standings
from app.services.ingestion import ingest_league, ingest_all_leagues

router = APIRouter(prefix="/leagues", tags=["leagues"])


class RefreshAllOut(BaseModel):
    results: list[str]


class StandingRow(BaseModel):
    position: int | None
    team_api_id: int | None
    team_name: str | None
    team_crest: str | None
    played: int | None
    won: int | None
    draw: int | None
    lost: int | None
    goals_for: int | None
    goals_against: int | None
    goal_difference: int | None
    points: int | None
    db_id: int | None = None   # internal team id when ingested (for analysis)


class StandingGroup(BaseModel):
    group: str | None
    rows: list[StandingRow]


class CalibrationBucketOut(BaseModel):
    range_low: float
    range_high: float
    predicted_avg: float
    observed_freq: float
    count: int


class BacktestOut(BaseModel):
    league_api_id: int
    league_name: str
    n_matches_total: int
    n_predicted: int
    n_skipped: int
    period_from: str | None
    period_to: str | None
    brier_1x2_model: float | None
    brier_1x2_baseline: float | None
    skill_score_1x2: float | None
    log_loss_model: float | None
    log_loss_baseline: float | None
    accuracy_model: float | None
    accuracy_baseline: float | None
    brier_over25_model: float | None
    brier_over25_baseline: float | None
    over25_base_rate: float | None
    brier_btts_model: float | None
    brier_btts_baseline: float | None
    btts_base_rate: float | None
    calibration: list[CalibrationBucketOut]


@router.get("/", response_model=list[LeagueOut])
def list_leagues(db: Session = Depends(get_db)):
    return db.query(League).order_by(League.name).all()


@router.get("/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, db: Session = Depends(get_db)):
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


@router.get("/{league_api_id}/standings", response_model=list[StandingGroup])
async def league_standings(league_api_id: int, db: Session = Depends(get_db)):
    """Current league table(s), enriched with our internal team db ids so the
    UI can deep-link a row into analysis."""
    if league_api_id not in FD_LEAGUES:
        raise HTTPException(status_code=404, detail="League not supported")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            groups = await fetch_standings(client, league_api_id)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")

    api_ids = {r["team_api_id"] for g in groups for r in g["rows"] if r["team_api_id"]}
    db_ids = {}
    if api_ids:
        rows = db.query(Team.api_id, Team.id).filter(Team.api_id.in_(api_ids)).all()
        db_ids = {aid: tid for aid, tid in rows}
    for g in groups:
        for r in g["rows"]:
            r["db_id"] = db_ids.get(r["team_api_id"])
    return groups


@router.post("/{league_api_id}/refresh", response_model=LeagueOut)
async def refresh_league(league_api_id: int, db: Session = Depends(get_db)):
    """Trigger manual data refresh for a specific league."""
    try:
        league = await ingest_league(db, league_api_id)
        return league
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"API error: {e}")


@router.post("/{league_api_id}/backtest", response_model=BacktestOut)
async def backtest_league(league_api_id: int):
    """Walk-forward backtest: replays every finished match of the league
    (previous + current season) predicting each one with only the data
    available before kickoff, then scores the predictions (Brier, log-loss,
    calibration) against the real results and a no-skill baseline."""
    if league_api_id not in FD_LEAGUES:
        raise HTTPException(status_code=404, detail="League not supported")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            info, matches = await fetch_league_finished_matches(client, league_api_id)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")

    result = run_backtest(matches)
    return BacktestOut(
        league_api_id=league_api_id,
        league_name=info["name"],
        **result.__dict__,
    )


@router.post("/refresh-all", response_model=RefreshAllOut)
async def refresh_all_leagues(db: Session = Depends(get_db)):
    """Sequentially refresh every supported league. Slow (~30s) but rate-limit
    safe. Returns a per-league OK/ERROR breakdown."""
    results = await ingest_all_leagues(db)
    return RefreshAllOut(results=results)
