import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Search, CalendarDays } from 'lucide-react'
import type { MatchAnalysis, Team, AbsentPlayer } from './types'
import { matchesApi } from './lib/api'
import { useToast } from './lib/toast'
import MatchSelector from './pages/MatchSelector'
import AnalysisDashboard from './pages/AnalysisDashboard'
import UpcomingFixtures from './pages/UpcomingFixtures'
import Login from './pages/Login'

type Tab = 'analyse' | 'fixtures'
type View = 'selector' | 'dashboard'

function useAuth() {
  const [token, setToken] = useState(() => localStorage.getItem('morebet_token') ?? '')
  const [email, setEmail] = useState(() => localStorage.getItem('morebet_email') ?? '')

  function login(t: string, e: string) {
    localStorage.setItem('morebet_token', t)
    localStorage.setItem('morebet_email', e)
    setToken(t)
    setEmail(e)
  }

  function logout() {
    localStorage.removeItem('morebet_token')
    localStorage.removeItem('morebet_email')
    setToken('')
    setEmail('')
  }

  return { token, email, login, logout }
}

export default function App() {
  const { token, email, login, logout } = useAuth()
  const toast = useToast()
  const [tab, setTab] = useState<Tab>('analyse')
  const [view, setView] = useState<View>('selector')
  const [analysis, setAnalysis] = useState<MatchAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!token) return <Login onLogin={login} />

  // Called from UpcomingFixtures with just home+away (no absences, default xg)
  async function handleQuickAnalyse(homeTeam: Team, awayTeam: Team) {
    setTab('analyse')
    await handleAnalyse(homeTeam, awayTeam, [], [], 0.4)
  }

  async function handleAnalyse(
    homeTeam: Team,
    awayTeam: Team,
    absentHome: AbsentPlayer[],
    absentAway: AbsentPlayer[],
    xgWeight: number,
  ) {
    setLoading(true)
    setError('')
    try {
      const result = await matchesApi.calculate({
        home_team_id: homeTeam.id,
        away_team_id: awayTeam.id,
        absent_home: absentHome,
        absent_away: absentAway,
        xg_weight: xgWeight,
      })
      setAnalysis(result)
      setView('dashboard')
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          ?? 'Erro ao calcular. Verifique se o backend está rodando.'
        : 'Erro ao calcular. Verifique se o backend está rodando.'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-900">
      {/* Top bar with user info */}
      <div className="border-b border-surface-700 bg-surface-800/60 backdrop-blur sticky top-0 z-20">
        <div className="max-w-2xl mx-auto px-4 py-2 flex items-center justify-between">
          <span className="text-xs text-surface-400">{email}</span>
          <button onClick={logout} className="text-xs text-surface-400 hover:text-white transition-colors">
            Sair
          </button>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 pb-12">
        {/* Tab navigation — hidden when dashboard is open */}
        {view !== 'dashboard' && (
          <div className="flex gap-1 mt-4 p-1 bg-surface-800 rounded-xl border border-surface-700">
            {([
              { id: 'analyse' as Tab, icon: Search,       label: 'Analisar Jogo'  },
              { id: 'fixtures' as Tab, icon: CalendarDays, label: 'Próximos Jogos' },
            ] as const).map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm
                            font-medium transition-all ${
                  tab === id
                    ? 'bg-brand-500 text-white shadow-sm'
                    : 'text-surface-400 hover:text-white'
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>
        )}

        <AnimatePresence mode="wait">
          {tab === 'analyse' && view === 'selector' && (
            <motion.div
              key="selector"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.25 }}
            >
              <MatchSelector onAnalyse={handleAnalyse} loading={loading} />
              {error && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-3 text-sm text-red-400 text-center"
                >
                  {error}
                </motion.p>
              )}
            </motion.div>
          )}

          {view === 'dashboard' && analysis && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
            >
              <AnalysisDashboard
                analysis={analysis}
                onBack={() => setView('selector')}
              />
            </motion.div>
          )}

          {tab === 'fixtures' && view !== 'dashboard' && (
            <motion.div
              key="fixtures"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
            >
              <UpcomingFixtures onAnalyse={handleQuickAnalyse} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
