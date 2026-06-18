"""Elo model for national teams — ordering, symmetry and lambda sanity."""
import pytest

from app.core.elo import (
    EloParams,
    compute_elo,
    elo_to_lambdas,
    _expected,
    _mov_multiplier,
    START_ELO,
)


def _m(h, a, hg, ag, neutral=True):
    return {"home_id": h, "away_id": a, "home_goals": hg, "away_goals": ag, "neutral": neutral}


class TestComputeElo:
    def test_winner_gains_loser_loses(self):
        elo = compute_elo([_m("A", "B", 2, 0)])
        assert elo["A"] > START_ELO > elo["B"]

    def test_zero_sum(self):
        elo = compute_elo([_m("A", "B", 3, 1)])
        assert elo["A"] + elo["B"] == pytest.approx(2 * START_ELO)

    def test_consistent_winner_rises_to_top(self):
        # A beats everyone, D loses to everyone → A top, D bottom
        games = [
            _m("A", "B", 2, 0), _m("A", "C", 1, 0), _m("A", "D", 3, 0),
            _m("B", "C", 1, 0), _m("B", "D", 2, 0), _m("C", "D", 1, 0),
        ] * 3
        elo = compute_elo(games)
        order = sorted(elo, key=lambda k: -elo[k])
        assert order[0] == "A" and order[-1] == "D"

    def test_bigger_win_moves_more(self):
        small = compute_elo([_m("A", "B", 1, 0)])["A"]
        big = compute_elo([_m("A", "B", 5, 0)])["A"]
        assert big > small

    def test_draw_between_equals_is_neutral(self):
        elo = compute_elo([_m("A", "B", 1, 1)])
        assert elo["A"] == pytest.approx(START_ELO)
        assert elo["B"] == pytest.approx(START_ELO)

    def test_home_advantage_dampens_home_win_gain(self):
        # Winning at home (expected) gains less than winning at a neutral site
        home = compute_elo([_m("A", "B", 1, 0, neutral=False)])["A"]
        neut = compute_elo([_m("A", "B", 1, 0, neutral=True)])["A"]
        assert home < neut


class TestEloToLambdas:
    def test_equal_teams_symmetric(self):
        lh, la = elo_to_lambdas(1700, 1700, neutral=True)
        assert lh == pytest.approx(la)

    def test_favorite_has_higher_lambda(self):
        lh, la = elo_to_lambdas(1900, 1500, neutral=True)
        assert lh > la
        assert la >= EloParams().min_lambda

    def test_bigger_gap_bigger_supremacy(self):
        sup_small = (lambda r: r[0] - r[1])(elo_to_lambdas(1750, 1700, neutral=True))
        sup_big = (lambda r: r[0] - r[1])(elo_to_lambdas(2000, 1500, neutral=True))
        assert sup_big > sup_small

    def test_home_advantage_lifts_home(self):
        neutral = elo_to_lambdas(1700, 1700, neutral=True)
        at_home = elo_to_lambdas(1700, 1700, neutral=False)
        assert at_home[0] > neutral[0]

    def test_strong_vs_weak_is_clear_favorite(self):
        """A 300-Elo gap (e.g. Portugal vs a minnow) must make the favourite a
        clear ~75%+ pick — the bug being fixed (was ~35% on the goals model)."""
        import math
        lh, la = elo_to_lambdas(1714, 1412, neutral=True)

        def pois(l, k):
            return math.exp(-l) * l ** k / math.factorial(k)
        ph = sum(
            pois(lh, h) * pois(la, a)
            for h in range(11) for a in range(11) if h > a
        )
        assert ph > 0.70


def test_expected_and_mov_helpers():
    assert _expected(1500, 1500, 0) == pytest.approx(0.5)
    assert _expected(1900, 1500, 0) > 0.9
    assert _mov_multiplier(1) == 1.0
    assert _mov_multiplier(2) == 1.5
    assert _mov_multiplier(5) > _mov_multiplier(3)
