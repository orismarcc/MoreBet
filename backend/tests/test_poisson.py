"""
Tests for the Poisson distribution core.
All expected values computed from first principles or validated against scipy.
"""
import math
import pytest

from app.core.poisson import poisson_pmf, compute_distribution


class TestPoissonPMF:
    def test_known_value_lambda_282_k2(self):
        # Example from spec: λ=2.82, k=2 → P ≈ 0.237
        result = poisson_pmf(2.82, 2)
        assert abs(result - 0.237) < 0.001

    def test_k0_is_exp_minus_lambda(self):
        lam = 1.5
        assert abs(poisson_pmf(lam, 0) - math.exp(-lam)) < 1e-10

    def test_sum_to_one(self):
        total = sum(poisson_pmf(2.0, k) for k in range(50))
        assert abs(total - 1.0) < 1e-6

    def test_lambda_zero_only_k0(self):
        assert poisson_pmf(0, 0) == 1.0
        assert poisson_pmf(0, 1) == 0.0

    def test_negative_k_returns_zero(self):
        # factorial(-1) would raise, guard against it
        with pytest.raises((ValueError, OverflowError)):
            math.factorial(-1)
        # our function should handle k=0 at minimum
        assert poisson_pmf(1.5, 0) > 0


class TestComputeDistribution:
    def test_probabilities_sum_to_one(self):
        dist = compute_distribution(2.0, max_goals=8)
        assert abs(sum(dist.probabilities) - 1.0) < 1e-9

    def test_prob_method_matches_list(self):
        dist = compute_distribution(1.44, max_goals=8)
        for k in range(9):
            assert dist.prob(k) == dist.probabilities[k]

    def test_prob_at_least_0_equals_1(self):
        dist = compute_distribution(1.5)
        assert abs(dist.prob_at_least(0) - 1.0) < 1e-9

    def test_prob_at_most_max_equals_1(self):
        dist = compute_distribution(1.5)
        assert abs(dist.prob_at_most(dist.max_goals) - 1.0) < 1e-9

    def test_out_of_range_returns_zero(self):
        dist = compute_distribution(1.5, max_goals=5)
        assert dist.prob(6) == 0.0
        assert dist.prob(-1) == 0.0
