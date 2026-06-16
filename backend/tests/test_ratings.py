"""Opponent-adjusted ratings: strength of schedule must override raw goals."""
import pytest

from app.core.ratings import (
    compute_ratings,
    seed_from_matches,
    team_split_inputs,
    TeamRating,
)
from app.core.engine import TeamInput, analyse_match
from app.core.strength import LeagueAverages


def test_empty_input():
    ratings, mu = compute_ratings([])
    assert ratings == {}
    assert mu == 0.0


def test_average_rating_is_one():
    games = [("a", "b", 2, 1), ("b", "c", 1, 1), ("c", "a", 0, 3)]
    ratings, mu = compute_ratings(games)
    mean_atk = sum(r.attack for r in ratings.values()) / len(ratings)
    mean_def = sum(r.defense for r in ratings.values()) / len(ratings)
    assert mean_atk == pytest.approx(1.0, abs=1e-6)
    assert mean_def == pytest.approx(1.0, abs=1e-6)


def test_strength_of_schedule_beats_raw_average():
    """Two teams score the SAME raw average, but one did it against a strong
    defence and the other against a punching bag. The first must rate higher."""
    games = [
        # 'giant' and 'flatTrack' both average 3 goals scored...
        ("giant", "elite_def", 3, 0),    # 3 vs a team that otherwise concedes nothing
        ("giant", "elite_def", 3, 0),
        ("flatTrack", "sieve", 3, 0),    # 3 vs a team that concedes to everyone
        ("flatTrack", "sieve", 3, 0),
        # establish that elite_def is elite and sieve is a sieve, via others
        ("elite_def", "other1", 0, 0),
        ("elite_def", "other2", 0, 0),
        ("sieve", "other1", 0, 5),
        ("sieve", "other2", 0, 5),
        ("other1", "other2", 1, 1),
    ]
    ratings, _ = compute_ratings(games)
    assert ratings["giant"].attack > ratings["flatTrack"].attack


def test_minnow_defence_is_exposed():
    """A team that conceded little ONLY because it faced weak attacks must not
    rate as a good defence — the Cape Verde failure mode."""
    games = [
        # 'minnow' concedes few goals but only plays toothless attackers
        ("minnow", "toothless1", 1, 0),
        ("minnow", "toothless2", 1, 0),
        ("toothless1", "strong", 0, 4),
        ("toothless2", "strong", 0, 4),
        ("toothless1", "toothless2", 0, 0),
        # 'realwall' concedes the same but against a lethal attack
        ("realwall", "strong", 0, 0),
        ("realwall", "strong", 1, 0),
    ]
    ratings, _ = compute_ratings(games)
    # realwall held a strong attack scoreless → genuinely better defence
    # (lower defense rating = concedes less)
    assert ratings["realwall"].defense < ratings["minnow"].defense


def test_dedup_caller_responsibility_no_crash_on_repeats():
    games = [("a", "b", 1, 0), ("a", "b", 1, 0), ("b", "a", 0, 1)]
    ratings, mu = compute_ratings(games)
    assert mu > 0
    assert "a" in ratings and "b" in ratings


def test_ratings_converge_stable():
    games = [("a", "b", 2, 1), ("b", "c", 3, 0), ("c", "a", 1, 1), ("a", "c", 2, 2)]
    r1, _ = compute_ratings(games, iterations=30)
    r2, _ = compute_ratings(games, iterations=120)
    for key in r1:
        assert r1[key].attack == pytest.approx(r2[key].attack, abs=1e-3)
        assert r1[key].defense == pytest.approx(r2[key].defense, abs=1e-3)


class TestSeedFromMatches:
    def test_empty(self):
        ratings, mh, ma = seed_from_matches([])
        assert ratings == {} and mh == 0.0 and ma == 0.0

    def test_home_away_means_split(self):
        # Home teams score more here → mu_home > mu_away (home advantage)
        matches = [("a", "b", 3, 0), ("b", "a", 2, 1), ("a", "c", 2, 0), ("c", "a", 1, 1)]
        _r, mu_home, mu_away = seed_from_matches(matches)
        assert mu_home == pytest.approx((3 + 2 + 2 + 1) / 4)
        assert mu_away == pytest.approx((0 + 1 + 0 + 1) / 4)

    def test_split_inputs_reproduce_engine_lambdas(self):
        """The whole point: team_split_inputs + league(mu_home, mu_away) through
        the engine (no shrinkage) must reproduce λ = atk·def·mu exactly."""
        matches = [
            ("strong", "weak", 4, 0), ("weak", "strong", 0, 3),
            ("strong", "mid", 2, 1), ("mid", "strong", 1, 2),
            ("mid", "weak", 2, 0), ("weak", "mid", 1, 1),
        ]
        ratings, mu_home, mu_away = seed_from_matches(matches)
        rh, ra = ratings["strong"], ratings["weak"]
        hs = team_split_inputs(rh, mu_home, mu_away)
        as_ = team_split_inputs(ra, mu_home, mu_away)
        ti = TeamInput(
            home_goals_scored_avg=hs["home_goals_scored"],
            home_goals_conceded_avg=hs["home_goals_conceded"],
            away_goals_scored_avg=as_["away_goals_scored"],
            away_goals_conceded_avg=as_["away_goals_conceded"],
        )
        r = analyse_match(ti, LeagueAverages(home_goals_avg=mu_home, away_goals_avg=mu_away))
        assert r.lambda_home == pytest.approx(rh.attack * ra.defense * mu_home, abs=1e-6)
        assert r.lambda_away == pytest.approx(ra.attack * rh.defense * mu_away, abs=1e-6)

    def test_strong_team_favored_over_weak(self):
        matches = [
            ("strong", "weak", 4, 0), ("weak", "strong", 0, 3),
            ("strong", "mid", 2, 1), ("mid", "strong", 1, 2),
            ("mid", "weak", 2, 0), ("weak", "mid", 1, 1),
            ("strong", "weak", 3, 0), ("mid", "weak", 3, 1),
        ]
        ratings, mu_home, mu_away = seed_from_matches(matches)
        hs = team_split_inputs(ratings["strong"], mu_home, mu_away)
        as_ = team_split_inputs(ratings["weak"], mu_home, mu_away)
        ti = TeamInput(
            home_goals_scored_avg=hs["home_goals_scored"],
            home_goals_conceded_avg=hs["home_goals_conceded"],
            away_goals_scored_avg=as_["away_goals_scored"],
            away_goals_conceded_avg=as_["away_goals_conceded"],
        )
        r = analyse_match(ti, LeagueAverages(home_goals_avg=mu_home, away_goals_avg=mu_away))
        assert r.markets.home_win > 0.6  # strong at home vs weak


def test_team_split_inputs_mirror_when_neutral():
    """Neutral venue (mu_home == mu_away) ⇒ home and away splits mirror."""
    s = team_split_inputs(TeamRating(attack=1.5, defense=0.8, games=10), 1.4, 1.4)
    assert s["home_goals_scored"] == s["away_goals_scored"]
    assert s["home_goals_conceded"] == s["away_goals_conceded"]
