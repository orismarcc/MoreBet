import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CalendarDays, LogOut, Search, TrendingUp, Users } from 'lucide-react'
import type { MatchAnalysis, Team, AbsentPlayer, TeamSearchResult } from './types'
import { matchesApi } from './lib/api'
import { useToast } from './lib/toast'
import MatchSelector from './pages/MatchSelector'
import AnalysisDashboard from './pages/AnalysisDashboard'
import UpcomingFixtures from './pages/UpcomingFixtures'
import TeamExplorer from './pages/TeamExplorer'
import Login from './pages/Login'

type Page = 'analyse' | 'fixtures' | 'teams'
type View = 'selector' | 'dashboard'

const NAV = [
  { id: 'analyse' as Page,  icon: Search,       label: 'Análise' },
  { id: 'fixtures' as Page, icon: CalendarDays, label: 'Jogos' },
  { id: 'teams' as Page,    icon: Users,        label: 'Times' },
]

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
  // Active page persists across refresh so a reload keeps you where you were.
  const [page, setPage] = useState<Page>(() => {
    const saved = localStorage.getItem('morebet_page')
    return saved === 'fixtures' || saved === 'teams' || saved === 'analyse' ? saved : 'analyse'
  })
  const [view, setView] = useState<View>('selector')
  const [analysis, setAnalysis] = useState<MatchAnalysis | null>(null)
  // A team to open on the Times page (set when a standings row is clicked).
  const [teamToOpen, setTeamToOpen] = useState<TeamSearchResult | null>(null)

  if (!token) return <Login onLogin={login} />

  function navigate(p: Page) {
    setPage(p)
    localStorage.setItem('morebet_page', p)
    if (p !== 'analyse') setView('selector')
  }

  // Open a team's full profile on the Times page (from a standings click).
  function openTeam(team: TeamSearchResult) {
    setTeamToOpen(team)
    navigate('teams')
  }

  // Jump to a league's standings/fixtures on the Análise page (from a
  // competition chip on a team profile).
  function openLeague(apiId: number) {
    localStorage.setItem('morebet_league_api', String(apiId))
    setView('selector')
    navigate('analyse')
  }

  // Chamado de fixtures/standings/times com apenas mandante+visitante
  async function handleQuickAnalyse(homeTeam: Team, awayTeam: Team) {
    setPage('analyse')
    localStorage.setItem('morebet_page', 'analyse')
    await handleAnalyse(homeTeam, awayTeam, [], [], 0.4)
  }

  async function handleAnalyse(
    homeTeam: Team,
    awayTeam: Team,
    absentHome: AbsentPlayer[],
    absentAway: AbsentPlayer[],
    xgWeight: number,
  ) {
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
      window.scrollTo({ top: 0 })
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          ?? 'Erro ao calcular. Tente novamente.'
        : 'Erro ao calcular. Tente novamente.'
      toast.error(msg)
    }
  }

  const showDashboard = page === 'analyse' && view === 'dashboard' && analysis

  return (
    <div className="min-h-screen bg-surface-900">
      {/* ── Header ── */}
      <header className="border-b border-surface-600/60 bg-surface-800/70 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-4">
          {/* Logo */}
          <button
            onClick={() => { navigate('analyse'); setView('selector') }}
            className="flex items-center gap-2 flex-shrink-0"
            aria-label="Ir para o início"
          >
            <span className="w-8 h-8 rounded-xl bg-brand-500/20 border border-brand-500/30 grid place-items-center">
              <TrendingUp size={16} className="text-brand-400" />
            </span>
            <span className="font-bold text-white text-lg tracking-tight">
              More<span className="text-brand-400">Bet</span>
            </span>
          </button>

          {/* Nav desktop */}
          <nav className="hidden md:flex items-center gap-1 ml-4">
            {NAV.map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                onClick={() => navigate(id)}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-sm font-medium
                            transition-all ${
                  page === id
                    ? 'bg-brand-500/15 text-brand-300'
                    : 'text-surface-400 hover:text-white hover:bg-surface-700'
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </nav>

          {/* Usuário */}
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden sm:block text-xs text-surface-400 truncate max-w-[180px]">{email}</span>
            <button
              onClick={logout}
              title="Sair"
              aria-label="Sair"
              className="text-surface-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-surface-700"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      {/* ── Conteúdo ── */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pb-24 md:pb-12">
        <AnimatePresence mode="wait">
          {page === 'analyse' && view === 'selector' && (
            <motion.div
              key="selector"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22 }}
            >
              <MatchSelector onAnalyse={handleQuickAnalyse} onOpenTeam={openTeam} />
            </motion.div>
          )}

          {showDashboard && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22 }}
            >
              <AnalysisDashboard
                analysis={analysis!}
                onBack={() => setView('selector')}
              />
            </motion.div>
          )}

          {page === 'fixtures' && (
            <motion.div
              key="fixtures"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22 }}
              className="max-w-3xl mx-auto"
            >
              <UpcomingFixtures onAnalyse={handleQuickAnalyse} />
            </motion.div>
          )}

          {page === 'teams' && (
            <motion.div
              key="teams"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22 }}
            >
              <TeamExplorer
                onAnalyse={handleQuickAnalyse}
                initialTeam={teamToOpen}
                onConsumed={() => setTeamToOpen(null)}
                onOpenLeague={openLeague}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* ── Bottom nav (mobile) ── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-surface-800/95 backdrop-blur-md
                   border-t border-surface-600/60 pb-[env(safe-area-inset-bottom)]"
        aria-label="Navegação principal"
      >
        <div className="grid grid-cols-3 h-16">
          {NAV.map(({ id, icon: Icon, label }) => {
            const active = page === id
            return (
              <button
                key={id}
                onClick={() => navigate(id)}
                className="flex flex-col items-center justify-center gap-1 relative"
              >
                {active && (
                  <motion.span
                    layoutId="bottomnav-pill"
                    className="absolute top-0 h-0.5 w-10 rounded-full bg-brand-400"
                  />
                )}
                <Icon size={19} className={active ? 'text-brand-400' : 'text-surface-400'} />
                <span className={`text-[11px] font-medium ${active ? 'text-brand-300' : 'text-surface-400'}`}>
                  {label}
                </span>
              </button>
            )
          })}
        </div>
      </nav>
    </div>
  )
}
