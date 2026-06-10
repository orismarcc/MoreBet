"""
Data ingestion service — called by the scheduler and by manual refresh endpoints.
"""
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.orm import League, Team, Match, Player
from app.services.football_data import (
    SUPPORTED_LEAGUES,
    fetch_league_with_form,
)
# Player-level stats (absence modifiers) still come from the legacy provider;
# this is a secondary feature and off the league-refresh critical path.
from app.services.api_football import fetch_players


async def ingest_league(db: Session, league_id: int) -> League:
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Current-season data with each team's averages computed from their
        # last N matches (recent form), via football-data.org.
        league_data, teams_data = await fetch_league_with_form(client, league_id)
        if not league_data or not teams_data:
            raise ValueError(f"League {league_id} not found in API")

        league = db.query(League).filter(League.api_id == league_id).first()
        if not league:
            league = League(**league_data)
            db.add(league)
        else:
            for k, v in league_data.items():
                setattr(league, k, v)
        db.flush()

        # The provider switch changed team api_ids, so old rows can't be matched
        # by id. Wipe this league's teams (and their dependents) and re-import a
        # clean set to avoid stale duplicates.
        old_ids = [t.id for t in db.query(Team).filter(Team.league_id == league.id).all()]
        if old_ids:
            db.query(Player).filter(Player.team_id.in_(old_ids)).delete(synchronize_session=False)
            db.query(Match).filter(
                (Match.home_team_id.in_(old_ids)) | (Match.away_team_id.in_(old_ids))
            ).delete(synchronize_session=False)
            db.query(Team).filter(Team.league_id == league.id).delete(synchronize_session=False)
            db.flush()

        for td in teams_data:
            team = Team(league_id=league.id, last_updated=datetime.now(timezone.utc), **td)
            db.add(team)
        db.flush()

        _update_league_averages(league, teams_data)
        league.last_updated = datetime.now(timezone.utc)

        db.commit()
        db.refresh(league)
        return league


def _update_league_averages(league: League, teams_data: list[dict]) -> None:
    """Recalculate MGM/MGV from team home/away averages."""
    home_goals = [t["home_goals_scored"] for t in teams_data if t["home_played"] > 0]
    away_goals = [t["away_goals_scored"] for t in teams_data if t["away_played"] > 0]

    if home_goals:
        league.home_goals_avg = sum(home_goals) / len(home_goals)
    if away_goals:
        league.away_goals_avg = sum(away_goals) / len(away_goals)

    league.total_matches = sum(t["home_played"] for t in teams_data)


async def ingest_all_leagues(db: Session) -> list[str]:
    results = []
    for league_id, (name, _) in SUPPORTED_LEAGUES.items():
        try:
            await ingest_league(db, league_id)
            results.append(f"OK: {name}")
        except Exception as e:
            results.append(f"ERROR: {name} — {e}")
    return results


async def ingest_players_for_team(db: Session, team: Team) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        players_data = await fetch_players(client, team.api_id)
        total_goals = sum(p["goals"] for p in players_data) or 1

        for pd in players_data:
            player = (
                db.query(Player)
                .filter(Player.api_id == pd["api_id"], Player.team_id == team.id)
                .first()
            )
            contribution = pd["goals"] / total_goals
            if not player:
                player = Player(
                    team_id=team.id,
                    goal_contribution_pct=contribution,
                    **pd,
                )
                db.add(player)
            else:
                for k, v in pd.items():
                    setattr(player, k, v)
                player.goal_contribution_pct = contribution
            player.last_updated = datetime.now(timezone.utc)

        db.commit()
