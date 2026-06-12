"""Calibration guards: shrinkage, form decay and the xG completeness gate.

These tests pin the behaviours that keep the model honest at the extremes —
overconfident favourites, 0% win probabilities and partial-xG corruption.
"""
import pytest

from app.core.engine import TeamInput, analyse_match
from app.core.strength import LeagueAverages, shrink_avg
from app.services.football_data import (
    _decay_weights,
    _team_form_averages,
    _team_neutral_averages,
)

LEAGUE = LeagueAverages(home_goals_avg=1.55, away_goals_avg=1.25)


class TestShrinkage:
    def test_none_played_keeps_average_untouched(self):
        assert shrink_avg(2.6, None, 1.55) == 2.6

    def test_pulls_toward_league_average(self):
        shrunk = shrink_avg(2.6, 10, 1.55)
        assert 1.55 < shrunk < 2.6

    def test_more_games_means_less_shrinkage(self):
        few = shrink_avg(2.6, 5, 1.55)
        many = shrink_avg(2.6, 20, 1.55)
        assert abs(many - 1.55) > abs(few - 1.55)

    def test_zero_games_returns_league_average(self):
        assert shrink_avg(0.0, 0, 1.55) == pytest.approx(1.55)

    def test_engine_without_counts_is_backward_compatible(self):
        ti = TeamInput(
            home_goals_scored_avg=2.0, home_goals_conceded_avg=1.1,
            away_goals_scored_avg=1.2, away_goals_conceded_avg=1.5,
        )
        r = analyse_match(ti, LEAGUE)
        # Unshrunk: λ_home = (2.0/1.55) × (1.5/1.55) × 1.55
        assert r.lambda_home == pytest.approx((2.0 / 1.55) * (1.5 / 1.55) * 1.55)

    def test_strong_favourite_is_tempered(self):
        """City-vs-bottom-side: raw model said 92%+; with shrinkage the
        probability must land closer to real market prices (≤ 88%)."""
        kwargs = dict(
            home_goals_scored_avg=2.6, home_goals_conceded_avg=0.8,
            away_goals_scored_avg=0.7, away_goals_conceded_avg=2.2,
        )
        raw = analyse_match(TeamInput(**kwargs), LEAGUE)
        shrunk = analyse_match(TeamInput(**kwargs, home_played=12, away_played=12), LEAGUE)
        assert shrunk.markets.home_win < raw.markets.home_win
        assert shrunk.markets.home_win <= 0.88

    def test_goalless_team_never_has_zero_win_probability(self):
        ti = TeamInput(
            home_goals_scored_avg=0.0, home_goals_conceded_avg=1.5,
            away_goals_scored_avg=1.5, away_goals_conceded_avg=1.0,
            home_played=8, away_played=8,
        )
        r = analyse_match(ti, LEAGUE)
        assert r.lambda_home > 0
        assert r.markets.home_win > 0.01

    def test_defensive_duel_0_0_is_not_extreme(self):
        """Two packed defences: raw model gave 0-0 a 38.8% chance — far above
        anything seen in real markets. Shrinkage must keep it under 25%."""
        ti = TeamInput(
            home_goals_scored_avg=0.9, home_goals_conceded_avg=0.7,
            away_goals_scored_avg=0.8, away_goals_conceded_avg=0.9,
            home_played=12, away_played=12,
        )
        r = analyse_match(ti, LEAGUE)
        assert r.matrix.prob_score(0, 0) < 0.25


class TestXgGate:
    BASE = dict(
        home_goals_scored_avg=1.5, home_goals_conceded_avg=1.3,
        away_goals_scored_avg=1.2, away_goals_conceded_avg=1.4,
    )
    LEAGUE_XG = LeagueAverages(
        home_goals_avg=1.55, away_goals_avg=1.25,
        home_xg_avg=1.5, away_xg_avg=1.2,
    )

    def test_partial_xg_is_ignored(self):
        """Missing any xG field must fall back to the goals-only model instead
        of zeroing one side's strength (the old `or 0` bug)."""
        no_xg = analyse_match(TeamInput(**self.BASE), self.LEAGUE_XG)
        partial = analyse_match(
            TeamInput(
                **self.BASE,
                home_xg_scored_avg=1.6, home_xg_conceded_avg=None,
                away_xg_scored_avg=None, away_xg_conceded_avg=1.3,
            ),
            self.LEAGUE_XG,
        )
        assert partial.lambda_home == pytest.approx(no_xg.lambda_home)
        assert partial.lambda_away == pytest.approx(no_xg.lambda_away)

    def test_complete_xg_still_blends(self):
        full = analyse_match(
            TeamInput(
                **self.BASE,
                home_xg_scored_avg=1.9, home_xg_conceded_avg=1.0,
                away_xg_scored_avg=1.1, away_xg_conceded_avg=1.3,
            ),
            self.LEAGUE_XG,
        )
        no_xg = analyse_match(TeamInput(**self.BASE), self.LEAGUE_XG)
        assert full.lambda_home != pytest.approx(no_xg.lambda_home)


class TestFormDecay:
    def test_newest_match_has_weight_one(self):
        w = _decay_weights(5)
        assert w[-1] == 1.0
        assert all(w[i] < w[i + 1] for i in range(len(w) - 1))

    def test_recent_games_dominate_form(self):
        """A team that was bad early but scores 3/game in its last games must
        average above the simple mean."""
        history = (
            [{"is_home": True, "scored": 0, "conceded": 2}] * 10
            + [{"is_home": True, "scored": 3, "conceded": 0}] * 5
        )
        avgs = _team_form_averages(history, last_n=30)
        simple_mean = (0 * 10 + 3 * 5) / 15
        assert avgs["home_goals_scored"] > simple_mean

    def test_neutral_averages_still_mirror_splits(self):
        history = [
            {"is_home": True, "scored": 2, "conceded": 1},
            {"is_home": False, "scored": 0, "conceded": 3},
            {"is_home": True, "scored": 1, "conceded": 1},
        ]
        avgs = _team_neutral_averages(history, last_n=30)
        assert avgs["home_goals_scored"] == avgs["away_goals_scored"]
        assert avgs["home_goals_conceded"] == avgs["away_goals_conceded"]
        assert avgs["home_played"] == avgs["away_played"] == 3


class TestExtendedMatrix:
    def test_blowout_top_score_is_not_the_residual_bucket(self):
        """λ≈6.8 used to surface '8-0' at 30% because P(8+) was lumped into
        the last cell of an 8×8 matrix. With 10 buckets the mode is sane."""
        ti = TeamInput(
            home_goals_scored_avg=3.5, home_goals_conceded_avg=0.5,
            away_goals_scored_avg=0.5, away_goals_conceded_avg=3.0,
        )
        r = analyse_match(ti, LEAGUE)
        top_home, _top_away, top_p = r.top_scores[0]
        assert top_home < r.matrix.max_goals  # mode is a real score, not the tail
        assert top_p < 0.25

    def test_matrix_still_sums_to_one(self):
        ti = TeamInput(
            home_goals_scored_avg=3.5, home_goals_conceded_avg=0.5,
            away_goals_scored_avg=0.5, away_goals_conceded_avg=3.0,
        )
        r = analyse_match(ti, LEAGUE)
        total = sum(sum(row) for row in r.matrix.matrix)
        assert total == pytest.approx(1.0)
