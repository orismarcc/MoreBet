"""
Contract guard: every API response model's fields must match the TypeScript
interface the frontend consumes. This is the cheap insurance against the most
common way a change "breaks the flow between updates" — a field renamed/added
on one side only. If this test fails, backend and frontend drifted; fix the
mismatch before shipping.
"""
import re
from pathlib import Path

import pytest

from app.models.schemas import (
    MarketsOut, FairOddsOut, MatchAnalysisOut, TeamOut, LeagueOut, ScoreProb, ValueCheckOut,
)
from app.services.recommender import ValidatedRecommendation, RecommendationReport, MarketOddsEvent
from app.api.routes.leagues import BacktestOut, CalibrationBucketOut, StandingRow, StandingGroup
from app.api.routes.teams import (
    RecentMatch, RecentSummary, RecentForm, UpcomingTeamMatch, TeamSearchResult,
)
from app.api.routes.matches import H2HMatch, GoalEvent, StatLabel, MatchDetails
from app.api.routes.fixtures import UpcomingFixture as FixtureModel

_TYPES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types"
_IDX = (_TYPES / "index.ts").read_text(encoding="utf8")
_FIX = (_TYPES / "fixtures.ts").read_text(encoding="utf8")


def _ts_fields(src: str, name: str) -> set[str] | None:
    m = re.search(r"interface " + name + r"\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return None
    return set(re.findall(r"^\s+(\w+)\??\s*:", m.group(1), re.M))


# (pydantic model, TS interface name, TS source)
PAIRS = [
    (MarketsOut, "MarketSet", _IDX), (FairOddsOut, "MarketSet", _IDX),
    (MatchAnalysisOut, "MatchAnalysis", _IDX), (TeamOut, "Team", _IDX),
    (LeagueOut, "League", _IDX), (ScoreProb, "ScoreProb", _IDX),
    (ValueCheckOut, "ValueCheckResult", _IDX),
    (ValidatedRecommendation, "AgentRecommendation", _IDX),
    (RecommendationReport, "RecommendationReport", _IDX),
    (MarketOddsEvent, "MarketOddsEvent", _IDX), (BacktestOut, "BacktestReport", _IDX),
    (CalibrationBucketOut, "CalibrationBucket", _IDX), (StandingRow, "StandingRow", _IDX),
    (StandingGroup, "StandingGroup", _IDX), (RecentMatch, "RecentMatch", _IDX),
    (RecentSummary, "RecentSummary", _IDX), (RecentForm, "RecentForm", _IDX),
    (UpcomingTeamMatch, "UpcomingTeamMatch", _IDX), (TeamSearchResult, "TeamSearchResult", _IDX),
    (H2HMatch, "H2HMatch", _IDX), (GoalEvent, "GoalEvent", _IDX),
    (StatLabel, "StatLabel", _IDX), (MatchDetails, "MatchDetails", _IDX),
    (FixtureModel, "UpcomingFixture", _FIX),
]


@pytest.mark.parametrize("model,ts_name,src", PAIRS, ids=[f"{m.__name__}->{n}" for m, n, _ in PAIRS])
def test_response_model_matches_ts_interface(model, ts_name, src):
    py = set(model.model_fields.keys())
    ts = _ts_fields(src, ts_name)
    assert ts is not None, f"TS interface '{ts_name}' not found"
    assert py == ts, (
        f"Contract drift {model.__name__} <-> {ts_name}: "
        f"backend-only={sorted(py - ts)} frontend-only={sorted(ts - py)}"
    )
