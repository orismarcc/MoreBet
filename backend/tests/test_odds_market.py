"""Unit tests for the-odds-api name matching and market resolution (no network)."""
from app.services import odds_market as om


def test_name_match_exact_and_alias():
    assert om._name_match("Brazil", "Brazil")
    assert om._name_match("United States", "USA")
    assert om._name_match("Czechia", "Czech Republic")
    assert om._name_match("Cruzeiro EC", "Cruzeiro")


def test_name_match_rejects_weak_token_collisions():
    # Regression: these share only a geographic modifier and must NOT match.
    assert not om._name_match("South Korea", "South Africa")
    assert not om._name_match("Saudi Arabia", "South Africa")
    assert not om._name_match("North Macedonia", "South Korea")
    assert not om._name_match("United States", "United Arab Emirates")


def test_find_event_picks_correct_orientation():
    events = [
        {"home_team": "Morocco", "away_team": "Brazil", "bookmakers": []},
        {"home_team": "South Africa", "away_team": "Mexico", "bookmakers": []},
    ]
    ev = om._find_event(events, "Brazil", "Morocco")
    assert ev is not None and ev["home_team"] == "Morocco"
    assert om._find_event(events, "Brazil", "South Korea") is None


def _event_with(market_key, outcomes):
    return {
        "home_team": "Brazil", "away_team": "Morocco",
        "bookmakers": [{
            "key": "pinnacle", "title": "Pinnacle",
            "markets": [{"key": market_key, "outcomes": outcomes}],
        }],
    }


def test_h2h_resolution_by_team_name():
    ev = _event_with("h2h", [
        {"name": "Brazil", "price": 1.70},
        {"name": "Morocco", "price": 6.0},
        {"name": "Draw", "price": 4.0},
    ])
    res = om._market_resolvers("Brazil", "Morocco")
    assert res["home_win"](ev) == (1.70, "Pinnacle")
    assert res["away_win"](ev) == (6.0, "Pinnacle")
    assert res["draw"](ev) == (4.0, "Pinnacle")


def test_totals_resolution_by_line():
    ev = _event_with("totals", [
        {"name": "Over", "price": 2.10, "point": 2.5},
        {"name": "Under", "price": 1.75, "point": 2.5},
        {"name": "Over", "price": 1.50, "point": 1.5},
    ])
    res = om._market_resolvers("Brazil", "Morocco")
    assert res["over_25"](ev) == (2.10, "Pinnacle")
    assert res["under_25"](ev) == (1.75, "Pinnacle")
    assert res["over_15"](ev) == (1.50, "Pinnacle")
    assert res["over_35"](ev) is None


def test_best_price_across_bookmakers():
    ev = {
        "home_team": "Brazil", "away_team": "Morocco",
        "bookmakers": [
            {"key": "a", "title": "A", "markets": [{"key": "h2h", "outcomes": [{"name": "Brazil", "price": 1.70}]}]},
            {"key": "b", "title": "B", "markets": [{"key": "h2h", "outcomes": [{"name": "Brazil", "price": 1.82}]}]},
        ],
    }
    res = om._market_resolvers("Brazil", "Morocco")
    assert res["home_win"](ev) == (1.82, "B")  # best (highest) price wins


def test_demargin_removes_overround():
    # 1X2 with ~5% overround → de-margined sums to 1.
    probs = om._demargin([1.69, 3.76, 5.58])
    assert abs(sum(probs) - 1.0) < 1e-9
    assert probs[0] > probs[1] > probs[2]  # favourite highest


def test_sharp_probabilities_1x2_and_totals_and_dc():
    event = {
        "home_team": "Brazil", "away_team": "Morocco",
        "bookmakers": [{
            "key": "pinnacle", "title": "Pinnacle",
            "markets": [
                {"key": "h2h", "outcomes": [
                    {"name": "Brazil", "price": 1.69},
                    {"name": "Morocco", "price": 5.58},
                    {"name": "Draw", "price": 3.76},
                ]},
                {"key": "totals", "outcomes": [
                    {"name": "Over", "price": 2.05, "point": 2.5},
                    {"name": "Under", "price": 1.80, "point": 2.5},
                ]},
            ],
        }],
    }
    sp = om.sharp_probabilities(event, "Brazil", "Morocco")
    assert 0.55 < sp["home_win"] < 0.60          # de-margined favourite
    assert abs(sp["home_or_draw"] - (sp["home_win"] + sp["draw"])) < 1e-9
    assert abs((sp["over_25"] + sp["under_25"]) - 1.0) < 1e-9


def test_sharp_prefers_sharpest_book():
    # A soft book with a wild line must not override Pinnacle for the benchmark.
    event = {
        "home_team": "A", "away_team": "B",
        "bookmakers": [
            {"key": "softbook", "title": "Soft", "markets": [{"key": "h2h", "outcomes": [
                {"name": "A", "price": 1.40}, {"name": "B", "price": 9.0}, {"name": "Draw", "price": 5.0}]}]},
            {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [
                {"name": "A", "price": 2.00}, {"name": "B", "price": 4.0}, {"name": "Draw", "price": 3.5}]}]},
        ],
    }
    sp = om.sharp_probabilities(event, "A", "B")
    # Pinnacle (A=2.00 → ~48%) wins over Soft (A=1.40 → ~70%).
    assert sp["home_win"] < 0.55
