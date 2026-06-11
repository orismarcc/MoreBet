from dataclasses import dataclass, fields

from app.core.markets import MatchMarkets

MIN_PROB = 0.001  # guard against division by zero


def prob_to_odds(prob: float) -> float:
    """Convert probability to decimal fair odds (no margin)."""
    p = max(prob, MIN_PROB)
    return round(1.0 / p, 3)


@dataclass
class FairOdds:
    home_win: float
    draw: float
    away_win: float
    home_or_draw: float
    away_or_draw: float
    home_or_away: float
    over_05: float
    over_15: float
    over_25: float
    over_35: float
    over_45: float
    under_05: float
    under_15: float
    under_25: float
    under_35: float
    under_45: float
    btts_yes: float
    btts_no: float
    ah_home_minus_half: float
    ah_home_minus_one: float
    ah_home_minus_one_half: float
    ah_home_plus_half: float
    ah_away_minus_half: float
    ah_away_minus_one: float
    ah_away_minus_one_half: float
    ah_away_plus_half: float
    btts_and_over_25: float
    btts_and_under_25: float
    home_and_over_25: float
    away_and_over_25: float
    score_0_1_goals: float
    score_2_3_goals: float
    score_4_plus_goals: float


def calc_fair_odds(markets: MatchMarkets) -> FairOdds:
    # FairOdds mirrors MatchMarkets field-by-field; convert each prob to odds.
    return FairOdds(
        **{f.name: prob_to_odds(getattr(markets, f.name)) for f in fields(FairOdds)}
    )


@dataclass
class ValueResult:
    market: str
    fair_odds: float
    bookie_odds: float
    ev_pct: float      # expected value %
    has_value: bool    # True if EV > 0
    kelly_pct: float   # fraction of bankroll the Kelly criterion suggests (0..1)


def calc_value(market: str, fair_odds: float, bookie_odds: float) -> ValueResult:
    """
    EV% = (bookie_odds / fair_odds - 1) × 100
    Positive EV means the bookie is paying more than the fair price.

    Kelly stake = (b·p − q) / b, where:
      - b = bookie_odds − 1 (net profit per unit staked on a win)
      - p = true win probability (= 1 / fair_odds)
      - q = 1 − p
    Returned as a fraction of the bankroll, clamped to [0, 1]. Use a "fractional
    Kelly" (e.g. 25%) downstream if you want a less aggressive sizing.
    """
    ev_pct = round((bookie_odds / fair_odds - 1) * 100, 2)

    p = 1.0 / max(fair_odds, MIN_PROB)
    b = max(bookie_odds - 1.0, 1e-9)
    kelly_raw = (b * p - (1 - p)) / b
    kelly = max(0.0, min(1.0, kelly_raw))

    return ValueResult(
        market=market,
        fair_odds=fair_odds,
        bookie_odds=bookie_odds,
        ev_pct=ev_pct,
        has_value=ev_pct > 0,
        kelly_pct=round(kelly, 4),
    )
