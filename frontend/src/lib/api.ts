import axios from 'axios'
import type {
  League, Team, Player, MatchAnalysis,
  CalculateMatchPayload, ValueCheckPayload, ValueCheckResult,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
})

// Inject JWT token on every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('morebet_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, clear token and reload to show login
api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('morebet_token')
      localStorage.removeItem('morebet_email')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string; email: string }>(
      '/auth/login', { email, password }
    ).then(r => r.data),
  me: () => api.get('/auth/me').then(r => r.data),
}

export const leaguesApi = {
  list: () => api.get<League[]>('/leagues/').then(r => r.data),
  get: (id: number) => api.get<League>(`/leagues/${id}`).then(r => r.data),
  refresh: (apiId: number) => api.post<League>(`/leagues/${apiId}/refresh`).then(r => r.data),
  refreshAll: () =>
    api.post<{ results: string[] }>('/leagues/refresh-all', undefined, { timeout: 180_000 })
      .then(r => r.data),
  backtest: (leagueApiId: number) =>
    api.post<import('../types').BacktestReport>(`/leagues/${leagueApiId}/backtest`, undefined, {
      timeout: 120_000,
    }).then(r => r.data),
}

export const teamsApi = {
  byLeague: (leagueId: number) =>
    api.get<Team[]>(`/teams/league/${leagueId}`).then(r => r.data),
  get: (id: number) => api.get<Team>(`/teams/${id}`).then(r => r.data),
  players: (teamId: number) =>
    api.get<Player[]>(`/teams/${teamId}/players`).then(r => r.data),
  recent: (teamId: number, limit = 6, upcoming = false) =>
    api.get<import('../types').RecentForm>(`/teams/${teamId}/recent`, {
      params: { limit, upcoming },
    }).then(r => r.data),
  byApiId: (apiId: number) =>
    api.get<Team>(`/teams/api/${apiId}`).then(r => r.data),
  recentByApiId: (apiId: number, limit = 6, upcoming = false) =>
    api.get<import('../types').RecentForm>(`/teams/api/${apiId}/recent`, {
      params: { limit, upcoming },
    }).then(r => r.data),
  search: (q: string) =>
    api.get<import('../types').TeamSearchResult[]>('/teams/search', {
      params: { q },
    }).then(r => r.data),
}

export const matchesApi = {
  calculate: (payload: CalculateMatchPayload) =>
    api.post<MatchAnalysis>('/matches/calculate', payload).then(r => r.data),
  // O agente analisa forma + H2H + backtest e chama o Claude — pode levar ~1min
  recommend: (payload: CalculateMatchPayload) =>
    api.post<import('../types').RecommendationReport>('/matches/recommend', payload, {
      timeout: 180_000,
    }).then(r => r.data),
  checkValue: (payload: ValueCheckPayload) =>
    api.post<ValueCheckResult>('/matches/value', payload).then(r => r.data),
  h2h: (homeApiId: number, awayApiId: number, limit = 3) =>
    api.get<import('../types').H2HMatch[]>('/matches/h2h', {
      params: { home_api_id: homeApiId, away_api_id: awayApiId, limit },
      timeout: 45_000,
    }).then(r => r.data),
  details: (m: import('../types').MatchRef) =>
    api.get<import('../types').MatchDetails>('/matches/details', {
      params: {
        date: m.date,
        home: m.home_name,
        away: m.away_name,
        competition_code: m.competition_code ?? undefined,
      },
      timeout: 45_000,
    }).then(r => r.data),
}

export const fixturesApi = {
  upcoming: (days: number = 7, leagueIds: number[] = []) =>
    api.get<import('../types/fixtures').UpcomingFixture[]>('/fixtures/upcoming', {
      params: {
        days,
        league_ids: leagueIds.length ? leagueIds.join(',') : undefined,
      },
    }).then(r => r.data),
}

export const playersApi = {
  updateMetrics: (
    playerId: number,
    data: { goal_contribution_pct?: number; sca?: number; xg_assisted?: number; is_available?: boolean }
  ) => api.put<Player>(`/players/${playerId}/metrics`, data).then(r => r.data),
}

export default api
