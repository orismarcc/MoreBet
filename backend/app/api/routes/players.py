from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import Player
from app.models.schemas import PlayerOut, PlayerUpdateIn

router = APIRouter(prefix="/players", tags=["players"])


@router.put("/{player_id}/metrics", response_model=PlayerOut)
def update_player_metrics(
    player_id: int,
    payload: PlayerUpdateIn,
    db: Session = Depends(get_db),
):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    update_data = payload.model_dump(exclude_none=True)
    for k, v in update_data.items():
        setattr(player, k, v)

    db.commit()
    db.refresh(player)
    return player
