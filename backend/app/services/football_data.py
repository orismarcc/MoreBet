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
_TTL_DEFAULT = 600.0  # 10 minutes
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
_FINISHED = "FINISHED"


def _headers() -> dict[str, str]:
    return {"X-Auth-Token": settings.football_data_key}


def _code(league_id: int) -> str:
    if league_id not in FD_LEAGUES:
        raise ValueError(f"League {league_id} is not supported")
    return FD_LEAGUES[league_id][0]


async def _get_matches(
    client: httpx.AsyncClient, code: str, *, season: int | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> dict:
    params: dict[str, str | int] = {}
    if season is not None:
        params["season"] = season
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to
    return await _get_with_retry(
        client,
        f"{settings.football_data_base_url}/competitions/{code}/matches",
        params=params,
    )


def _team_form_averages(matches: list[dict], last_n: int) -> dict:
    """From a chronologically-sorted (oldest→newest) list of a team's matches,
    take the most recent `last_n` and compute home/away scoring averages."""
    recent = matches[-last_n:]
    home = [m for m in recent if m["is_home"]]
    away = [m for m in recent if not m["is_home"]]

    def _avg(games: list[dict], key: str) -> float:
        return sum(g[key] for g in games) / len(games) if games else 0.0

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
    scored/conceded average and mirror it into both home and away splits."""
    recent = matches[-last_n:]
    n = len(recent)
    scored = sum(m["scored"] for m in recent) / n if n else 0.0
    conceded = sum(m["conceded"] for m in recent) / n if n else 0.0
    return {
        "home_played": n,
        "home_goals_scored": scored,
        "home_goals_conceded": conceded,
        "away_played": n,
        "away_goals_scored": scored,
        "away_goals_conceded": conceded,
    }


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
        teams.setdefault(m["homeTeam"]["id"], m["homeTeam"])
        teams.setdefault(m["awayTeam"]["id"], m["awayTeam"])
    for m in all_finished:
        ft = m["score"]["fullTime"]
        gh, ga = ft["home"], ft["away"]
        h, a = m["homeTeam"], m["awayTeam"]
        histories.setdefault(h["id"], []).append({"is_home": True,  "scored": gh, "conceded": ga})
        histories.setdefault(a["id"], []).append({"is_home": False, "scored": ga, "conceded": gh})

    if is_tournament:
        # Every team drawn into the current edition is a genuine participant —
        # use the full schedule (group games exist before any kick-off).
        current_team_ids = {
            m[side]["id"] for m in cur_matches for side in ("homeTeam", "awayTeam")
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


async def fetch_team_upcoming_matches(
    client: httpx.AsyncClient, team_api_id: int, limit: int = 5
) -> list[dict]:
    """Next scheduled matches for a team within the coming 60 days."""
    today = date.today()
    data = await _cached_get(
        client,
        f"{settings.football_data_base_url}/teams/{team_api_id}/matches",
        params={
            "dateFrom": today.isoformat(),
            "dateTo": (today + timedelta(days=60)).isoformat(),
            "limit": 20,
        },
    )
    upcoming: list[dict] = []
    for m in sorted(data.get("matches", []), key=lambda x: x["utcDate"]):
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
            "opponent_crest": opp.get("crest"),
        })
        if len(upcoming) >= limit:
            break
    return upcoming


async def fetch_team_recent_matches(
    client: httpx.AsyncClient, team_api_id: int, limit: int = 6
) -> dict:
    """Recent finished matches for a team (across all competitions) plus an
    aggregated form summary. `team_api_id` is the football-data.org team id."""
    data = await _cached_get(
        client,
        f"{settings.football_data_base_url}/teams/{team_api_id}/matches",
        params={"status": "FINISHED", "limit": max(limit, 1)},
    )

    raw = [
        m for m in data.get("matches", [])
        if m["score"]["fullTime"]["home"] is not None
        and m["score"]["fullTime"]["away"] is not None
    ]
    # Most recent first
    raw.sort(key=lambda m: m["utcDate"], reverse=True)
    raw = raw[:limit]

    matches: list[dict] = []
    wins = draws = losses = gf = ga = 0
    over_15 = over_25 = btts = clean_sheets = failed_to_score = 0

    for m in raw:
        is_home = m["homeTeam"]["id"] == team_api_id
        opp = m["awayTeam"] if is_home else m["homeTeam"]
        ft = m["score"]["fullTime"]
        my_goals = ft["home"] if is_home else ft["away"]
        opp_goals = ft["away"] if is_home else ft["home"]

        if my_goals > opp_goals:
            result = "W"; wins += 1
        elif my_goals == opp_goals:
            result = "D"; draws += 1
        else:
            result = "L"; losses += 1

        gf += my_goals
        ga += opp_goals
        if my_goals + opp_goals > 1.5:
            over_15 += 1
        if my_goals + opp_goals > 2.5:
            over_25 += 1
        if my_goals > 0 and opp_goals > 0:
            btts += 1
        if opp_goals == 0:
            clean_sheets += 1
        if my_goals == 0:
            failed_to_score += 1

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

    n = len(matches) or 1
    summary = {
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
        "clean_sheets": clean_sheets,
        "failed_to_score": failed_to_score,
        "ppg": round((wins * 3 + draws) / n, 2),
        # Oldest→newest so the UI can render a left-to-right form streak
        "form": "".join(m["result"] for m in reversed(matches)),
    }
    return {"summary": summary, "matches": matches}


async def fetch_upcoming_fixtures(
    client: httpx.AsyncClient, league_id: int, days: int = 7
) -> list[dict]:
    """Scheduled (not-yet-played) matches in the next `days` days for a league."""
    code = _code(league_id)
    name, country = SUPPORTED_LEAGUES[league_id]
    today = date.today()
    to = today + timedelta(days=days)
    data = await _get_matches(
        client, code, date_from=today.isoformat(), date_to=to.isoformat()
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
) -> list[dict]:
    """Last direct meetings between two teams (within competitions the free
    tier exposes). One cached call: team A's finished matches filtered for B."""
    data = await _cached_get(
        client,
        f"{settings.football_data_base_url}/teams/{team_a_api_id}/matches",
        params={"status": "FINISHED", "limit": 100},
    )
    meetings: list[dict] = []
    for m in sorted(data.get("matches", []), key=lambda x: x["utcDate"], reverse=True):
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
            if t.get("id") and t["id"] not in seen:
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
