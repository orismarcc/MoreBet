from dataclasses import dataclass

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
    under_05: float
    under_15: float
    under_25: float
    under_35: float
    btts_yes: float
    btts_no: float
    ah_home_minus_half: float
    ah_away_minus_half: float


def calc_fair_odds(markets: MatchMarkets) -> FairOdds:
    return FairOdds(
        home_win=prob_to_odds(markets.home_win),
        draw=prob_to_odds(markets.draw),
        away_win=prob_to_odds(markets.away_win),
        home_or_draw=prob_to_odds(markets.home_or_draw),
        away_or_draw=prob_to_odds(markets.away_or_draw),
        home_or_away=prob_to_odds(markets.home_or_away),
        over_05=prob_to_odds(markets.over_05),
        over_15=prob_to_odds(markets.over_15),
        over_25=prob_to_odds(markets.over_25),
        over_35=prob_to_odds(markets.over_35),
        under_05=prob_to_odds(markets.under_05),
        under_15=prob_to_odds(markets.under_15),
        under_25=prob_to_odds(markets.under_25),
        under_35=prob_to_odds(markets.under_35),
        btts_yes=prob_to_odds(markets.btts_yes),
        btts_no=prob_to_odds(markets.btts_no),
        ah_home_minus_half=prob_to_odds(markets.ah_home_minus_half),
        ah_away_minus_half=prob_to_odds(markets.ah_away_minus_half),
    )


@dataclass
class ValueResult:
    market: str
    fair_odds: float
    bookie_odds: float
    ev_pct: float      # expected value %
    has_value: bool    # True if EV > 0


def calc_value(market: str, fair_odds: float, bookie_odds: float) -> ValueResult:
    """
    EV% = (bookie_odds / fair_odds - 1) × 100
    Positive EV means the bookie is paying more than the fair price.
    """
    ev_pct = round((bookie_odds / fair_odds - 1) * 100, 2)
    return ValueResult(
        market=market,
        fair_odds=fair_odds,
        bookie_odds=bookie_odds,
        ev_pct=ev_pct,
        has_value=ev_pct > 0,
    )
