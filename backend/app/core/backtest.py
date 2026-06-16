"""
Walk-forward backtesting of the match-analysis model.

For every finished match (in chronological order) the model predicts using
ONLY the matches played before it — exactly the data it would have had on
matchday — and the prediction is scored against the real result. This is the
ground truth for calibration work: every change to shrinkage, decay or the
Poisson layer should move these numbers, not just intuition.

Metrics:
- Brier score (1X2 multiclass, lower = better; ~0.667 for always-uniform)
- Log-loss (lower = better)
- Accuracy of the modal outcome
- Brier skill score vs a no-skill baseline (positive = model beats baseline)
- Calibration table (predicted probability vs observed frequency)

The baseline is the running outcome frequency (Laplace-smoothed): a bettor who
knows only "how often home teams win in this league so far". Beating it means
the team-strength layer adds real information.
"""
import math
from dataclasses import dataclass, field

from app.core.engine import TeamInput, analyse_match
from app.core.ratings import seed_from_matches, team_split_inputs
from app.core.strength import LeagueAverages
from app.services.football_data import _team_form_averages

_EPS = 1e-9

# Don't predict until the league/teams have a minimal sample: predictions from
# 2 games of data are noise and would unfairly drag the metrics.
MIN_LEAGUE_MATCHES = 30
MIN_TEAM_MATCHES = 5
MIN_SPLIT_MATCHES = 2  # at least N home games (home side) / away games (away side)
FORM_WINDOW = 30


@dataclass
class _Prediction:
    p_home: float
    p_draw: float
    p_away: float
    p_over25: float
    p_btts: float
    outcome: int          # 0=home, 1=draw, 2=away
    went_over25: bool
    btts_happened: bool


@dataclass
class BacktestResult:
    n_matches_total: int
    n_predicted: int
    n_skipped: int
    period_from: str | None
    period_to: str | None
    # 1X2
    brier_1x2_model: float | None = None
    brier_1x2_baseline: float | None = None
    skill_score_1x2: float | None = None
    log_loss_model: float | None = None
    log_loss_baseline: float | None = None
    accuracy_model: float | None = None
    accuracy_baseline: float | None = None
    # Binary markets
    brier_over25_model: float | None = None
    brier_over25_baseline: float | None = None
    over25_base_rate: float | None = None
    brier_btts_model: float | None = None
    brier_btts_baseline: float | None = None
    btts_base_rate: float | None = None
    # Calibration: list of (bucket_low, bucket_high, avg_predicted, observed, n)
    calibration: list[dict] = field(default_factory=list)


def _outcome(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def run_backtest(matches: list[dict]) -> BacktestResult:
    """`matches` is chronological (oldest first), each:
    {utc_date, home_id, away_id, home_goals, away_goals}."""
    histories: dict[int, list[dict]] = {}
    # Running league tallies (matches already played before the current one)
    n_played = 0
    sum_home_goals = 0.0
    sum_away_goals = 0.0
    outcome_counts = [0, 0, 0]
    over25_count = 0
    btts_count = 0

    predictions: list[_Prediction] = []
    baselines: list[tuple[float, float, float, float, float]] = []
    skipped = 0
    # Match list seen so far (with opponent ids) — the input to the rating
    # solver. Grown incrementally; mirrors production's seed_from_matches.
    prior_games: list[tuple[int, int, int, int]] = []

    for m in matches:
        home_hist = histories.get(m["home_id"], [])
        away_hist = histories.get(m["away_id"], [])

        prediction_made = False
        if (
            n_played >= MIN_LEAGUE_MATCHES
            and len(home_hist) >= MIN_TEAM_MATCHES
            and len(away_hist) >= MIN_TEAM_MATCHES
        ):
            home_avgs = _team_form_averages(home_hist, FORM_WINDOW)
            away_avgs = _team_form_averages(away_hist, FORM_WINDOW)
            # Same opponent-adjusted ratings the production seeding uses, fit on
            # only the matches played before this one (no leakage).
            ratings, mu_home, mu_away = seed_from_matches(prior_games)
            rh = ratings.get(m["home_id"])
            ra = ratings.get(m["away_id"])
            if (
                home_avgs["home_played"] >= MIN_SPLIT_MATCHES
                and away_avgs["away_played"] >= MIN_SPLIT_MATCHES
                and rh is not None and ra is not None and mu_home > 0
            ):
                league = LeagueAverages(home_goals_avg=mu_home, away_goals_avg=mu_away)
                hs = team_split_inputs(rh, mu_home, mu_away)
                as_ = team_split_inputs(ra, mu_home, mu_away)
                ti = TeamInput(
                    home_goals_scored_avg=hs["home_goals_scored"],
                    home_goals_conceded_avg=hs["home_goals_conceded"],
                    away_goals_scored_avg=as_["away_goals_scored"],
                    away_goals_conceded_avg=as_["away_goals_conceded"],
                )
                analysis = analyse_match(ti, league)
                mk = analysis.markets

                predictions.append(_Prediction(
                    p_home=mk.home_win,
                    p_draw=mk.draw,
                    p_away=mk.away_win,
                    p_over25=mk.over_25,
                    p_btts=mk.btts_yes,
                    outcome=_outcome(m["home_goals"], m["away_goals"]),
                    went_over25=m["home_goals"] + m["away_goals"] > 2.5,
                    btts_happened=m["home_goals"] > 0 and m["away_goals"] > 0,
                ))
                # Laplace-smoothed running frequencies — what a "no model"
                # bettor knows at this point in time.
                baselines.append((
                    (outcome_counts[0] + 1) / (n_played + 3),
                    (outcome_counts[1] + 1) / (n_played + 3),
                    (outcome_counts[2] + 1) / (n_played + 3),
                    (over25_count + 1) / (n_played + 2),
                    (btts_count + 1) / (n_played + 2),
                ))
                prediction_made = True

        if not prediction_made:
            skipped += 1

        # Record the actual result AFTER predicting — never leak the future.
        gh, ga = m["home_goals"], m["away_goals"]
        histories.setdefault(m["home_id"], []).append(
            {"is_home": True, "scored": gh, "conceded": ga})
        histories.setdefault(m["away_id"], []).append(
            {"is_home": False, "scored": ga, "conceded": gh})
        prior_games.append((m["home_id"], m["away_id"], gh, ga))
        n_played += 1
        sum_home_goals += gh
        sum_away_goals += ga
        outcome_counts[_outcome(gh, ga)] += 1
        if gh + ga > 2.5:
            over25_count += 1
        if gh > 0 and ga > 0:
            btts_count += 1

    result = BacktestResult(
        n_matches_total=len(matches),
        n_predicted=len(predictions),
        n_skipped=skipped,
        period_from=matches[0]["utc_date"] if matches else None,
        period_to=matches[-1]["utc_date"] if matches else None,
    )
    if not predictions:
        return result

    n = len(predictions)

    def _brier3(probs_of) -> float:
        total = 0.0
        for p, probs in zip(predictions, probs_of):
            for k in range(3):
                o = 1.0 if p.outcome == k else 0.0
                total += (probs[k] - o) ** 2
        return total / n

    model_1x2 = [(p.p_home, p.p_draw, p.p_away) for p in predictions]
    base_1x2 = [(b[0], b[1], b[2]) for b in baselines]

    result.brier_1x2_model = _brier3(model_1x2)
    result.brier_1x2_baseline = _brier3(base_1x2)
    if result.brier_1x2_baseline > 0:
        result.skill_score_1x2 = 1.0 - result.brier_1x2_model / result.brier_1x2_baseline

    result.log_loss_model = -sum(
        math.log(max(probs[p.outcome], _EPS))
        for p, probs in zip(predictions, model_1x2)
    ) / n
    result.log_loss_baseline = -sum(
        math.log(max(probs[p.outcome], _EPS))
        for p, probs in zip(predictions, base_1x2)
    ) / n

    result.accuracy_model = sum(
        1 for p, probs in zip(predictions, model_1x2)
        if probs.index(max(probs)) == p.outcome
    ) / n
    result.accuracy_baseline = sum(
        1 for p, probs in zip(predictions, base_1x2)
        if probs.index(max(probs)) == p.outcome
    ) / n

    def _brier2(pairs) -> float:
        return sum((prob - (1.0 if happened else 0.0)) ** 2 for prob, happened in pairs) / n

    result.brier_over25_model = _brier2((p.p_over25, p.went_over25) for p in predictions)
    result.brier_over25_baseline = _brier2(
        (b[3], p.went_over25) for p, b in zip(predictions, baselines))
    result.over25_base_rate = sum(1 for p in predictions if p.went_over25) / n

    result.brier_btts_model = _brier2((p.p_btts, p.btts_happened) for p in predictions)
    result.brier_btts_baseline = _brier2(
        (b[4], p.btts_happened) for p, b in zip(predictions, baselines))
    result.btts_base_rate = sum(1 for p in predictions if p.btts_happened) / n

    # Calibration: pool the three 1X2 (probability, outcome) pairs of every
    # match into 10%-wide buckets. Well-calibrated ⇒ observed ≈ predicted.
    buckets: list[list[float]] = [[0.0, 0.0, 0] for _ in range(10)]
    for p, probs in zip(predictions, model_1x2):
        for k in range(3):
            idx = min(int(probs[k] * 10), 9)
            buckets[idx][0] += probs[k]
            buckets[idx][1] += 1.0 if p.outcome == k else 0.0
            buckets[idx][2] += 1
    result.calibration = [
        {
            "range_low": i / 10,
            "range_high": (i + 1) / 10,
            "predicted_avg": round(b[0] / b[2], 4),
            "observed_freq": round(b[1] / b[2], 4),
            "count": int(b[2]),
        }
        for i, b in enumerate(buckets) if b[2] > 0
    ]
    return result
