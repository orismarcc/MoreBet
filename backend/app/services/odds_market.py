"""
Real bookmaker odds via the-odds-api (v4) — closes the value loop.

The recommender computes, per market, the minimum odds a bookmaker must pay for
the bet to carry +VALUE_MARGIN of edge (`min_bookie_odds`). This service fetches
the actual market odds (Pinnacle, Betfair and ~20 more) and reports the best
available price per market, so the UI can show whether that bar is really
cleared and the true EV at that price.

Free tier = 500 credits/month and one /odds call returns every event of a
competition, so responses are cached per sport with a generous TTL. The key is
optional: without it, recommendations simply ship without market comparison.
"""
import logging
import time
import unicodedata

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Our internal league api_id -> the-odds-api sport key.
LEAGUE_TO_SPORT: dict[int, str] = {
    1:   "soccer_fifa_world_cup",
    39:  "soccer_epl",
    140: "soccer_spain_la_liga",
    135: "soccer_italy_serie_a",
    78:  "soccer_germany_bundesliga",
    61:  "soccer_france_ligue_one",
    71:  "soccer_brazil_campeonato",
    94:  "soccer_portugal_primeira_liga",
    88:  "soccer_netherlands_eredivisie",
}

# Featured markets only — h2h (1X2) and totals (O/U) are the universal, liquid
# markets available at the sport level (one call returns every event). Additional
# markets like btts/double_chance need per-event calls (extra credits) and 422
# the sport endpoint, so we skip them: those recommendations still show the
# value bar, just without a real-odds comparison. Cost = markets × regions.
_MARKETS = "h2h,totals"
_REGIONS = "eu"
_TTL = 1800.0  # 30 min — lines move, but not within a single analysis session
_cache: dict[str, tuple[float, list]] = {}

# National-team / club naming differences between providers that token overlap
# alone won't catch. Folded (lowercase, no accents) on both sides.
_ALIASES: dict[str, str] = {
    "usa": "united states",
    "united states of america": "united states",
    "korea republic": "south korea",
    "south korea": "south korea",
    "ir iran": "iran",
    "iran": "iran",
    "czechia": "czech",
    "czech republic": "czech",
    "bosnia and herzegovina": "bosnia",
    "bosnia-herzegovina": "bosnia",
    "cote d'ivoire": "ivory coast",
    "ivory coast": "ivory coast",
    "turkiye": "turkey",
    "turkey": "turkey",
    "cabo verde": "cape verde",
    "cape verde": "cape verde",
}

_STOP = {
    "fc", "ec", "sc", "cr", "ca", "cd", "afc", "cf", "ac", "as", "ss", "club",
    "clube", "de", "do", "da", "e", "the", "if", "fk", "sv", "and", "of",
}

# Geographic / generic modifiers that must NOT, on their own, make two names
# match — "South Korea" and "South Africa" share only "south". A match needs a
# discriminating token, or exact (aliased) equality.
_WEAK = {
    "south", "north", "east", "west", "new", "saudi", "republic", "united",
    "states", "central", "city", "town", "real", "san", "santa", "dr",
}


def is_configured() -> bool:
    return bool(settings.odds_api_key)


def sport_for_league(league_api_id: int) -> str | None:
    return LEAGUE_TO_SPORT.get(league_api_id)


def _fold(s: str) -> str:
    s = "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return _ALIASES.get(s.strip(), s.strip())


def _tokens(name: str) -> set[str]:
    folded = _fold(name)
    folded = _ALIASES.get(folded, folded)
    return {t for t in folded.replace("-", " ").split() if t and t not in _STOP}


def _name_match(a: str, b: str) -> bool:
    # Exact (aliased, accent-folded) equality first — handles "USA" ↔
    # "United States" and any name whose only tokens are weak modifiers.
    if _fold(a) == _fold(b):
        return True
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    # A match needs at least one *discriminating* shared token, so "South
    # Korea" never matches "South Africa" on "south" alone.
    if (ta & tb) - _WEAK:
        return True
    strong_a, strong_b = ta - _WEAK, tb - _WEAK
    for x in strong_a:
        for y in strong_b:
            if len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x)):
                return True
    return False


async def _fetch_sport(client: httpx.AsyncClient, sport_key: str) -> list[dict]:
    now = time.monotonic()
    hit = _cache.get(sport_key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    r = await client.get(
        f"{settings.odds_api_base_url}/sports/{sport_key}/odds",
        params={
            "apiKey": settings.odds_api_key,
            "regions": _REGIONS,
            "markets": _MARKETS,
            "oddsFormat": "decimal",
        },
    )
    if r.status_code in (401, 422):
        # Sport out of season / not offered right now — cache empty briefly so
        # we don't keep spending credits on it.
        _cache[sport_key] = (now, [])
        return []
    r.raise_for_status()
    events = r.json()
    remaining = r.headers.get("x-requests-remaining")
    if remaining is not None:
        logger.info("the-odds-api: %s credits remaining after %s", remaining, sport_key)
    _cache[sport_key] = (now, events)
    return events


def _best_h2h(event: dict, outcome_pred) -> tuple[float, str] | None:
    best: tuple[float, str] | None = None
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != "h2h":
                continue
            for o in mkt.get("outcomes", []):
                if outcome_pred(o) and (best is None or o["price"] > best[0]):
                    best = (o["price"], bm.get("title", bm["key"]))
    return best


def _best_total(event: dict, side: str, line: float) -> tuple[float, str] | None:
    best: tuple[float, str] | None = None
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != "totals":
                continue
            for o in mkt.get("outcomes", []):
                if o.get("name", "").lower() == side and abs(o.get("point", -99) - line) < 0.01:
                    if best is None or o["price"] > best[0]:
                        best = (o["price"], bm.get("title", bm["key"]))
    return best


def _best_named(event: dict, market_key: str, name_pred) -> tuple[float, str] | None:
    best: tuple[float, str] | None = None
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != market_key:
                continue
            for o in mkt.get("outcomes", []):
                if name_pred(o.get("name", "")) and (best is None or o["price"] > best[0]):
                    best = (o["price"], bm.get("title", bm["key"]))
    return best


def _market_resolvers(home: str, away: str) -> dict:
    """Map our market keys to a function that extracts (best_price, book)."""
    def dc(*needles):
        ns = [n.lower() for n in needles]
        return lambda nm: all(x in nm.lower() for x in ns)

    return {
        "home_win": lambda e: _best_h2h(e, lambda o: _name_match(o["name"], home)),
        "away_win": lambda e: _best_h2h(e, lambda o: _name_match(o["name"], away)),
        "draw":     lambda e: _best_h2h(e, lambda o: o["name"].lower() == "draw"),
        "over_05":  lambda e: _best_total(e, "over", 0.5),
        "over_15":  lambda e: _best_total(e, "over", 1.5),
        "over_25":  lambda e: _best_total(e, "over", 2.5),
        "over_35":  lambda e: _best_total(e, "over", 3.5),
        "over_45":  lambda e: _best_total(e, "over", 4.5),
        "under_05": lambda e: _best_total(e, "under", 0.5),
        "under_15": lambda e: _best_total(e, "under", 1.5),
        "under_25": lambda e: _best_total(e, "under", 2.5),
        "under_35": lambda e: _best_total(e, "under", 3.5),
        "under_45": lambda e: _best_total(e, "under", 4.5),
        "btts_yes": lambda e: _best_named(e, "btts", dc("yes")),
        "btts_no":  lambda e: _best_named(e, "btts", dc("no")),
        # the-odds-api double_chance outcome names are like "Home/Draw".
        "home_or_draw": lambda e: _best_named(e, "double_chance", lambda nm: _dc_match(nm, home, away, {"home", "draw"})),
        "away_or_draw": lambda e: _best_named(e, "double_chance", lambda nm: _dc_match(nm, home, away, {"away", "draw"})),
        "home_or_away": lambda e: _best_named(e, "double_chance", lambda nm: _dc_match(nm, home, away, {"home", "away"})),
    }


def _dc_match(outcome_name: str, home: str, away: str, want: set[str]) -> bool:
    """double_chance outcomes name the two covered results, e.g. 'Home/Draw' or
    '<HomeTeam>/Draw'. Resolve each side and check the covered set matches."""
    parts = [p.strip() for p in outcome_name.replace(" or ", "/").split("/")]
    got: set[str] = set()
    for p in parts:
        pl = p.lower()
        if pl in ("draw", "x", "tie"):
            got.add("draw")
        elif pl in ("home", "1") or _name_match(p, home):
            got.add("home")
        elif pl in ("away", "2") or _name_match(p, away):
            got.add("away")
    return got == want


def _find_event(events: list[dict], home: str, away: str) -> dict | None:
    for e in events:
        eh, ea = e.get("home_team", ""), e.get("away_team", "")
        # Accept either orientation — we resolve outcomes by team name anyway.
        if (_name_match(eh, home) and _name_match(ea, away)) or \
           (_name_match(eh, away) and _name_match(ea, home)):
            return e
    return None


async def fetch_market_odds(
    league_api_id: int, home_name: str, away_name: str, wanted_keys: list[str],
) -> dict | None:
    """Best real bookmaker odds for the requested market keys of one matchup.

    Returns {"event": {...meta}, "odds": {key: {"odds": float, "bookmaker": str}}}
    or None when not configured / no matching event was found.
    """
    if not is_configured():
        return None
    sport = sport_for_league(league_api_id)
    if not sport:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            events = await _fetch_sport(client, sport)
    except httpx.HTTPError as exc:
        logger.warning("the-odds-api fetch failed for %s: %s", sport, exc)
        return None

    event = _find_event(events, home_name, away_name)
    if not event:
        return None

    resolvers = _market_resolvers(event["home_team"], event["away_team"])
    odds: dict[str, dict] = {}
    for key in wanted_keys:
        fn = resolvers.get(key)
        if not fn:
            continue
        best = fn(event)
        if best:
            odds[key] = {"odds": round(best[0], 3), "bookmaker": best[1]}

    return {
        "event": {
            "home": event["home_team"],
            "away": event["away_team"],
            "commence_time": event.get("commence_time"),
            "bookmaker_count": len(event.get("bookmakers", [])),
        },
        "odds": odds,
    }
