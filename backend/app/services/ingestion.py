"""
Data ingestion service — called by the scheduler and by manual refresh endpoints.
"""
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.orm import League, Team, Match, Player
from app.services.api_football import (
    SUPPORTED_LEAGUES,
    fetch_league_with_form,
    fetch_players,
)


async def ingest_league(db: Session, league_id: int) -> League:
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Single resolver: picks the newest accessible season and computes
        # each team's averages from their last N matches (recent form).
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

        team_map: dict[int, Team] = {}

        for td in teams_data:
            team = (
                db.query(Team)
                .filter(Team.api_id == td["api_id"], Team.league_id == league.id)
                .first()
            )
            if not team:
                team = Team(league_id=league.id, **td)
                db.add(team)
            else:
                for k, v in td.items():
                    setattr(team, k, v)
            team.last_updated = datetime.now(timezone.utc)
            db.flush()
            team_map[td["api_id"]] = team

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
