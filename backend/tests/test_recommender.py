"""Anti-hallucination enforcement layer of the recommendation agent.

These tests never call the Claude API — they pin the code-level guarantees:
unknown markets are dropped, the 3-recommendation cap holds, and confidence
levels that violate the probability/sample rules are downgraded.
"""
from app.services.recommender import (
    AgentRecommendation,
    AgentReport,
    MARKET_LABELS,
    validate_report,
)

MARKETS = {
    "home_win": 0.70,
    "home_or_draw": 0.85,
    "over_25": 0.58,
    "btts_yes": 0.52,
    "under_45": 0.93,
}


def _report(recs: list[AgentRecommendation]) -> AgentReport:
    return AgentReport(no_bet=False, summary="resumo", recommendations=recs)


def _rec(market: str, confidence: str = "alta") -> AgentRecommendation:
    return AgentRecommendation(market=market, confidence=confidence, rationale="ok")


class TestValidateReport:
    def test_unknown_market_is_dropped(self):
        recs, notes = validate_report(
            _report([_rec("home_win"), _rec("mercado_inventado")]),
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert [r.market for r in recs] == ["home_win"]
        assert any("desconhecido" in n.lower() for n in notes)

    def test_more_than_max_are_trimmed(self):
        recs, notes = validate_report(
            _report([_rec("home_win"), _rec("home_or_draw"), _rec("over_25"), _rec("under_45")]),
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert len(recs) == 2
        assert any("limitado" in n for n in notes)

    def test_duplicates_are_removed(self):
        recs, _ = validate_report(
            _report([_rec("home_win"), _rec("home_win")]),
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert len(recs) == 1

    def test_probability_and_fair_odds_come_from_our_model(self):
        recs, _ = validate_report(
            _report([_rec("home_win")]), MARKETS, min_sample=10, backtest_skill=0.05)
        r = recs[0]
        assert r.model_probability == 0.70
        assert r.fair_odds == round(1 / 0.70, 3)
        # Minimum bookie odds embed the value margin → every bet is +EV
        assert r.min_bookie_odds == round(r.fair_odds * 1.04, 3)
        assert r.market_label == MARKET_LABELS["home_win"]

    def test_quarter_kelly_stake(self):
        recs, _ = validate_report(
            _report([_rec("home_win")]), MARKETS, min_sample=10, backtest_skill=0.05)
        # kelly = m·p / (1 + m − p) com m=0.04, p=0.70 → /4
        expected = (0.04 * 0.70 / (1.04 - 0.70)) / 4
        assert abs(recs[0].suggested_stake_pct - round(expected, 4)) < 1e-9

    def test_micro_odds_cannot_be_high_confidence(self):
        """fair 1/0.85 = 1.176 < 1.30 → alta vira media (regra de lucro)."""
        recs, _ = validate_report(
            _report([_rec("home_or_draw", "alta")]),
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert recs[0].confidence == "media"
        assert any("micro-odds" in c.lower() for c in recs[0].caveats)

    def test_high_confidence_downgraded_below_65pct(self):
        recs, _ = validate_report(
            _report([_rec("over_25", "alta")]),  # 0.58 < 0.65
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert recs[0].confidence == "media"
        assert any("rebaixada" in c.lower() for c in recs[0].caveats)

    def test_any_confidence_downgraded_below_55pct(self):
        recs, _ = validate_report(
            _report([_rec("btts_yes", "media")]),  # 0.52 < 0.55
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert recs[0].confidence == "baixa"

    def test_high_confidence_requires_sample(self):
        recs, _ = validate_report(
            _report([_rec("home_win", "alta")]),  # prob ok, sample 4 < 8
            MARKETS, min_sample=4, backtest_skill=0.05,
        )
        assert recs[0].confidence == "media"

    def test_high_confidence_requires_positive_backtest_skill(self):
        recs, _ = validate_report(
            _report([_rec("home_win", "alta")]),
            MARKETS, min_sample=10, backtest_skill=-0.02,
        )
        assert recs[0].confidence == "media"

    def test_compliant_high_confidence_survives(self):
        recs, _ = validate_report(
            _report([_rec("home_win", "alta")]),  # 0.70 → fair 1.43 ≥ 1.30, tudo ok
            MARKETS, min_sample=10, backtest_skill=0.05,
        )
        assert recs[0].confidence == "alta"
        assert recs[0].caveats == []

    def test_all_markets_have_labels(self):
        from app.core.markets import MatchMarkets
        from dataclasses import fields
        for f in fields(MatchMarkets):
            assert f.name in MARKET_LABELS, f"sem label pt-BR: {f.name}"
