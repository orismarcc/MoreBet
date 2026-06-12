"""Walk-forward backtest: leak-free replay and metric sanity."""
import pytest

from app.core.backtest import (
    MIN_LEAGUE_MATCHES,
    run_backtest,
)


def _match(day: int, home: int, away: int, gh: int, ga: int) -> dict:
    return {
        "utc_date": f"2025-01-{day:02d}T15:00:00Z" if day <= 31 else f"2025-02-{day-31:02d}T15:00:00Z",
        "home_id": home,
        "away_id": away,
        "home_goals": gh,
        "away_goals": ga,
    }


def _hierarchy_league(rounds: int = 8) -> list[dict]:
    """4 teams with a strict pecking order: lower id beats higher id 3-0 at
    home and 2-0 away. Perfectly predictable — the model should crush the
    frequency baseline here."""
    teams = [1, 2, 3, 4]
    matches: list[dict] = []
    day = 1
    for _ in range(rounds):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                if h < a:
                    matches.append(_match(day, h, a, 3, 0))
                else:
                    matches.append(_match(day, h, a, 0, 2))
                day = day % 55 + 1
    matches.sort(key=lambda m: m["utc_date"])
    return matches


class TestRunBacktest:
    def test_insufficient_data_predicts_nothing(self):
        matches = _hierarchy_league(rounds=1)  # 12 matches < MIN_LEAGUE_MATCHES
        r = run_backtest(matches)
        assert r.n_predicted == 0
        assert r.n_skipped == len(matches)
        assert r.brier_1x2_model is None

    def test_warmup_is_respected(self):
        matches = _hierarchy_league(rounds=8)
        r = run_backtest(matches)
        assert r.n_predicted > 0
        # Nothing predicted before the league warm-up window
        assert r.n_skipped >= MIN_LEAGUE_MATCHES
        assert r.n_predicted + r.n_skipped == r.n_matches_total

    def test_metrics_in_valid_ranges(self):
        r = run_backtest(_hierarchy_league(rounds=8))
        assert 0.0 <= r.brier_1x2_model <= 2.0
        assert 0.0 <= r.brier_1x2_baseline <= 2.0
        assert 0.0 <= r.accuracy_model <= 1.0
        assert r.log_loss_model > 0
        assert 0.0 <= r.brier_over25_model <= 1.0
        assert 0.0 <= r.brier_btts_model <= 1.0

    def test_model_beats_baseline_on_predictable_league(self):
        """With a strict pecking order, team strengths are everything — the
        model must beat the outcome-frequency baseline by a wide margin."""
        r = run_backtest(_hierarchy_league(rounds=8))
        assert r.skill_score_1x2 > 0.2
        assert r.accuracy_model > r.accuracy_baseline
        assert r.log_loss_model < r.log_loss_baseline

    def test_calibration_buckets_are_consistent(self):
        r = run_backtest(_hierarchy_league(rounds=8))
        # 3 pooled (prob, outcome) pairs per predicted match
        assert sum(b["count"] for b in r.calibration) == r.n_predicted * 3
        for b in r.calibration:
            assert b["range_low"] <= b["predicted_avg"] <= b["range_high"] + 1e-9
            assert 0.0 <= b["observed_freq"] <= 1.0

    def test_empty_input(self):
        r = run_backtest([])
        assert r.n_matches_total == 0
        assert r.n_predicted == 0
        assert r.calibration == []
