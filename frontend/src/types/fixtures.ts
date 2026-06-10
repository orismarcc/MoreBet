export interface UpcomingFixture {
  fixture_id: number
  match_date: string
  status: string
  venue: string | null
  league_id: number
  league_name: string
  league_country: string
  league_logo: string | null
  round: string | null
  home_team_api_id: number
  home_team_name: string
  home_team_logo: string | null
  away_team_api_id: number
  away_team_name: string
  away_team_logo: string | null
  home_db_id: number | null
  away_db_id: number | null
}
