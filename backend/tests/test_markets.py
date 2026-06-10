"""
Tests for ScoreMatrix, MatchMarkets, FairOdds and ValueFinder.
Reference values cross-checked with published Poisson football models.
"""
import pytest

from app.core.matrix import ScoreMatrix
from app.core.markets import calc_markets
from app.core.odds import calc_fair_odds, calc_value, prob_to_odds


class TestScoreMatrix:
    def test_matrix_sums_to_one(self):
        m = ScoreMatrix(lambda_home=1.5, lambda_away=1.2)
        total = sum(m.matrix[h][a] for h in range(m.max_goals + 1) for a in range(m.max_goals + 1))
        assert abs(total - 1.0) < 1e-6

    def test_top_scores_sorted_descending(self):
        m = ScoreMatrix(lambda_home=1.5, lambda_away=1.2)
        top = m.top_scores(5)
        probs = [p for _, _, p in top]
        assert probs == sorted(probs, reverse=True)

    def test_top_scores_length(self):
        m = ScoreMatrix(lambda_home=1.5, lambda_away=1.2)
        assert len(m.top_scores(10)) == 10


class TestMatchMarkets:
    def setup_method(self):
        self.matrix = ScoreMatrix(lambda_home=1.5, lambda_away=1.2)
        self.markets = calc_markets(self.matrix)

    def test_1x2_sums_to_one(self):
        total = self.markets.home_win + self.markets.draw + self.markets.away_win
        assert abs(total - 1.0) < 1e-6

    def test_btts_complement(self):
        assert abs(self.markets.btts_yes + self.markets.btts_no - 1.0) < 1e-6

    def test_over_under_complement(self):
        for line in ["05", "15", "25", "35"]:
            over = getattr(self.markets, f"over_{line}")
            under = getattr(self.markets, f"under_{line}")
            assert abs(over + under - 1.0) < 1e-4, f"Failed for line {line}"

    def test_double_chance_gt_single(self):
        assert self.markets.home_or_draw > self.markets.home_win
        assert self.markets.home_or_draw > self.markets.draw

    def test_home_favoured_when_lambda_higher(self):
        assert self.markets.home_win > self.markets.away_win

    def test_known_probabilities_range(self):
        # With λ_home=1.5, λ_away=1.2, home win should be roughly 45–55%
        assert 0.40 < self.markets.home_win < 0.60
        # Over 2.5 with combined λ≈2.7 should be ~55–70%
        assert 0.50 < self.markets.over_25 < 0.75


class TestFairOdds:
    def test_odds_are_reciprocal_of_prob(self):
        m = ScoreMatrix(lambda_home=1.5, lambda_away=1.2)
        markets = calc_markets(m)
        odds = calc_fair_odds(markets)
        assert abs(odds.home_win - 1.0 / markets.home_win) < 0.001
        assert abs(odds.draw - 1.0 / markets.draw) < 0.001

    def test_minimum_odds_one(self):
        m = ScoreMatrix(lambda_home=1.5, lambda_away=1.2)
        markets = calc_markets(m)
        odds = calc_fair_odds(markets)
        assert odds.home_win >= 1.0
        assert odds.away_win >= 1.0


class TestValueFinder:
    def test_positive_ev_when_bookie_higher(self):
        result = calc_value("1X2_home", fair_odds=1.81, bookie_odds=2.10)
        assert result.has_value is True
        assert result.ev_pct > 0

    def test_zero_ev_when_equal(self):
        result = calc_value("1X2_home", fair_odds=2.0, bookie_odds=2.0)
        assert result.ev_pct == 0.0
        assert result.has_value is False

    def test_negative_ev_when_bookie_lower(self):
        result = calc_value("1X2_home", fair_odds=2.0, bookie_odds=1.80)
        assert result.has_value is False
        assert result.ev_pct < 0

    def test_ev_formula(self):
        # EV% = (bookie / fair - 1) × 100
        result = calc_value("draw", fair_odds=3.40, bookie_odds=3.80)
        expected_ev = (3.80 / 3.40 - 1) * 100
        assert abs(result.ev_pct - expected_ev) < 0.01


class TestProbToOdds:
    def test_fifty_percent_is_2(self):
        assert prob_to_odds(0.5) == 2.0

    def test_hundred_percent_is_1(self):
        assert prob_to_odds(1.0) == 1.0

    def test_min_prob_guard(self):
        # Should not raise division by zero
        result = prob_to_odds(0.0)
        assert result > 0
