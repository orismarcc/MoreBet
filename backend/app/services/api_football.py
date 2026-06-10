"""
HTTP client for api-football.com (v3).
All requests use x-apisports-key header.
"""
import httpx
from app.config import settings

SUPPORTED_LEAGUES = {
    39:  ("Premier League", "England"),
    140: ("La Liga", "Spain"),
    135: ("Serie A", "Italy"),
    78:  ("Bundesliga", "Germany"),
    61:  ("Ligue 1", "France"),
    71:  ("Brasileiro Série A", "Brazil"),
}

CURRENT_SEASON = 2024


def _headers() -> dict[str, str]:
    return {"x-apisports-key": settings.api_football_key}


async def fetch_league(client: httpx.AsyncClient, league_id: int) -> dict:
    r = await client.get(
        f"{settings.api_football_base_url}/leagues",
        headers=_headers(),
        params={"id": league_id, "season": CURRENT_SEASON},
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("response"):
        return {}
    item = data["response"][0]
    return {
        "api_id": item["league"]["id"],
        "name": item["league"]["name"],
        "country": item["country"]["name"],
        "season": CURRENT_SEASON,
        "logo_url": item["league"]["logo"],
    }


async def fetch_standings(client: httpx.AsyncClient, league_id: int) -> list[dict]:
    r = await client.get(
        f"{settings.api_football_base_url}/standings",
        headers=_headers(),
        params={"league": league_id, "season": CURRENT_SEASON},
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("response"):
        return []
    standings = data["response"][0]["league"]["standings"][0]
    teams = []
    for entry in standings:
        team = entry["team"]
        home = entry["home"]
        away = entry["away"]
        teams.append({
            "api_id": team["id"],
            "name": team["name"],
            "logo_url": team["logo"],
            "home_played": home["played"],
            "home_goals_scored": home["goals"]["for"] / home["played"] if home["played"] else 0.0,
            "home_goals_conceded": home["goals"]["against"] / home["played"] if home["played"] else 0.0,
            "away_played": away["played"],
            "away_goals_scored": away["goals"]["for"] / away["played"] if away["played"] else 0.0,
            "away_goals_conceded": away["goals"]["against"] / away["played"] if away["played"] else 0.0,
        })
    return teams


async def fetch_fixtures(
    client: httpx.AsyncClient, league_id: int, season: int = CURRENT_SEASON
) -> list[dict]:
    r = await client.get(
        f"{settings.api_football_base_url}/fixtures",
        headers=_headers(),
        params={"league": league_id, "season": season, "status": "FT"},
    )
    r.raise_for_status()
    data = r.json()
    fixtures = []
    for f in data.get("response", []):
        fixture = f["fixture"]
        goals = f["goals"]
        score = f.get("score", {})
        fixtures.append({
            "api_id": fixture["id"],
            "match_date": fixture["date"],
            "home_team_api_id": f["teams"]["home"]["id"],
            "away_team_api_id": f["teams"]["away"]["id"],
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "is_finished": True,
        })
    return fixtures


async def fetch_players(
    client: httpx.AsyncClient, team_id: int
) -> list[dict]:
    """Fetch top players for a team (season stats)."""
    r = await client.get(
        f"{settings.api_football_base_url}/players",
        headers=_headers(),
        params={"team": team_id, "season": CURRENT_SEASON},
    )
    r.raise_for_status()
    data = r.json()
    players = []
    for entry in data.get("response", []):
        p = entry["player"]
        stats = entry.get("statistics", [{}])[0]
        goals = stats.get("goals", {})
        games = stats.get("games", {})
        players.append({
            "api_id": p["id"],
            "name": p["name"],
            "position": games.get("position"),
            "goals": goals.get("total") or 0,
            "assists": goals.get("assists") or 0,
            "minutes_played": games.get("minutes") or 0,
        })
    return players
