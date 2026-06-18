"""
Elo ratings for national teams.

Goal-ratio attack/defense ratings (ratings.py) are unreliable for national
teams: friendly/qualifier scorelines are noisy, and confederations barely play
each other, so a multiplicative goals model misranks across them badly (it put
Portugal at ~23% to beat Morocco). Elo fixes both problems — it learns from
RESULTS (margin only secondary), and sparse cross-confederation games still
link the scale over time. This is the gold standard for international football
(eloratings.net). Calibrated by walk-forward backtest over real internationals.
"""
from dataclasses import dataclass

START_ELO = 1500.0


@dataclass
class EloParams:
    # Defaults won a walk-forward Brier sweep over ~900 real internationals
    # (k∈30..50, scale∈120..170, total∈2.5..2.7): Brier 0.573, log-loss 0.965,
    # calibration within ~2pp across all probability buckets.
    k: float = 50.0          # base update weight
    hfa: float = 65.0        # home-field advantage in Elo points (0 at neutral)
    scale: float = 170.0     # Elo points per goal of expected supremacy
    total: float = 2.5       # baseline total goals (both teams) in a match
    min_lambda: float = 0.18


def _mov_multiplier(goal_diff: int) -> float:
    """Margin-of-victory multiplier (World Football Elo). Bigger wins move the
    rating more, with diminishing returns so blowouts don't dominate."""
    d = abs(goal_diff)
    if d <= 1:
        return 1.0
    if d == 2:
        return 1.5
    if d == 3:
        return 1.75
    return 1.75 + (d - 3) / 8.0


def _expected(elo_home: float, elo_away: float, hfa: float) -> float:
    """Expected score for the home side (1=win, .5=draw, 0=loss space)."""
    return 1.0 / (1.0 + 10 ** (-(elo_home - elo_away + hfa) / 400.0))


def compute_elo(
    matches: list[dict], params: EloParams | None = None
) -> dict[object, float]:
    """Ratings from a chronologically-sorted match list. Each match:
    {home_id, away_id, home_goals, away_goals, neutral: bool}. Unknown teams
    start at 1500. Returns {team_id: elo}."""
    p = params or EloParams()
    elo: dict[object, float] = {}
    for m in matches:
        h, a = m["home_id"], m["away_id"]
        eh = elo.get(h, START_ELO)
        ea = elo.get(a, START_ELO)
        hfa = 0.0 if m.get("neutral") else p.hfa
        exp_h = _expected(eh, ea, hfa)
        gh, ga = m["home_goals"], m["away_goals"]
        score_h = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        delta = p.k * _mov_multiplier(gh - ga) * (score_h - exp_h)
        elo[h] = eh + delta
        elo[a] = ea - delta
    return elo


def elo_to_lambdas(
    elo_home: float, elo_away: float, *, neutral: bool, params: EloParams | None = None
) -> tuple[float, float]:
    """Map two Elo ratings to expected goals (λ_home, λ_away).

    Supremacy (goal difference) is linear in the Elo gap; total goals is a
    baseline nudged up slightly for mismatches (favourites pad the score). Both
    λ are floored so no side is ever a literal zero."""
    p = params or EloParams()
    dr = elo_home - elo_away + (0.0 if neutral else p.hfa)
    supremacy = dr / p.scale
    # Mismatches produce a few more goals than two evenly-matched sides.
    total = p.total + min(abs(supremacy) * 0.12, 0.6)
    lam_home = max(p.min_lambda, (total + supremacy) / 2.0)
    lam_away = max(p.min_lambda, (total - supremacy) / 2.0)
    return lam_home, lam_away
