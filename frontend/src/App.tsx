import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { MatchAnalysis, Team, AbsentPlayer } from './types'
import { matchesApi } from './lib/api'
import MatchSelector from './pages/MatchSelector'
import AnalysisDashboard from './pages/AnalysisDashboard'

type View = 'selector' | 'dashboard'

export default function App() {
  const [view, setView] = useState<View>('selector')
  const [analysis, setAnalysis] = useState<MatchAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Erro ao calcular. Verifique se o backend está rodando.'
        : 'Erro ao calcular. Verifique se o backend está rodando.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-900">
      <div className="max-w-2xl mx-auto px-4 pb-12">
        <AnimatePresence mode="wait">
          {view === 'selector' && (
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
        </AnimatePresence>
      </div>
    </div>
  )
}
