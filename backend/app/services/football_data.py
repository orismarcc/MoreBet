"""
HTTP client for football-data.org (v4).

This is the PRIMARY data provider. Its free tier (TIER_ONE) covers all eight
MoreBet leagues *with the current season* — which the previous provider
(API-Football free) did not, leaving the app stuck on an old season.

Auth is via the `X-Auth-Token` header. Free tier allows ~10 requests/minute.
"""
import asyncio
import json
import logging
import time
from datetime import date, timedelta

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Free tier limit is 10 req/min — leave generous headroom so concurrent
# refreshes don't trip the limiter.
_MAX_RETRIES = 4
_BASE_BACKOFF = 2.0   # seconds; doubles each retry
# Cap each retry sleep: the provider sends Retry-After: 60 when the minute
# quota is gone, and honouring it verbatim makes our own request outlive the
# frontend's timeout — the user just sees "dados indisponíveis". Failing fast
# (and serving from cache, below) is the better trade.
_MAX_RETRY_SLEEP = 6.0


async def _get_with_retry(
    client: httpx.AsyncClient, url: str, *, params: dict | None = None
) -> dict:
    """GET wrapper that retries on 429 / 5xx with capped exponential backoff."""
    for attempt in range(_MAX_RETRIES):
        r = await client.get(url, headers=_headers(), params=params or {})
        if r.status_code < 400:
            return r.json()
        # Retry on rate-limit or server errors.
        if r.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
            wait = min(
                float(r.headers.get("Retry-After", _BASE_BACKOFF * (2 ** attempt))),
                _MAX_RETRY_SLEEP,
            )
            logger.warning(
                "football-data.org %s on %s — retrying in %.1fs (attempt %d/%d)",
                r.status_code, url, wait, attempt + 1, _MAX_RETRIES,
            )
            await asyncio.sleep(wait)
            continue
        r.raise_for_status()
    # Unreachable — raise_for_status above always throws on the last failed attempt.
    raise RuntimeError(f"unreachable: exhausted retries for {url}")


# ── Small in-process TTL cache ───────────────────────────────────────────────
# Team-level reads (recent form, upcoming, head-to-head) are hammered by the UI
# but barely change within minutes. Caching them keeps bursts of user clicks
# well inside the 10 req/min budget — this was the root cause of intermittent
# "dados indisponíveis" on the Times page.
_TTL_DEFAULT = 600.0          # 10 minutes
_TTL_TEAM = 3 * 3600.0        # finished/upcoming per-team windows
_TTL_LEAGUE_FIXTURES = 900.0  # league schedule windows (Jogos page fan-out)
_response_cache: dict[str, tuple[float, dict]] = {}


async def _cached_get(
    client: httpx.AsyncClient, url: str, *, params: dict | None = None,
    ttl: float = _TTL_DEFAULT,
) -> dict:
    key = url + "|" + json.dumps(params or {}, sort_keys=True)
    hit = _response_cache.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        data = await _get_with_retry(client, url, params=params)
    except httpx.HTTPError:
        # Provider unavailable — serve stale data if we have any, else re-raise.
        if hit:
            logger.warning("serving stale cache for %s (provider unavailable)", url)
            return hit[1]
        raise
    _response_cache[key] = (now, data)
    if len(_response_cache) > 500:  # bounded memory
        oldest = sorted(_response_cache.items(), key=lambda kv: kv[1][0])[:100]
        for k, _ in oldest:
            _response_cache.pop(k, None)
    return data

# Stable API-Football numeric id (kept as the DB / frontend key) -> the
# football-data.org competition code. Keeping the original ids means existing
# league rows, the frontend league list and the /leagues/{id}/refresh URLs all
# keep working unchanged after the provider switch.
FD_LEAGUES: dict[int, tuple[str, str, str]] = {
    1:   ("WC",  "Copa do Mundo FIFA",  "World"),
    39:  ("PL",  "Premier League",      "England"),
    140: ("PD",  "La Liga",             "Spain"),
    135: ("SA",  "Serie A",             "Italy"),
    78:  ("BL1", "Bundesliga",          "Germany"),
    61:  ("FL1", "Ligue 1",             "France"),
    71:  ("BSA", "Brasileirão Série A", "Brazil"),
    94:  ("PPL", "Primeira Liga",       "Portugal"),
    88:  ("DED", "Eredivisie",          "Netherlands"),
}

# Knockout tournaments on neutral venues: home/away splits are meaningless, so
# team strength is computed over ALL matches and mirrored into both splits.
# These also get a previous-edition fallback while the current edition has no
# finished matches yet (e.g. World Cup group stage about to kick off).
TOURNAMENT_LEAGUES: set[int] = {1}

# Mirrors the old api_football.SUPPORTED_LEAGUES shape {id: (name, country)} so
# the rest of the app keeps importing one stable name.
SUPPORTED_LEAGUES: dict[int, tuple[str, str]] = {
    lid: (name, country) for lid, (_code, name, country) in FD_LEAGUES.items()
}

# How many recent matches define a team's "current form".
FORM_WINDOW = 30
# Exponential decay per match: the newest game weighs 1.0, the one before
# 0.95, then 0.95², … With a 30-game window the effective sample is ~16 games,
# so recent form dominates without throwing away the season's baseline.
FORM_DECAY = 0.95
_FINISHED = "FINISHED"


def _decay_weights(n: int, decay: float = FORM_DECAY) -> list[float]:
    """Weights for a chronologically-sorted (oldest→newest) list of n matches:
    newest gets 1.0, each step back multiplies by `decay`."""
    return [decay ** (n - 1 - i) for i in range(n)]


def _weighted_avg(pairs: list[tuple[float, float]]) -> float:
    """Mean of (value, weight) pairs; 0.0 when there is no weight."""
    total_w = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total_w if total_w > 0 else 0.0


def _headers() -> dict[str, str]:
    return {"X-Auth-Token": settings.football_data_key}


def _code(league_id: int) -> str:
    if league_id not in FD_LEAGUES:
        raise ValueError(f"League {league_id} is not supported")
    return FD_LEAGUES[league_id][0]


async def _get_matches(
    client: httpx.AsyncClient, code: str, *, season: int | None = None,
    date_from: str | None = None, date_to: str | None = None,
    ttl: float | None = None,
) -> dict:
    params: dict[str, str | int] = {}
    if season is not None:
        params["season"] = season
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to
    url = f"{settings.football_data_base_url}/competitions/{code}/matches"
    if ttl is not None:
        return await _cached_get(client, url, params=params, ttl=ttl)
    return await _get_with_retry(client, url, params=params)


def _team_form_averages(matches: list[dict], last_n: int) -> dict:
    """From a chronologically-sorted (oldest→newest) list of a team's matches,
    take the most recent `last_n` and compute exponentially-decayed home/away
    scoring averages — recent games weigh more than old ones."""
    recent = matches[-last_n:]
    weights = _decay_weights(len(recent))
    home = [(m, w) for m, w in zip(recent, weights) if m["is_home"]]
    away = [(m, w) for m, w in zip(recent, weights) if not m["is_home"]]

    def _avg(games: list[tuple[dict, float]], key: str) -> float:
        return _weighted_avg([(g[key], w) for g, w in games])

    return {
        "home_played": len(home),
        "home_goals_scored": _avg(home, "scored"),
        "home_goals_conceded": _avg(home, "conceded"),
        "away_played": len(away),
        "away_goals_scored": _avg(away, "scored"),
        "away_goals_conceded": _avg(away, "conceded"),
    }


def _team_neutral_averages(matches: list[dict], last_n: int) -> dict:
    """Tournament variant: venues are neutral, so compute one combined
    (decay-weighted) scored/conceded average and mirror it into both splits."""
    recent = matches[-last_n:]
    weights = _decay_weights(len(recent))
    n = len(recent)
    scored = _weighted_avg([(m["scored"], w) for m, w in zip(recent, weights)])
    conceded = _weighted_avg([(m["conceded"], w) for m, w in zip(recent, weights)])
    return {
        "home_played": n,
        "home_goals_scored": scored,
        "home_goals_conceded": conceded,
        "away_played": n,
        "away_goals_scored": scored,
        "away_goals_conceded": conceded,
    }


async def _bootstrap_tournament_from_internationals(
    client: httpx.AsyncClient, league_id: int, name: str, country: str,
    emblem: str | None,
) -> tuple[dict, list[dict]] | None:
    """Pre-tournament seeding: build each participant's neutral-venue scoring
    averages from their last internationals (friendlies + qualifiers via
    ESPN), mirrored into both home/away splits. Nations we can't map get the
    field average. Returns None when nothing could be built."""
    from app.services import espn as espn_svc

    participants = await fetch_wc_participants(client)
    if not participants:
        return None
    try:
        espn_teams = await espn_svc.fetch_wc_espn_team_map(client)
    except httpx.HTTPError:
        return None

    # Lower concurrency than other fan-outs: ESPN rate-limits bursts and a
    # collapsed seeding leaves every nation on the field-average default.
    sem = asyncio.Semaphore(4)

    async def _averages(p: dict) -> tuple[dict, tuple[float, float, int] | None]:
        match = next(
            (t for t in espn_teams if espn_svc._teams_match(p["name"], t["name"])),
            None,
        )
        if not match:
            return p, None
        async with sem:
            try:
                results = await espn_svc.fetch_team_intl_results(
                    client, match["espn_id"], limit=12
                )
            except httpx.HTTPError:
                return p, None
        if not results:
            return p, None
        n = len(results)
        gf = sum(r["goals_for"] for r in results) / n
        ga = sum(r["goals_against"] for r in results) / n
        return p, (gf, ga, n)

    per_team = await asyncio.gather(*(_averages(p) for p in participants))
    with_data = [avg for _, avg in per_team if avg is not None]
    # Partial success still beats the all-default fallback: teams with data get
    # real strength, the rest get the field average computed from those.
    if len(with_data) < 8:
        return None  # genuinely too sparse to be meaningful
    field_gf = sum(a[0] for a in with_data) / len(with_data)
    field_ga = sum(a[1] for a in with_data) / len(with_data)

    teams_list: list[dict] = []
    for p, avg in per_team:
        gf, ga, n = avg if avg is not None else (field_gf, field_ga, 0)
        teams_list.append({
            "api_id": p["api_id"],
            "name": p["name"],
            "short_name": p["short_name"],
            "logo_url": p["crest"],
            "home_played": n,
            "home_goals_scored": gf,
            "home_goals_conceded": ga,
            "away_played": n,
            "away_goals_scored": gf,
            "away_goals_conceded": ga,
        })

    logger.info(
        "tournament %s seeded from internationals: %d/%d nations with data",
        name, len(with_data), len(participants),
    )
    league_dict = {
        "api_id": league_id,
        "name": name,
        "country": country,
        "season": date.today().year,
        "logo_url": emblem,
    }
    return league_dict, teams_list


async def fetch_league_with_form(
    client: httpx.AsyncClient, league_id: int, last_n: int = FORM_WINDOW
) -> tuple[dict, list[dict]]:
    """Single source of truth for ingestion.

    Pulls the current season's matches (plus the previous season so a team's
    last-`last_n` window can cross the season boundary) and computes each team's
    home/away averages from genuine recent form. Returns (league_dict,
    teams_list) using the same shapes the ORM/ingestion expect.
    """
    code, name, country = FD_LEAGUES[league_id]

    current = await _get_matches(client, code)
    season_year = current.get("filters", {}).get("season")
    comp = current.get("competition", {})
    cur_matches = current.get("matches", [])

    # Previous season (best-effort) to extend the form window across the boundary.
    prev_matches: list[dict] = []
    if season_year is not None:
        try:
            prev = await _get_matches(client, code, season=int(season_year) - 1)
            prev_matches = prev.get("matches", [])
        except httpx.HTTPError:
            pass

    def _finished(ms: list[dict]) -> list[dict]:
        return [
            m for m in ms
            if m["status"] == _FINISHED
            and m["score"]["fullTime"]["home"] is not None
            and m["score"]["fullTime"]["away"] is not None
        ]

    is_tournament = league_id in TOURNAMENT_LEAGUES

    cur_finished = _finished(cur_matches)
    prev_finished = _finished(prev_matches)

    if is_tournament:
        # Tournaments: each nation's strength comes from its last ~12
        # internationals (friendlies + qualifiers + the tournament itself, via
        # ESPN). This both makes the OPENING matches analysable (the primary
        # provider has zero national-team history) and gives a far richer
        # sample than 1-3 group games mid-tournament. Falls through to the
        # neutral in-tournament path only if the seeding source fails.
        try:
            seeded = await _bootstrap_tournament_from_internationals(
                client, league_id, name, country, comp.get("emblem"),
            )
        except Exception as exc:  # seeding source down → in-tournament data
            logger.warning("tournament seeding failed (%s) — using in-tournament data", exc)
            seeded = None
        if seeded is not None:
            return seeded

    if not cur_finished and not (is_tournament and prev_finished):
        raise ValueError(
            f"League {league_id} ({code}): no finished matches in the current "
            f"season {season_year} yet"
        )

    # Build per-team chronological histories from current + previous seasons.
    all_finished = prev_finished + cur_finished
    all_finished.sort(key=lambda m: m["utcDate"])

    teams: dict[int, dict] = {}
    histories: dict[int, list[dict]] = {}
    # Tournaments: register team info from EVERY current-edition match (any
    # status) so participants without a finished match yet still get name/crest.
    info_source = all_finished + (cur_matches if is_tournament else [])
    for m in info_source:
        for side in ("homeTeam", "awayTeam"):
            t = m[side]
            # Knockout placeholders ("Winner of group A") carry null ids.
            if t.get("id") and t.get("name"):
                teams.setdefault(t["id"], t)
    for m in all_finished:
        ft = m["score"]["fullTime"]
        gh, ga = ft["home"], ft["away"]
        h, a = m["homeTeam"], m["awayTeam"]
        histories.setdefault(h["id"], []).append({"is_home": True,  "scored": gh, "conceded": ga})
        histories.setdefault(a["id"], []).append({"is_home": False, "scored": ga, "conceded": gh})

    if is_tournament:
        # Every team drawn into the current edition is a genuine participant —
        # use the full schedule (group games exist before any kick-off).
        # Skip knockout placeholders (null id) and anything without team info.
        current_team_ids = {
            m[side]["id"]
            for m in cur_matches for side in ("homeTeam", "awayTeam")
            if m[side].get("id") and m[side]["id"] in teams
        }
    else:
        # Genuine participants of the CURRENT season only. Counting current-season
        # matches excludes any intruder and ignores prev-season-only teams.
        season_counts: dict[int, int] = {}
        for m in cur_finished:
            for side in ("homeTeam", "awayTeam"):
                tid = m[side]["id"]
                season_counts[tid] = season_counts.get(tid, 0) + 1
        threshold = max(season_counts.values()) * 0.5
        current_team_ids = {tid for tid, n in season_counts.items() if n >= threshold}

    # Tournament fallback for teams with no recorded match in this competition
    # (e.g. a World Cup debutant): use the field-wide average so λ stays sane
    # instead of collapsing to zero.
    with_history = [tid for tid in current_team_ids if histories.get(tid)]
    fallback: dict | None = None
    if is_tournament and with_history:
        per_team = [_team_neutral_averages(histories[tid], last_n) for tid in with_history]
        k = len(per_team)
        fallback = {
            "home_played": 0,
            "home_goals_scored": sum(t["home_goals_scored"] for t in per_team) / k,
            "home_goals_conceded": sum(t["home_goals_conceded"] for t in per_team) / k,
            "away_played": 0,
            "away_goals_scored": sum(t["away_goals_scored"] for t in per_team) / k,
            "away_goals_conceded": sum(t["away_goals_conceded"] for t in per_team) / k,
        }

    teams_list: list[dict] = []
    for tid in current_team_ids:
        info = teams[tid]
        history = histories.get(tid, [])
        if history:
            averages = (
                _team_neutral_averages(history, last_n)
                if is_tournament
                else _team_form_averages(history, last_n)
            )
        elif fallback is not None:
            averages = dict(fallback)
        else:
            continue  # no usable data for this team
        teams_list.append({
            "api_id": tid,
            "name": info["name"],
            "short_name": info.get("tla") or info.get("shortName"),
            "logo_url": info.get("crest"),
            **averages,
        })

    league_dict = {
        "api_id": league_id,           # keep the stable numeric key
        "name": name,
        "country": country,
        "season": int(season_year) if season_year is not None else date.today().year,
        "logo_url": comp.get("emblem"),
    }
    return league_dict, teams_list


async def fetch_league_finished_matches(
    client: httpx.AsyncClient, league_id: int
) -> tuple[dict, list[dict]]:
    """All finished matches of a league (previous + current season), oldest
    first — the input for walk-forward backtesting. Returns (league_info,
    matches) where each match is {utc_date, home_id, away_id, home_goals,
    away_goals}. Cached for 1h: backtests re-run cheaply."""
    code, name, country = FD_LEAGUES[league_id]
    current = await _get_matches(client, code, ttl=3600.0)
    season_year = current.get("filters", {}).get("season")
    all_raw = list(current.get("matches", []))
    if season_year is not None:
        try:
            prev = await _get_matches(client, code, season=int(season_year) - 1, ttl=3600.0)
            all_raw = list(prev.get("matches", [])) + all_raw
        except httpx.HTTPError:
            pass

    finished = [
        m for m in all_raw
        if m["status"] == _FINISHED
        and m["score"]["fullTime"]["home"] is not None
        and m["score"]["fullTime"]["away"] is not None
        and m["homeTeam"].get("id") and m["awayTeam"].get("id")
    ]
    finished.sort(key=lambda m: m["utcDate"])
    matches = [
        {
            "utc_date": m["utcDate"],
            "home_id": m["homeTeam"]["id"],
            "away_id": m["awayTeam"]["id"],
            "home_goals": m["score"]["fullTime"]["home"],
            "away_goals": m["score"]["fullTime"]["away"],
        }
        for m in finished
    ]
    league_info = {"api_id": league_id, "name": name, "country": country}
    return league_info, matches


# The per-team matches endpoint 403s on the free tier whenever the team has
# matches in a restricted competition (e.g. Werder/Leipzig in the DFB-Pokal) —
# no filter combination unlocks it. Once we see a 403 we remember it and use
# the per-competition fallback below, which always works.
_team_endpoint_blocked: set[int] = set()
_team_league_code: dict[int, str] = {}  # learned api_id -> competition code


async def _league_season_matches(client: httpx.AsyncClient, code: str) -> list[dict]:
    """All matches (any status) of a competition's current season — one cached
    call shared by every team of that league."""
    data = await _get_matches(client, code, ttl=_TTL_TEAM)
    return data.get("matches", [])


async def _locate_team_league(
    client: httpx.AsyncClient, team_api_id: int, league_hint: str | None
) -> str | None:
    """Find which of our competitions a team plays in (memoised)."""
    if team_api_id in _team_league_code:
        return _team_league_code[team_api_id]
    codes: list[str] = []
    if league_hint:
        codes.append(league_hint)
    codes += [c for c, _n, _co in FD_LEAGUES.values() if c not in codes]
    for code in codes:
        try:
            ms = await _league_season_matches(client, code)
        except httpx.HTTPError:
            continue
        for m in ms:
            if team_api_id in (m["homeTeam"].get("id"), m["awayTeam"].get("id")):
                _team_league_code[team_api_id] = code
                return code
    return None


def _finished_only(ms: list[dict]) -> list[dict]:
    out = [
        m for m in ms
        if m["status"] == _FINISHED
        and m["score"]["fullTime"]["home"] is not None
        and m["score"]["fullTime"]["away"] is not None
    ]
    out.sort(key=lambda m: m["utcDate"], reverse=True)
    return out


async def _team_finished_matches(
    client: httpx.AsyncClient, team_api_id: int, league_hint: str | None = None
) -> list[dict]:
    """A team's recent finished matches, newest first.

    Primary: the per-team endpoint (cross-competition, up to 100 games).
    Fallback on 403: the team's league season matches filtered locally —
    league-only, but available for every team. Both paths are cached and
    shared by recent-form, summaries AND head-to-head, so a full analysis
    costs at most 2 provider calls cold and zero warm."""
    if team_api_id not in _team_endpoint_blocked:
        try:
            data = await _cached_get(
                client,
                f"{settings.football_data_base_url}/teams/{team_api_id}/matches",
                params={"status": "FINISHED", "limit": 100},
                ttl=_TTL_TEAM,
            )
            return _finished_only(data.get("matches", []))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise
            _team_endpoint_blocked.add(team_api_id)
            logger.info(
                "team %s matches endpoint restricted — using league fallback",
                team_api_id,
            )

    code = await _locate_team_league(client, team_api_id, league_hint)
    if code is None:
        return []
    ms = await _league_season_matches(client, code)
    mine = [
        m for m in ms
        if team_api_id in (m["homeTeam"].get("id"), m["awayTeam"].get("id"))
    ]
    return _finished_only(mine)


async def fetch_team_upcoming_matches(
    client: httpx.AsyncClient, team_api_id: int, limit: int = 5,
    league_hint: str | None = None,
) -> list[dict]:
    """Next scheduled matches for a team within the coming 60 days.
    Same 403 fallback as finished matches: league schedule filtered locally."""
    today = date.today()
    candidates: list[dict] = []
    if team_api_id not in _team_endpoint_blocked:
        try:
            data = await _cached_get(
                client,
                f"{settings.football_data_base_url}/teams/{team_api_id}/matches",
                params={
                    "dateFrom": today.isoformat(),
                    "dateTo": (today + timedelta(days=60)).isoformat(),
                    "limit": 20,
                },
                ttl=_TTL_TEAM,
            )
            candidates = data.get("matches", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise
            _team_endpoint_blocked.add(team_api_id)
    if not candidates and team_api_id in _team_endpoint_blocked:
        code = await _locate_team_league(client, team_api_id, league_hint)
        if code is not None:
            ms = await _league_season_matches(client, code)
            candidates = [
                m for m in ms
                if team_api_id in (m["homeTeam"].get("id"), m["awayTeam"].get("id"))
                and m["utcDate"][:10] >= today.isoformat()
            ]

    upcoming: list[dict] = []
    for m in sorted(candidates, key=lambda x: x["utcDate"]):
        if m["status"] not in ("SCHEDULED", "TIMED"):
            continue
        is_home = m["homeTeam"]["id"] == team_api_id
        opp = m["awayTeam"] if is_home else m["homeTeam"]
        comp = m.get("competition", {})
        upcoming.append({
            "match_id": m["id"],
            "date": m["utcDate"],
            "competition": comp.get("name"),
            "competition_emblem": comp.get("emblem"),
            "is_home": is_home,
            "opponent": opp["name"],
            "opponent_api_id": opp.get("id"),
            "opponent_crest": opp.get("crest"),
        })
        if len(upcoming) >= limit:
            break
    return upcoming


def build_form_summary(matches: list[dict]) -> dict:
    """Aggregate stats from a list of RecentMatch-shaped dicts (any source)."""
    wins = sum(1 for m in matches if m["result"] == "W")
    draws = sum(1 for m in matches if m["result"] == "D")
    losses = sum(1 for m in matches if m["result"] == "L")
    gf = sum(m["goals_for"] for m in matches)
    ga = sum(m["goals_against"] for m in matches)
    over_15 = sum(1 for m in matches if m["goals_for"] + m["goals_against"] > 1.5)
    over_25 = sum(1 for m in matches if m["goals_for"] + m["goals_against"] > 2.5)
    btts = sum(1 for m in matches if m["goals_for"] > 0 and m["goals_against"] > 0)
    n = len(matches) or 1
    return {
        "played": len(matches),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": gf,
        "goals_against": ga,
        "avg_goals_for": round(gf / n, 2),
        "avg_goals_against": round(ga / n, 2),
        "over_15_pct": round(over_15 / n * 100),
        "over_25_pct": round(over_25 / n * 100),
        "btts_pct": round(btts / n * 100),
        "clean_sheets": sum(1 for m in matches if m["goals_against"] == 0),
        "failed_to_score": sum(1 for m in matches if m["goals_for"] == 0),
        "ppg": round((wins * 3 + draws) / n, 2),
        # Oldest→newest so the UI can render a left-to-right form streak
        "form": "".join(m["result"] for m in reversed(matches)),
    }


async def fetch_standings(client: httpx.AsyncClient, league_id: int) -> list[dict]:
    """League table(s). One TOTAL table for leagues; several group tables for
    tournaments (World Cup). Returns [{group, rows:[...]}] cached for 15 min."""
    code = _code(league_id)
    data = await _cached_get(
        client,
        f"{settings.football_data_base_url}/competitions/{code}/standings",
        ttl=_TTL_LEAGUE_FIXTURES,
    )
    groups: list[dict] = []
    for st in data.get("standings", []):
        if st.get("type") != "TOTAL":
            continue
        rows = []
        for r in st.get("table", []):
            t = r.get("team", {})
            rows.append({
                "position": r.get("position"),
                "team_api_id": t.get("id"),
                "team_name": t.get("name"),
                "team_crest": t.get("crest"),
                "played": r.get("playedGames"),
                "won": r.get("won"),
                "draw": r.get("draw"),
                "lost": r.get("lost"),
                "goals_for": r.get("goalsFor"),
                "goals_against": r.get("goalsAgainst"),
                "goal_difference": r.get("goalDifference"),
                "points": r.get("points"),
            })
        if rows:
            groups.append({"group": st.get("group"), "rows": rows})
    return groups


async def fetch_team_form(
    client: httpx.AsyncClient, team_api_id: int, team_name: str | None,
    limit: int = 6, league_hint: str | None = None,
) -> dict:
    """Recent form with an internationals fallback for national teams — the club
    provider has no history for them, so World Cup sides would otherwise look
    formless. Falls back to ESPN friendlies/qualifiers keyed by name."""
    payload = await fetch_team_recent_matches(client, team_api_id, limit, league_hint)
    if payload["summary"]["played"] == 0 and team_name:
        from app.services import espn as espn_svc
        try:
            intl = await espn_svc.recent_internationals_by_name(client, team_name, limit)
        except Exception:
            intl = None
        if intl:
            return {"summary": build_form_summary(intl), "matches": intl}
    return payload


async def fetch_team_recent_matches(
    client: httpx.AsyncClient, team_api_id: int, limit: int = 6,
    league_hint: str | None = None,
) -> dict:
    """Recent finished matches for a team (across all competitions) plus an
    aggregated form summary. `team_api_id` is the football-data.org team id."""
    raw = (await _team_finished_matches(client, team_api_id, league_hint))[:limit]

    matches: list[dict] = []
    for m in raw:
        is_home = m["homeTeam"]["id"] == team_api_id
        opp = m["awayTeam"] if is_home else m["homeTeam"]
        ft = m["score"]["fullTime"]
        my_goals = ft["home"] if is_home else ft["away"]
        opp_goals = ft["away"] if is_home else ft["home"]
        result = "W" if my_goals > opp_goals else ("D" if my_goals == opp_goals else "L")

        comp = m.get("competition", {})
        matches.append({
            "match_id": m["id"],
            "date": m["utcDate"],
            "competition": comp.get("name"),
            "competition_code": comp.get("code"),
            "competition_emblem": comp.get("emblem"),
            "is_home": is_home,
            "opponent": opp["name"],
            "opponent_short": opp.get("tla") or opp.get("shortName"),
            "opponent_crest": opp.get("crest"),
            "goals_for": my_goals,
            "goals_against": opp_goals,
            "result": result,
        })

    return {"summary": build_form_summary(matches), "matches": matches}


async def fetch_upcoming_fixtures(
    client: httpx.AsyncClient, league_id: int, days: int = 7
) -> list[dict]:
    """Scheduled (not-yet-played) matches in the next `days` days for a league."""
    code = _code(league_id)
    name, country = SUPPORTED_LEAGUES[league_id]
    today = date.today()
    to = today + timedelta(days=days)
    data = await _get_matches(
        client, code, date_from=today.isoformat(), date_to=to.isoformat(),
        ttl=_TTL_LEAGUE_FIXTURES,
    )
    comp = data.get("competition", {})
    league_logo = comp.get("emblem")

    fixtures: list[dict] = []
    for m in data.get("matches", []):
        if m["status"] not in ("SCHEDULED", "TIMED"):
            continue
        h, a = m["homeTeam"], m["awayTeam"]
        md = m.get("matchday")
        fixtures.append({
            "fixture_id": m["id"],
            "match_date": m["utcDate"],
            "status": m["status"],
            "venue": None,  # football-data.org free tier has no venue
            "league_id": league_id,
            "league_name": name,
            "league_country": country,
            "league_logo": league_logo,
            "round": f"Matchday {md}" if md else None,
            "home_team_api_id": h["id"],
            "home_team_name": h["name"],
            "home_team_logo": h.get("crest"),
            "away_team_api_id": a["id"],
            "away_team_name": a["name"],
            "away_team_logo": a.get("crest"),
        })
    return sorted(fixtures, key=lambda x: x["match_date"])


async def fetch_head_to_head(
    client: httpx.AsyncClient,
    team_a_api_id: int,
    team_b_api_id: int,
    limit: int = 3,
    league_hint: str | None = None,
) -> list[dict]:
    """Last direct meetings between two teams (within competitions the free
    tier exposes). Reuses the shared cached finished-matches window of team A."""
    raw = await _team_finished_matches(client, team_a_api_id, league_hint)
    meetings: list[dict] = []
    for m in raw:
        h, a = m["homeTeam"], m["awayTeam"]
        ids = {h.get("id"), a.get("id")}
        if team_b_api_id not in ids or team_a_api_id not in ids:
            continue
        ft = m["score"]["fullTime"]
        if ft["home"] is None or ft["away"] is None:
            continue
        comp = m.get("competition", {})
        meetings.append({
            "match_id": m["id"],
            "date": m["utcDate"],
            "competition": comp.get("name"),
            "competition_code": comp.get("code"),
            "home_api_id": h["id"],
            "home_name": h["name"],
            "home_crest": h.get("crest"),
            "away_api_id": a["id"],
            "away_name": a["name"],
            "away_crest": a.get("crest"),
            "home_goals": ft["home"],
            "away_goals": ft["away"],
        })
        if len(meetings) >= limit:
            break
    return meetings


# ── World Cup participants (national teams) ─────────────────────────────────
# National teams have no row in our DB while the tournament has no finished
# matches, but they DO exist in the current edition's schedule. We extract them
# from the WC fixtures and cache the list in-process so the team-search
# endpoint doesn't burn an API call per keystroke.
_WC_CACHE_TTL = 6 * 3600.0
_wc_participants_cache: dict = {"ts": 0.0, "teams": []}


async def fetch_wc_participants(client: httpx.AsyncClient) -> list[dict]:
    """All national teams drawn into the current World Cup edition.
    Returns [{api_id, name, short_name, crest}], cached for 6h."""
    import time

    now = time.monotonic()
    if _wc_participants_cache["teams"] and now - _wc_participants_cache["ts"] < _WC_CACHE_TTL:
        return _wc_participants_cache["teams"]

    data = await _get_matches(client, "WC")
    seen: dict[int, dict] = {}
    for m in data.get("matches", []):
        for side in ("homeTeam", "awayTeam"):
            t = m[side]
            if t.get("id") and t.get("name") and t["id"] not in seen:
                seen[t["id"]] = {
                    "api_id": t["id"],
                    "name": t["name"],
                    "short_name": t.get("tla") or t.get("shortName"),
                    "crest": t.get("crest"),
                }
    teams = sorted(seen.values(), key=lambda t: t["name"])
    _wc_participants_cache["ts"] = now
    _wc_participants_cache["teams"] = teams
    return teams
