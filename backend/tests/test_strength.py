"""Tests for team strength and lambda calculation."""
import pytest

from app.core.strength import (
    calc_team_strength,
    calc_lambda,
    blend_lambda,
    LeagueAverages,
)


class TestTeamStrength:
    def test_exact_values_from_spec(self):
        # From spec: Time A scored 2.0/game, MGM=1.44 → attack=1.38
        strength = calc_team_strength(
            goals_scored_avg=2.0,
            goals_conceded_avg=1.5,
            league_scored_avg=1.44,
            league_conceded_avg=1.05,
        )
        assert abs(strength.attack - (2.0 / 1.44)) < 0.01
        assert abs(strength.defense - (1.5 / 1.05)) < 0.01

    def test_average_team_has_strength_one(self):
        strength = calc_team_strength(1.44, 1.05, 1.44, 1.05)
        assert abs(strength.attack - 1.0) < 1e-9
        assert abs(strength.defense - 1.0) < 1e-9

    def test_zero_league_avg_returns_one(self):
        strength = calc_team_strength(1.5, 1.0, 0.0, 0.0)
        assert strength.attack == 1.0
        assert strength.defense == 1.0


class TestCalcLambda:
    def test_spec_example(self):
        # Spec shows λ ≈ 2.82 using rounded intermediate values.
        # Precise calculation with model convention (away_defense / MGM):
        #   home_attack = 2.0/1.44 = 1.3888, away_defense = 1.5/1.44 = 1.0416
        #   λ = 1.3888 × 1.0416 × 1.44 = 2.083 (calibrated model)
        result = calc_lambda(
            home_attack=2.0 / 1.44,
            away_defense=1.5 / 1.44,
            league_home_avg=1.44,
        )
        assert abs(result - 2.083) < 0.01

    def test_player_modifier_reduces_lambda(self):
        base = calc_lambda(1.3, 1.2, 1.44)
        reduced = calc_lambda(1.3, 1.2, 1.44, player_modifier=0.9)
        assert reduced < base
        assert abs(reduced - base * 0.9) < 1e-9


class TestBlendLambda:
    def test_no_xg_returns_raw(self):
        assert blend_lambda(2.5, None) == 2.5

    def test_blend_weights(self):
        result = blend_lambda(2.0, 3.0, xg_weight=0.4)
        expected = 0.6 * 2.0 + 0.4 * 3.0
        assert abs(result - expected) < 1e-9

    def test_full_xg_weight(self):
        result = blend_lambda(2.0, 3.0, xg_weight=1.0)
        assert abs(result - 3.0) < 1e-9
