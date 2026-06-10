"""
HTTP client for api-football.com (v3).
All requests use x-apisports-key header.
"""
from datetime import date, timedelta
import httpx
from app.config import settings

SUPPORTED_LEAGUES = {
    39:  ("Premier League", "England"),
    140: ("La Liga", "Spain"),
    135: ("Serie A", "Italy"),
    78:  ("Bundesliga", "Germany"),
    61:  ("Ligue 1", "France"),
    71:  ("Brasileiro Série A", "Brazil"),
    94:  ("Primeira Liga", "Portugal"),
    88:  ("Eredivisie", "Netherlands"),
}

# Leagues that run Jan-Dec (use current calendar year as season)
CALENDAR_YEAR_LEAGUES = {71, 72, 73}  # Brasileirão A/B/C


def current_season(league_id: int) -> int:
    today = date.today()
    if league_id in CALENDAR_YEAR_LEAGUES:
        return today.year
    # European leagues: season starts in July/August
    # If we're before July, the current season started last year
    return today.year if today.month >= 7 else today.year - 1


def _headers() -> dict[str, str]:
    return {"x-apisports-key": settings.api_football_key}


async def fetch_league(client: httpx.AsyncClient, league_id: int) -> dict:
    season = current_season(league_id)
    r = await client.get(
        f"{settings.api_football_base_url}/leagues",
        headers=_headers(),
        params={"id": league_id, "season": season},
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
        "season": season,
        "logo_url": item["league"]["logo"],
    }


async def fetch_standings(client: httpx.AsyncClient, league_id: int) -> list[dict]:
    season = current_season(league_id)
    r = await client.get(
        f"{settings.api_football_base_url}/standings",
        headers=_headers(),
        params={"league": league_id, "season": season},
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


async def fetch_upcoming_fixtures(
    client: httpx.AsyncClient,
    league_id: int,
    days: int = 7,
) -> list[dict]:
    """Fetch upcoming (not yet played) fixtures for the next N days."""
    today = date.today()
    date_to = today + timedelta(days=days)
    season = current_season(league_id)
    r = await client.get(
        f"{settings.api_football_base_url}/fixtures",
        headers=_headers(),
        params={
            "league": league_id,
            "season": season,
            "from": today.isoformat(),
            "to": date_to.isoformat(),
            "status": "NS-TBD-1H-HT-2H-ET-BT-P",  # Not started + live
        },
    )
    r.raise_for_status()
    data = r.json()
    fixtures = []
    for f in data.get("response", []):
        fixture = f["fixture"]
        home = f["teams"]["home"]
        away = f["teams"]["away"]
        fixtures.append({
            "fixture_id": fixture["id"],
            "match_date": fixture["date"],
            "status": fixture["status"]["short"],
            "venue": fixture.get("venue", {}).get("name"),
            "league_id": f["league"]["id"],
            "league_name": f["league"]["name"],
            "league_country": f["league"]["country"],
            "league_logo": f["league"]["logo"],
            "round": f["league"].get("round"),
            "home_team_api_id": home["id"],
            "home_team_name": home["name"],
            "home_team_logo": home["logo"],
            "away_team_api_id": away["id"],
            "away_team_name": away["name"],
            "away_team_logo": away["logo"],
        })
    return sorted(fixtures, key=lambda x: x["match_date"])


async def fetch_players(
    client: httpx.AsyncClient, team_id: int, league_id: int = 39
) -> list[dict]:
    season = current_season(league_id)
    r = await client.get(
        f"{settings.api_football_base_url}/players",
        headers=_headers(),
        params={"team": team_id, "season": season},
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
