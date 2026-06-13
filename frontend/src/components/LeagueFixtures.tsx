import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CalendarClock, ChevronRight, Home, Plane } from 'lucide-react'
import type { Team } from '../types'
import type { UpcomingFixture } from '../types/fixtures'
import { fixturesApi, teamsApi } from '../lib/api'
import Spinner from './Spinner'

interface Props {
  leagueApiId: number
  onAnalyse: (home: Team, away: Team) => void | Promise<void>
}

function dayLabel(iso: string) {
  return new Date(iso).toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' })
}
function timeLabel(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export default function LeagueFixtures({ leagueApiId, onAnalyse }: Props) {
  const [fixtures, setFixtures] = useState<UpcomingFixture[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<number | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true); setFixtures(null)
    fixturesApi.upcoming(14, [leagueApiId])
      .then(f => { if (alive) setFixtures(f) })
      .catch(() => { if (alive) setFixtures([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [leagueApiId])

  async function open(f: UpcomingFixture) {
    if (!f.home_db_id || !f.away_db_id) return
    setBusy(f.fixture_id)
    try {
      const [home, away] = await Promise.all([
        teamsApi.get(f.home_db_id), teamsApi.get(f.away_db_id),
      ])
      await onAnalyse(home, away)
    } finally {
      setBusy(null)
    }
  }

  const shown = (fixtures ?? []).slice(0, 8)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
    >
      <div className="section-title mb-1">
        <CalendarClock size={16} className="text-brand-400" />
        <h3>Próximos jogos</h3>
        <span className="text-xs text-surface-400 font-normal">· toque para analisar</span>
      </div>

      {loading && <div className="flex justify-center py-6"><Spinner size={22} /></div>}

      {!loading && shown.length === 0 && (
        <p className="text-xs text-surface-400 py-3">
          Nenhum jogo agendado nos próximos 14 dias para esta liga.
        </p>
      )}

      {!loading && shown.length > 0 && (
        <div className="divide-y divide-surface-700/60 mt-1">
          {shown.map(f => {
            const canAnalyse = !!f.home_db_id && !!f.away_db_id
            const isBusy = busy === f.fixture_id
            return (
              <button
                key={f.fixture_id}
                onClick={() => open(f)}
                disabled={!canAnalyse || isBusy}
                title={canAnalyse ? 'Analisar este confronto' : 'Sem dados de força para ambos os times ainda'}
                className={`w-full flex items-center gap-2.5 py-2.5 text-left transition-colors rounded-lg px-1 -mx-1 ${
                  canAnalyse ? 'hover:bg-surface-700/40 group' : 'opacity-60 cursor-not-allowed'
                }`}
              >
                <div className="flex flex-col items-center w-11 flex-shrink-0">
                  <span className="text-[10px] text-surface-400 leading-tight">{dayLabel(f.match_date)}</span>
                  <span className="text-sm font-mono font-semibold text-white tabular-nums">{timeLabel(f.match_date)}</span>
                </div>
                <div className="w-px self-stretch bg-surface-600/70 flex-shrink-0" />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <Home size={11} className="text-surface-500 flex-shrink-0" />
                    {f.home_team_logo && <img src={f.home_team_logo} alt="" className="w-4 h-4 object-contain flex-shrink-0" />}
                    <span className="text-sm text-white truncate">{f.home_team_name}</span>
                  </div>
                  <div className="flex items-center gap-2 min-w-0">
                    <Plane size={11} className="text-surface-500 flex-shrink-0" />
                    {f.away_team_logo && <img src={f.away_team_logo} alt="" className="w-4 h-4 object-contain flex-shrink-0" />}
                    <span className="text-sm text-white truncate">{f.away_team_name}</span>
                  </div>
                </div>
                {isBusy
                  ? <Spinner size={14} />
                  : canAnalyse
                  ? <ChevronRight size={16} className="text-surface-500 group-hover:text-brand-400 transition-colors flex-shrink-0" />
                  : <span className="text-[10px] text-surface-500 flex-shrink-0">sem dados</span>}
              </button>
            )
          })}
        </div>
      )}
    </motion.div>
  )
}
