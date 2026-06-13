import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Clock, CheckCircle2 } from 'lucide-react'
import type { League, Team } from '../types'
import { leaguesApi } from '../lib/api'
import { useToast } from '../lib/toast'
import Spinner from '../components/Spinner'
import BacktestPanel from '../components/BacktestPanel'
import LeagueStandings from '../components/LeagueStandings'
import LeagueFixtures from '../components/LeagueFixtures'

const LEAGUE_STORAGE_KEY = 'morebet_league_api'

function relativeAge(iso: string | null): { label: string; stale: boolean } {
  if (!iso) return { label: 'nunca atualizado', stale: true }
  const ageMs = Date.now() - new Date(iso).getTime()
  const hours = ageMs / 3_600_000
  if (hours < 1) return { label: `há ${Math.max(1, Math.round(ageMs / 60_000))} min`, stale: false }
  if (hours < 24) return { label: `há ${Math.round(hours)}h`, stale: false }
  const days = Math.round(hours / 24)
  return { label: `há ${days}d`, stale: days >= 3 }
}

interface Props {
  /** Open the analysis for a chosen matchup (defaults: no absences, 40% xG). */
  onAnalyse: (homeTeam: Team, awayTeam: Team) => void
}

export default function MatchSelector({ onAnalyse }: Props) {
  const [leagues, setLeagues] = useState<League[]>([])
  const [selectedLeague, setSelectedLeague] = useState<League | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshingAll, setRefreshingAll] = useState(false)
  const [refreshAllMsg, setRefreshAllMsg] = useState('')
  const [leaguesError, setLeaguesError] = useState('')
  const toast = useToast()

  // Load leagues and restore the last-selected one (survives page refresh).
  useEffect(() => {
    leaguesApi.list()
      .then(ls => {
        setLeagues(ls)
        const savedApi = Number(localStorage.getItem(LEAGUE_STORAGE_KEY) || '')
        const saved = ls.find(l => l.api_id === savedApi)
        if (saved) setSelectedLeague(saved)
      })
      .catch(() => setLeaguesError('Sem dados. Atualize as ligas primeiro.'))
  }, [])

  function selectLeague(l: League) {
    setSelectedLeague(l)
    localStorage.setItem(LEAGUE_STORAGE_KEY, String(l.api_id))
  }

  async function handleRefresh() {
    if (!selectedLeague) return
    setRefreshing(true)
    try {
      const updated = await leaguesApi.refresh(selectedLeague.api_id)
      setSelectedLeague(updated)
      setLeagues(prev => prev.map(l => (l.id === updated.id ? updated : l)))
      toast.success(`${updated.name} atualizada.`)
    } catch {
      toast.error('Falha ao atualizar a liga.')
    } finally {
      setRefreshing(false)
    }
  }

  async function handleRefreshAll() {
    setRefreshingAll(true)
    setRefreshAllMsg('')
    try {
      const { results } = await leaguesApi.refreshAll()
      const ok = results.filter(r => r.startsWith('OK')).length
      const fail = results.length - ok
      const summary = fail === 0 ? `Todas as ${ok} ligas atualizadas.` : `${ok} OK · ${fail} com erro.`
      setRefreshAllMsg(summary)
      fail === 0 ? toast.success(summary) : toast.info(summary)
      const fresh = await leaguesApi.list()
      setLeagues(fresh)
      if (selectedLeague) {
        const updated = fresh.find(l => l.id === selectedLeague.id)
        if (updated) setSelectedLeague(updated)
      }
    } catch {
      const msg = 'Falha ao atualizar — verifique a chave do provedor.'
      setRefreshAllMsg(msg)
      toast.error(msg)
    } finally {
      setRefreshingAll(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center pt-6 pb-1"
      >
        <h1 className="text-2xl font-bold text-white mb-1">Análise de partida</h1>
        <p className="text-surface-400 text-sm">
          Escolha a liga e toque em um próximo jogo — o modelo calcula probabilidades, odds justas e valor
        </p>
      </motion.div>

      {/* Liga */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="card space-y-3"
      >
        <div className="flex items-center justify-between flex-wrap gap-2">
          <p className="label flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-brand-500/20 text-brand-300 grid place-items-center text-[11px] font-bold normal-case">1</span>
            Escolha a liga
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefreshAll}
              disabled={refreshingAll || refreshing}
              title="Atualiza todas as ligas suportadas (~30s)"
              className="btn-ghost text-xs flex items-center gap-1.5 py-1.5"
            >
              {refreshingAll ? <Spinner size={14} /> : <RefreshCw size={14} />}
              Atualizar todas
            </button>
            {selectedLeague && (
              <button
                onClick={handleRefresh}
                disabled={refreshing || refreshingAll}
                className="btn-ghost text-xs flex items-center gap-1.5 py-1.5"
              >
                {refreshing ? <Spinner size={14} /> : <RefreshCw size={14} />}
                Apenas esta liga
              </button>
            )}
          </div>
        </div>
        {refreshAllMsg && (
          <p className="text-xs text-surface-300 flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-brand-400" /> {refreshAllMsg}
          </p>
        )}

        {leaguesError && !leagues.length && (
          <p className="text-xs text-yellow-400">{leaguesError}</p>
        )}

        {leagues.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {leagues.map(l => {
              const active = selectedLeague?.id === l.id
              return (
                <button
                  key={l.id}
                  onClick={() => selectLeague(l)}
                  className={`flex flex-col items-center justify-center gap-1.5 p-2.5 rounded-lg border
                              transition-all text-center min-h-[78px] ${
                    active
                      ? 'bg-brand-500/15 border-brand-500/60'
                      : 'bg-surface-700 border-surface-600 hover:border-surface-500'
                  }`}
                >
                  {l.logo_url ? (
                    <img src={l.logo_url} alt={l.name} className="w-7 h-7 object-contain" />
                  ) : (
                    <span className="w-7 h-7 grid place-items-center text-xs text-surface-400 bg-surface-800 rounded-full">
                      {l.country.slice(0, 2)}
                    </span>
                  )}
                  <span className={`text-[11px] font-medium leading-tight line-clamp-2 ${active ? 'text-white' : 'text-surface-300'}`}>
                    {l.name}
                  </span>
                </button>
              )
            })}
          </div>
        ) : (
          <div className="relative">
            <select disabled className="select-field pr-8 opacity-60">
              <option>Nenhuma liga carregada — clique em "Atualizar todas"</option>
            </select>
          </div>
        )}

        {selectedLeague?.home_goals_avg && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-surface-400">
            <span>
              MGM: <strong className="text-white">{selectedLeague.home_goals_avg.toFixed(2)}</strong>
              {' '}· MGV: <strong className="text-white">{selectedLeague.away_goals_avg?.toFixed(2)}</strong>
              {' '}· {selectedLeague.total_matches} jogos
            </span>
            {(() => {
              const age = relativeAge(selectedLeague.last_updated)
              return (
                <span className={`flex items-center gap-1 ${age.stale ? 'text-yellow-400' : 'text-surface-500'}`}>
                  <Clock size={11} /> atualizado {age.label}
                </span>
              )
            })()}
          </div>
        )}

        {selectedLeague && (
          <BacktestPanel
            key={selectedLeague.id}
            leagueApiId={selectedLeague.api_id}
            leagueName={selectedLeague.name}
          />
        )}
      </motion.div>

      {/* Classificação + próximos jogos da liga escolhida */}
      {selectedLeague && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
          <LeagueStandings key={`st-${selectedLeague.id}`} leagueApiId={selectedLeague.api_id} />
          <LeagueFixtures
            key={`fx-${selectedLeague.id}`}
            leagueApiId={selectedLeague.api_id}
            onAnalyse={onAnalyse}
          />
        </div>
      )}
    </div>
  )
}
