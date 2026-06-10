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

export const leaguesApi = {
  list: () => api.get<League[]>('/leagues/').then(r => r.data),
  get: (id: number) => api.get<League>(`/leagues/${id}`).then(r => r.data),
  refresh: (apiId: number) => api.post<League>(`/leagues/${apiId}/refresh`).then(r => r.data),
}

export const teamsApi = {
  byLeague: (leagueId: number) =>
    api.get<Team[]>(`/teams/league/${leagueId}`).then(r => r.data),
  get: (id: number) => api.get<Team>(`/teams/${id}`).then(r => r.data),
  players: (teamId: number) =>
    api.get<Player[]>(`/teams/${teamId}/players`).then(r => r.data),
}

export const matchesApi = {
  calculate: (payload: CalculateMatchPayload) =>
    api.post<MatchAnalysis>('/matches/calculate', payload).then(r => r.data),
  checkValue: (payload: ValueCheckPayload) =>
    api.post<ValueCheckResult>('/matches/value', payload).then(r => r.data),
}

export const playersApi = {
  updateMetrics: (
    playerId: number,
    data: { goal_contribution_pct?: number; sca?: number; xg_assisted?: number; is_available?: boolean }
  ) => api.put<Player>(`/players/${playerId}/metrics`, data).then(r => r.data),
}

export default api
