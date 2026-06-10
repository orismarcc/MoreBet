"""
HTTP client for football-data.org (v4).

This is the PRIMARY data provider. Its free tier (TIER_ONE) covers all eight
MoreBet leagues *with the current season* — which the previous provider
(API-Football free) did not, leaving the app stuck on an old season.

Auth is via the `X-Auth-Token` header. Free tier allows ~10 requests/minute.
"""
from datetime import date, timedelta

import httpx

from app.config import settings

# Stable API-Football numeric id (kept as the DB / frontend key) -> the
# football-data.org competition code. Keeping the original ids means existing
# league rows, the frontend league list and the /leagues/{id}/refresh URLs all
# keep working unchanged after the provider switch.
FD_LEAGUES: dict[int, tuple[str, str, str]] = {
    39:  ("PL",  "Premier League",      "England"),
    140: ("PD",  "La Liga",             "Spain"),
    135: ("SA",  "Serie A",             "Italy"),
    78:  ("BL1", "Bundesliga",          "Germany"),
    61:  ("FL1", "Ligue 1",             "France"),
    71:  ("BSA", "Brasileirão Série A", "Brazil"),
    94:  ("PPL", "Primeira Liga",       "Portugal"),
    88:  ("DED", "Eredivisie",          "Netherlands"),
}

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
    r = await client.get(
        f"{settings.football_data_base_url}/competitions/{code}/matches",
        headers=_headers(),
        params=params,
    )
    r.raise_for_status()
    return r.json()


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

    cur_finished = _finished(cur_matches)
    if not cur_finished:
        raise ValueError(
            f"League {league_id} ({code}): no finished matches in the current "
            f"season {season_year} yet"
        )

    # Build per-team chronological histories from current + previous seasons.
    all_finished = _finished(prev_matches) + cur_finished
    all_finished.sort(key=lambda m: m["utcDate"])

    teams: dict[int, dict] = {}
    histories: dict[int, list[dict]] = {}
    for m in all_finished:
        ft = m["score"]["fullTime"]
        gh, ga = ft["home"], ft["away"]
        h, a = m["homeTeam"], m["awayTeam"]
        teams.setdefault(h["id"], h)
        teams.setdefault(a["id"], a)
        histories.setdefault(h["id"], []).append({"is_home": True,  "scored": gh, "conceded": ga})
        histories.setdefault(a["id"], []).append({"is_home": False, "scored": ga, "conceded": gh})

    # Genuine participants of the CURRENT season only. Counting current-season
    # matches excludes any intruder and ignores prev-season-only teams.
    season_counts: dict[int, int] = {}
    for m in cur_finished:
        for side in ("homeTeam", "awayTeam"):
            tid = m[side]["id"]
            season_counts[tid] = season_counts.get(tid, 0) + 1
    threshold = max(season_counts.values()) * 0.5
    current_team_ids = {tid for tid, n in season_counts.items() if n >= threshold}

    teams_list: list[dict] = []
    for tid in current_team_ids:
        info = teams[tid]
        averages = _team_form_averages(histories[tid], last_n)
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
