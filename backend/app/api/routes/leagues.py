from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import League
from app.models.schemas import LeagueOut
from app.services.ingestion import ingest_league

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/", response_model=list[LeagueOut])
def list_leagues(db: Session = Depends(get_db)):
    return db.query(League).order_by(League.name).all()


@router.get("/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, db: Session = Depends(get_db)):
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


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
