"""
Match statistics via ESPN's public site API.

The primary provider (football-data.org free tier) exposes no per-match
statistics — no possession, shots, corners or goal timeline. ESPN's public
JSON endpoints carry all of that for the leagues we cover, keyed by their own
event ids, so we locate the event by (league, date, team names) and then read
its summary. Best-effort by design: when a match can't be matched we return
found=False instead of failing the request.
"""
import json
import logging
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# football-data.org competition code -> ESPN league slug
COMP_TO_ESPN: dict[str, str] = {
    "BSA": "bra.1",
    "PL":  "eng.1",
    "PD":  "esp.1",
    "SA":  "ita.1",
    "BL1": "ger.1",
    "FL1": "fra.1",
    "PPL": "por.1",
    "DED": "ned.1",
    "WC":  "fifa.world",
    "CL":  "uefa.champions",
    "EL":  "uefa.europa",
    "CLI": "conmebol.libertadores",
    "ELC": "eng.2",
    "FAC": "eng.fa",
    "CDR": "esp.copa_del_rey",
    "DFB": "ger.dfb_pokal",
    "CIT": "ita.coppa_italia",
    "CDF": "fra.coupe_de_france",
}

# Which boxscore statistics we surface, in display order.
_STATS = [
    ("possessionPct",  "Posse de bola", "%"),
    ("totalShots",     "Finalizações",  ""),
    ("shotsOnTarget",  "Chutes ao gol", ""),
    ("wonCorners",     "Escanteios",    ""),
    ("foulsCommitted", "Faltas",        ""),
    ("yellowCards",    "Cartões amarelos", ""),
    ("redCards",       "Cartões vermelhos", ""),
    ("saves",          "Defesas do goleiro", ""),
]

_CACHE_TTL = 24 * 3600.0  # finished-match stats never change
_cache: dict[str, tuple[float, dict]] = {}


def _norm_tokens(name: str) -> set[str]:
    """Accent-folded significant tokens of a team name, for fuzzy matching."""
    folded = "".join(
        c for c in unicodedata.normalize("NFD", name.lower())
        if unicodedata.category(c) != "Mn"
    )
    stop = {
        "fc", "ec", "sc", "cr", "ca", "cd", "afc", "cf", "ac", "as", "ss",
        "club", "clube", "de", "do", "da", "e", "esporte", "futebol",
        "regatas", "the", "if", "fk", "sv", "vfb", "vfl", "tsg", "rb", "1",
    }
    return {t for t in folded.replace("-", " ").split() if t and t not in stop}


def _teams_match(a: str, b: str) -> bool:
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb:
        return False
    if ta & tb:
        return True
    # Prefix tolerance for naming variants across sources
    # (e.g. "Czechia" vs "Czech Republic", "Bosnia-Herzegovina" variants).
    for x in ta:
        for y in tb:
            if len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x)):
                return True
    return False


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    """GET with a few retries — ESPN's public API rate-limits bursts (429) and
    occasionally 5xxs, which used to silently collapse the World Cup seeding."""
    import asyncio as _asyncio

    last: Exception | None = None
    for attempt in range(3):
        try:
            r = await client.get(url, params=params or {})
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            last = exc
            if attempt < 2:
                await _asyncio.sleep(0.6 * (attempt + 1))
    raise last  # type: ignore[misc]


async def _find_event(
    client: httpx.AsyncClient, slug: str, match_date: datetime,
    home_name: str, away_name: str,
) -> dict | None:
    """Locate the ESPN event for a match. Tries the UTC date and its
    neighbours, since ESPN groups scoreboards by US-local dates.

    Providers disagree on naming (football-data "CA Mineiro" vs ESPN
    "Atlético-MG"), so requiring both sides to match is too strict. A team
    plays at most once per day in a competition, so a single candidate event
    where at least one side matches is already a reliable identification."""
    for delta in (0, -1, 1):
        d = (match_date + timedelta(days=delta)).strftime("%Y%m%d")
        try:
            data = await _get(client, f"{_BASE}/{slug}/scoreboard", {"dates": d})
        except httpx.HTTPError:
            continue

        candidates: list[tuple[int, dict]] = []
        for ev in data.get("events", []):
            comps = (ev.get("competitions") or [{}])[0].get("competitors", [])
            ev_home = next((c for c in comps if c.get("homeAway") == "home"), None)
            ev_away = next((c for c in comps if c.get("homeAway") == "away"), None)
            if not ev_home or not ev_away:
                continue
            hn = ev_home["team"].get("displayName", "")
            an = ev_away["team"].get("displayName", "")
            score = int(_teams_match(home_name, hn)) + int(_teams_match(away_name, an))
            if score > 0:
                candidates.append((score, {"id": ev["id"], "home": hn, "away": an}))

        exact = [ev for s, ev in candidates if s == 2]
        if exact:
            return exact[0]
        if len(candidates) == 1:
            return candidates[0][1]
    return None


def _parse_summary(summary: dict, espn_home: str, espn_away: str) -> dict:
    teams = summary.get("boxscore", {}).get("teams", [])

    def _stats_for(side_name: str) -> dict:
        for t in teams:
            if _teams_match(side_name, t.get("team", {}).get("displayName", "")):
                raw = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
                return {key: raw.get(key) for key, _, _ in _STATS}
        return {key: None for key, _, _ in _STATS}

    goals = []
    for e in summary.get("keyEvents", []):
        type_text = (e.get("type") or {}).get("text", "")
        is_goal = bool(e.get("scoringPlay")) or "goal" in type_text.lower()
        if not is_goal:
            continue
        team_name = (e.get("team") or {}).get("displayName", "")
        side = "home" if _teams_match(team_name, espn_home) else "away"
        players = [p.get("athlete", {}).get("displayName") for p in e.get("participants", [])]
        goals.append({
            "minute": (e.get("clock") or {}).get("displayValue", ""),
            "side": side,
            "player": players[0] if players else None,
            "text": (e.get("text") or "")[:140],
        })

    return {
        "found": True,
        "source": "ESPN",
        "stat_labels": [{"key": k, "label": lbl, "suffix": sfx} for k, lbl, sfx in _STATS],
        "home_stats": _stats_for(espn_home),
        "away_stats": _stats_for(espn_away),
        "goals": goals,
    }


async def fetch_match_details(
    competition_code: str | None, match_date_iso: str,
    home_name: str, away_name: str,
) -> dict:
    """Possession/shots/corners/cards + goal timeline for a played match.
    `competition_code` may be a football-data code (mapped) or already an
    ESPN league slug (contains a dot, e.g. "fifa.friendly").
    Returns {found: False, reason} when the competition isn't mapped or the
    event can't be located."""
    raw_code = (competition_code or "").strip()
    slug = raw_code.lower() if "." in raw_code else COMP_TO_ESPN.get(raw_code.upper())
    if not slug:
        return {"found": False, "reason": f"Competição '{competition_code}' sem cobertura de estatísticas."}

    cache_key = json.dumps([slug, match_date_iso[:10], sorted(_norm_tokens(home_name) | _norm_tokens(away_name))])
    hit = _cache.get(cache_key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]

    try:
        match_date = datetime.fromisoformat(match_date_iso.replace("Z", "+00:00"))
    except ValueError:
        return {"found": False, "reason": "Data da partida inválida."}

    async with httpx.AsyncClient(timeout=20.0) as client:
        ev = await _find_event(client, slug, match_date, home_name, away_name)
        if not ev:
            result = {"found": False, "reason": "Partida não localizada na fonte de estatísticas."}
            _cache[cache_key] = (time.monotonic(), result)
            return result
        try:
            summary = await _get(client, f"{_BASE}/{slug}/summary", {"event": ev["id"]})
        except httpx.HTTPError as exc:
            logger.warning("ESPN summary failed for event %s: %s", ev["id"], exc)
            return {"found": False, "reason": "Fonte de estatísticas indisponível agora."}

    result = _parse_summary(summary, ev["home"], ev["away"])
    _cache[cache_key] = (time.monotonic(), result)
    if len(_cache) > 300:
        for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[:60]:
            _cache.pop(k, None)
    return result


# ── National teams (World Cup bootstrap & recent internationals) ─────────────
# football-data's free tier hides everything a national team played outside
# the World Cup itself, so before the first WC matches finish there is zero
# data to model with. ESPN's public schedule endpoint exposes each nation's
# last ~25 internationals (friendlies + qualifiers) with scores — we use it to
# seed pre-tournament strength and to show recent form for seleções.

_WC_MAP_TTL = 24 * 3600.0
_wc_map_cache: dict = {"ts": 0.0, "teams": []}


async def fetch_wc_espn_team_map(client: httpx.AsyncClient) -> list[dict]:
    """[{espn_id, name}] for every team in the current World Cup, from the
    tournament scoreboard (covers a wide date window). Cached 24h."""
    now = time.monotonic()
    if _wc_map_cache["teams"] and now - _wc_map_cache["ts"] < _WC_MAP_TTL:
        return _wc_map_cache["teams"]
    today = datetime.now(timezone.utc).date()
    window = (
        f"{(today - timedelta(days=10)).strftime('%Y%m%d')}"
        f"-{(today + timedelta(days=45)).strftime('%Y%m%d')}"
    )
    data = await _get(client, f"{_BASE}/fifa.world/scoreboard", {"dates": window})
    seen: dict[str, str] = {}
    for ev in data.get("events", []):
        for c in (ev.get("competitions") or [{}])[0].get("competitors", []):
            t = c.get("team") or {}
            if t.get("id"):
                seen[str(t["id"])] = t.get("displayName", "")
    teams = [{"espn_id": k, "name": v} for k, v in seen.items()]
    if teams:
        _wc_map_cache["ts"] = now
        _wc_map_cache["teams"] = teams
    return teams


async def fetch_team_intl_results(
    client: httpx.AsyncClient, espn_id: str, limit: int = 12
) -> list[dict]:
    """A national team's last finished internationals (any competition),
    newest first, shaped like our RecentMatch rows. competition_code carries
    the ESPN league slug so the stats modal works directly. Cached 6h."""
    cache_key = f"intl:{espn_id}"
    hit = _cache.get(cache_key)
    if hit and time.monotonic() - hit[0] < 6 * 3600.0:
        return hit[1][:limit]

    data = await _get(client, f"{_BASE}/all/teams/{espn_id}/schedule")
    out: list[dict] = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        status = ((comp.get("status") or {}).get("type") or {})
        if not status.get("completed"):
            continue
        comps = comp.get("competitors", [])
        me = next((c for c in comps if str(c.get("team", {}).get("id")) == str(espn_id)), None)
        opp = next((c for c in comps if str(c.get("team", {}).get("id")) != str(espn_id)), None)
        if not me or not opp:
            continue
        gf = (me.get("score") or {}).get("value")
        ga = (opp.get("score") or {}).get("value")
        if gf is None or ga is None:
            continue
        gf, ga = int(gf), int(ga)
        league = ev.get("league") or {}
        logos = (opp.get("team") or {}).get("logos") or []
        out.append({
            "match_id": int(ev.get("id") or 0),
            "date": ev.get("date", ""),
            "competition": league.get("name"),
            "competition_code": league.get("slug"),  # ESPN slug — modal-ready
            "competition_emblem": None,
            "is_home": me.get("homeAway") == "home",
            "opponent": (opp.get("team") or {}).get("displayName", ""),
            "opponent_espn_id": str((opp.get("team") or {}).get("id") or ""),
            "opponent_short": (opp.get("team") or {}).get("abbreviation"),
            "opponent_crest": logos[0].get("href") if logos else None,
            "goals_for": gf,
            "goals_against": ga,
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })
    out.sort(key=lambda m: m["date"], reverse=True)
    _cache[cache_key] = (time.monotonic(), out)
    return out[:limit]


async def head_to_head_internationals(
    client: httpx.AsyncClient, home_name: str, away_name: str, limit: int = 3,
) -> list[dict]:
    """Recent direct meetings between two national teams (friendlies +
    qualifiers via ESPN), in the dossier H2H shape. Reuses the cached
    internationals list of `home_name`, so it costs no extra network call when
    form was already fetched."""
    res = await recent_internationals_by_name(client, home_name, limit=40)
    if not res:
        return []
    out: list[dict] = []
    for m in res:
        if not _teams_match(m["opponent"], away_name):
            continue
        if m["is_home"]:
            hn, an, hg, ag = home_name, m["opponent"], m["goals_for"], m["goals_against"]
        else:
            hn, an, hg, ag = m["opponent"], home_name, m["goals_against"], m["goals_for"]
        out.append({
            "date": m["date"], "competition": m["competition"],
            "home_name": hn, "away_name": an, "home_goals": hg, "away_goals": ag,
        })
        if len(out) >= limit:
            break
    return out


async def recent_internationals_by_name(
    client: httpx.AsyncClient, team_name: str, limit: int = 10
) -> list[dict] | None:
    """Recent internationals for a WC nation located by name; None when the
    name can't be mapped to an ESPN team."""
    try:
        teams = await fetch_wc_espn_team_map(client)
    except httpx.HTTPError:
        return None
    match = next((t for t in teams if _teams_match(team_name, t["name"])), None)
    if not match:
        return None
    try:
        return await fetch_team_intl_results(client, match["espn_id"], limit)
    except httpx.HTTPError:
        return None
