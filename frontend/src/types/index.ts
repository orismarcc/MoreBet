export interface League {
  id: number
  api_id: number
  name: string
  country: string
  season: number
  logo_url: string | null
  home_goals_avg: number | null
  away_goals_avg: number | null
  total_matches: number
  last_updated: string | null
}

export interface Team {
  id: number
  api_id: number
  name: string
  short_name: string | null
  logo_url: string | null
  home_goals_scored: number
  home_goals_conceded: number
  away_goals_scored: number
  away_goals_conceded: number
  home_xg_scored: number | null
  away_xg_conceded: number | null
}

export interface Player {
  id: number
  name: string
  position: string | null
  goals: number
  assists: number
  goal_contribution_pct: number
  sca: number | null
  xg_assisted: number | null
  minutes_played: number
  is_available: boolean
}

export interface ScoreProb {
  home: number
  away: number
  prob: number
}

export interface MarketSet {
  // 1X2
  home_win: number
  draw: number
  away_win: number
  // Double chance
  home_or_draw: number
  away_or_draw: number
  home_or_away: number
  // Over / Under
  over_05: number
  over_15: number
  over_25: number
  over_35: number
  over_45: number
  under_05: number
  under_15: number
  under_25: number
  under_35: number
  under_45: number
  // BTTS
  btts_yes: number
  btts_no: number
  // Asian Handicap
  ah_home_minus_half: number
  ah_home_minus_one: number
  ah_home_minus_one_half: number
  ah_home_plus_half: number
  ah_away_minus_half: number
  ah_away_minus_one: number
  ah_away_minus_one_half: number
  ah_away_plus_half: number
  // Combined
  btts_and_over_25: number
  btts_and_under_25: number
  home_and_over_25: number
  away_and_over_25: number
  // Score ranges
  score_0_1_goals: number
  score_2_3_goals: number
  score_4_plus_goals: number
}

export type Markets = MarketSet
export type FairOdds = MarketSet

export interface MatchAnalysis {
  lambda_home: number
  lambda_away: number
  home_modifier: number
  away_modifier: number
  markets: Markets
  fair_odds: FairOdds
  top_scores: ScoreProb[]
  home_team: Team
  away_team: Team
}

export interface RecentMatch {
  match_id: number
  date: string
  competition: string | null
  competition_code: string | null
  competition_emblem: string | null
  is_home: boolean
  opponent: string
  opponent_short: string | null
  opponent_crest: string | null
  goals_for: number
  goals_against: number
  result: 'W' | 'D' | 'L'
}

export interface RecentSummary {
  played: number
  wins: number
  draws: number
  losses: number
  goals_for: number
  goals_against: number
  avg_goals_for: number
  avg_goals_against: number
  over_15_pct: number
  over_25_pct: number
  btts_pct: number
  clean_sheets: number
  failed_to_score: number
  ppg: number
  form: string
}

export interface UpcomingTeamMatch {
  match_id: number
  date: string
  competition: string | null
  competition_emblem: string | null
  is_home: boolean
  opponent: string
  opponent_api_id: number | null
  opponent_crest: string | null
}

export interface RecentForm {
  summary: RecentSummary
  matches: RecentMatch[]
  upcoming: UpcomingTeamMatch[]
}

export interface H2HMatch {
  match_id: number
  date: string
  competition: string | null
  competition_code: string | null
  home_api_id: number
  home_name: string
  home_crest: string | null
  away_api_id: number
  away_name: string
  away_crest: string | null
  home_goals: number
  away_goals: number
}

export interface GoalEvent {
  minute: string
  side: 'home' | 'away'
  player: string | null
  text: string
}

export interface StatLabel {
  key: string
  label: string
  suffix: string
}

export interface MatchDetails {
  found: boolean
  reason: string | null
  source: string | null
  stat_labels: StatLabel[]
  home_stats: Record<string, string | null>
  away_stats: Record<string, string | null>
  goals: GoalEvent[]
}

/** Referência mínima de uma partida jogada, para abrir o modal de detalhes. */
export interface MatchRef {
  date: string
  competition: string | null
  competition_code: string | null
  home_name: string
  away_name: string
  home_goals: number
  away_goals: number
}

export interface TeamSearchResult {
  kind: 'club' | 'national'
  db_id: number | null
  api_id: number
  name: string
  short_name: string | null
  crest: string | null
  context: string
}

export interface AbsentPlayer {
  player_id: number
  goal_contribution_pct: number
}

export interface CalculateMatchPayload {
  home_team_id: number
  away_team_id: number
  absent_home: AbsentPlayer[]
  absent_away: AbsentPlayer[]
  xg_weight: number
}

export interface ValueCheckPayload {
  market: string
  fair_odds: number
  bookie_odds: number
}

export interface ValueCheckResult {
  market: string
  fair_odds: number
  bookie_odds: number
  ev_pct: number
  has_value: boolean
  kelly_pct: number
  quarter_kelly_pct: number
  verdict: string
}

// ── Agente de recomendação ───────────────────────────────────────────────────

export type RecommendationConfidence = 'alta' | 'media' | 'baixa'

export interface AgentRecommendation {
  market: string
  market_label: string
  model_probability: number
  fair_odds: number
  min_bookie_odds: number
  suggested_stake_pct: number
  confidence: RecommendationConfidence
  rationale: string
  caveats: string[]
  market_odds: number | null
  market_bookmaker: string | null
  market_ev_pct: number | null
  has_market_value: boolean | null
  sharp_prob: number | null
  clv_pct: number | null
  market_disagreement: boolean | null
}

export interface StandingRow {
  position: number | null
  team_api_id: number | null
  team_name: string | null
  team_crest: string | null
  played: number | null
  won: number | null
  draw: number | null
  lost: number | null
  goals_for: number | null
  goals_against: number | null
  goal_difference: number | null
  points: number | null
  db_id: number | null
}

export interface StandingGroup {
  group: string | null
  rows: StandingRow[]
}

export interface MarketOddsEvent {
  home: string
  away: string
  commence_time: string | null
  bookmaker_count: number
}

export interface RecommendationReport {
  no_bet: boolean
  summary: string
  recommendations: AgentRecommendation[]
  data_quality_notes: string[]
  model_id: string
  cached: boolean
  market_odds_event: MarketOddsEvent | null
}

// ── Backtest ─────────────────────────────────────────────────────────────────

export interface CalibrationBucket {
  range_low: number
  range_high: number
  predicted_avg: number
  observed_freq: number
  count: number
}

export interface BacktestReport {
  league_api_id: number
  league_name: string
  n_matches_total: number
  n_predicted: number
  n_skipped: number
  period_from: string | null
  period_to: string | null
  brier_1x2_model: number | null
  brier_1x2_baseline: number | null
  skill_score_1x2: number | null
  log_loss_model: number | null
  log_loss_baseline: number | null
  accuracy_model: number | null
  accuracy_baseline: number | null
  brier_over25_model: number | null
  brier_over25_baseline: number | null
  over25_base_rate: number | null
  brier_btts_model: number | null
  brier_btts_baseline: number | null
  btts_base_rate: number | null
  calibration: CalibrationBucket[]
}
