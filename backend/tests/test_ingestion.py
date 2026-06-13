"""
Regression guard for the "Dados indisponíveis after refresh" bug: a refresh
must NOT change team db ids (the frontend holds them), and must drop only teams
that genuinely left the league.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.orm import Base, Team
from app.services import ingestion

_LEAGUE = {"api_id": 78, "name": "Bundesliga", "country": "Germany", "season": 2025, "logo_url": None}


def _team(api_id, name):
    return {
        "api_id": api_id, "name": name, "short_name": name[:3], "logo_url": None,
        "home_played": 10, "home_goals_scored": 2.0, "home_goals_conceded": 1.0,
        "away_played": 10, "away_goals_scored": 1.5, "away_goals_conceded": 1.2,
    }


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_refresh_keeps_team_ids_stable_and_drops_departed(monkeypatch):
    db = _session()

    async def fetch_v1(client, lid):
        return dict(_LEAGUE), [_team(5, "Bayern"), _team(4, "Dortmund"), _team(99, "Relegated")]

    monkeypatch.setattr(ingestion, "fetch_league_with_form", fetch_v1)
    await ingestion.ingest_league(db, 78)
    before = {t.api_id: t.id for t in db.query(Team).all()}
    assert set(before) == {5, 4, 99}

    # Second refresh: same teams (updated stats) minus the relegated one.
    async def fetch_v2(client, lid):
        return dict(_LEAGUE), [_team(5, "Bayern"), _team(4, "Dortmund")]

    monkeypatch.setattr(ingestion, "fetch_league_with_form", fetch_v2)
    await ingestion.ingest_league(db, 78)
    after = {t.api_id: t.id for t in db.query(Team).all()}

    assert after[5] == before[5], "surviving team id must not change across refresh"
    assert after[4] == before[4]
    assert 99 not in after, "team that left the league must be removed"
    db.close()
