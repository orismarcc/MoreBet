from pydantic import BaseModel, Field


# ── League ────────────────────────────────────────────────────────────────────

class LeagueOut(BaseModel):
    id: int
    api_id: int
    name: str
    country: str
    season: int
    logo_url: str | None
    home_goals_avg: float | None
    away_goals_avg: float | None
    total_matches: int

    model_config = {"from_attributes": True}


# ── Team ──────────────────────────────────────────────────────────────────────

class TeamOut(BaseModel):
    id: int
    api_id: int
    name: str
    short_name: str | None
    logo_url: str | None
    home_goals_scored: float
    home_goals_conceded: float
    away_goals_scored: float
    away_goals_conceded: float
    home_xg_scored: float | None
    away_xg_conceded: float | None

    model_config = {"from_attributes": True}


# ── Player ────────────────────────────────────────────────────────────────────

class PlayerOut(BaseModel):
    id: int
    name: str
    position: str | None
    goals: int
    assists: int
    goal_contribution_pct: float
    sca: float | None
    xg_assisted: float | None
    minutes_played: int
    is_available: bool

    model_config = {"from_attributes": True}


class PlayerUpdateIn(BaseModel):
    goal_contribution_pct: float | None = None
    sca: float | None = None
    xg_assisted: float | None = None
    is_available: bool | None = None


# ── Match Calculation ─────────────────────────────────────────────────────────

class AbsentPlayer(BaseModel):
    player_id: int
    goal_contribution_pct: float = Field(
        ..., ge=0.0, le=1.0,
        description="Fraction of team goals this player contributed (0–1)"
    )


class CalculateMatchIn(BaseModel):
    home_team_id: int
    away_team_id: int
    absent_home: list[AbsentPlayer] = []
    absent_away: list[AbsentPlayer] = []
    xg_weight: float = Field(default=0.4, ge=0.0, le=1.0)


class ScoreProb(BaseModel):
    home: int
    away: int
    prob: float


class _MarketFields(BaseModel):
    # 1X2
    home_win: float
    draw: float
    away_win: float
    # Double chance
    home_or_draw: float
    away_or_draw: float
    home_or_away: float
    # Over/Under
    over_05: float
    over_15: float
    over_25: float
    over_35: float
    over_45: float
    under_05: float
    under_15: float
    under_25: float
    under_35: float
    under_45: float
    # BTTS
    btts_yes: float
    btts_no: float
    # Asian Handicap
    ah_home_minus_half: float
    ah_home_minus_one: float
    ah_home_minus_one_half: float
    ah_home_plus_half: float
    ah_away_minus_half: float
    ah_away_minus_one: float
    ah_away_minus_one_half: float
    ah_away_plus_half: float
    # Combined
    btts_and_over_25: float
    btts_and_under_25: float
    home_and_over_25: float
    away_and_over_25: float
    # Score ranges
    score_0_1_goals: float
    score_2_3_goals: float
    score_4_plus_goals: float


class MarketsOut(_MarketFields):
    pass


class FairOddsOut(_MarketFields):
    pass


class MatchAnalysisOut(BaseModel):
    lambda_home: float
    lambda_away: float
    home_modifier: float
    away_modifier: float
    markets: MarketsOut
    fair_odds: FairOddsOut
    top_scores: list[ScoreProb]
    home_team: TeamOut
    away_team: TeamOut


# ── Value Finder ──────────────────────────────────────────────────────────────

class ValueCheckIn(BaseModel):
    market: str
    fair_odds: float
    bookie_odds: float = Field(..., gt=1.0)


class ValueCheckOut(BaseModel):
    market: str
    fair_odds: float
    bookie_odds: float
    ev_pct: float
    has_value: bool
    kelly_pct: float       # full-Kelly fraction of bankroll (0..1)
    quarter_kelly_pct: float  # conservative 25%-Kelly suggestion
    verdict: str
