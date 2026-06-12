"""Tests for the tournament (neutral-venue) ingestion path used by the World Cup."""
import pytest

from app.services.football_data import (
    FORM_DECAY,
    _team_neutral_averages,
    fetch_league_with_form,
    TOURNAMENT_LEAGUES,
    FD_LEAGUES,
)


def test_world_cup_is_registered():
    assert 1 in FD_LEAGUES
    assert FD_LEAGUES[1][0] == "WC"
    assert 1 in TOURNAMENT_LEAGUES


def test_neutral_averages_mirror_both_splits():
    matches = [
        {"is_home": True, "scored": 2, "conceded": 0},
        {"is_home": False, "scored": 1, "conceded": 1},
        {"is_home": False, "scored": 3, "conceded": 2},
    ]
    avg = _team_neutral_averages(matches, last_n=30)
    assert avg["home_played"] == avg["away_played"] == 3
    # Averages are decay-weighted (newest match weighs 1.0, older ones less).
    w = [FORM_DECAY ** 2, FORM_DECAY, 1.0]
    exp_scored = (2 * w[0] + 1 * w[1] + 3 * w[2]) / sum(w)
    exp_conceded = (0 * w[0] + 1 * w[1] + 2 * w[2]) / sum(w)
    assert avg["home_goals_scored"] == avg["away_goals_scored"] == pytest.approx(exp_scored)
    assert avg["home_goals_conceded"] == avg["away_goals_conceded"] == pytest.approx(exp_conceded)


def _match(mid, home, away, status="FINISHED", gh=None, ga=None, date="2022-12-01T00:00:00Z"):
    return {
        "id": mid,
        "utcDate": date,
        "status": status,
        "matchday": 1,
        "homeTeam": {"id": home, "name": f"Team {home}", "tla": f"T{home}", "crest": None},
        "awayTeam": {"id": away, "name": f"Team {away}", "tla": f"T{away}", "crest": None},
        "score": {"fullTime": {"home": gh, "away": ga}},
    }


class FakeClient:
    """Returns a current edition with only TIMED matches and a previous
    edition with finished ones — the exact pre-kickoff World Cup shape."""

    def __init__(self):
        self.calls = []

    async def get(self, url, headers=None, params=None):
        self.calls.append((url, params))
        season = (params or {}).get("season")
        if season is None:
            # Current edition: scheduled only, includes a debutant (id 30)
            payload = {
                "filters": {"season": 2026},
                "competition": {"emblem": None},
                "matches": [
                    _match(101, 10, 20, status="TIMED", date="2026-06-11T20:00:00Z"),
                    _match(102, 30, 10, status="TIMED", date="2026-06-12T20:00:00Z"),
                ],
            }
        else:
            # Previous edition: finished matches for teams 10 and 20 only
            payload = {
                "filters": {"season": season},
                "competition": {"emblem": None},
                "matches": [
                    _match(1, 10, 20, gh=2, ga=1),
                    _match(2, 20, 10, gh=0, ga=3),
                ],
            }

        class R:
            status_code = 200
            headers: dict = {}

            def json(self):
                return payload

            def raise_for_status(self):
                pass

        return R()


@pytest.mark.asyncio
async def test_tournament_prev_edition_fallback_and_debutant():
    league, teams = await fetch_league_with_form(FakeClient(), 1)

    assert league["api_id"] == 1
    assert league["season"] == 2026

    by_id = {t["api_id"]: t for t in teams}
    # All three drawn teams are participants
    assert set(by_id) == {10, 20, 30}

    # Team 10: scored 2 (older) and 3 (newer) — decay-weighted mean mirrored
    # on both splits.
    expected = (2 * FORM_DECAY + 3) / (FORM_DECAY + 1)
    assert by_id[10]["home_goals_scored"] == pytest.approx(expected)
    assert by_id[10]["away_goals_scored"] == pytest.approx(expected)

    # Debutant (30) gets the field-average fallback, not zeros
    assert by_id[30]["home_goals_scored"] > 0
    assert by_id[30]["home_played"] == 0  # flagged as having no own history
