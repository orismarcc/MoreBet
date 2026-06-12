import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ChevronRight, RefreshCw, Swords, Clock, CheckCircle2 } from 'lucide-react'
import type { League, Team, AbsentPlayer } from '../types'
import { leaguesApi, teamsApi } from '../lib/api'
import { useToast } from '../lib/toast'
import PlayerAbsenceSelector from '../components/PlayerAbsenceSelector'
import Spinner from '../components/Spinner'
import BacktestPanel from '../components/BacktestPanel'

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
  onAnalyse: (
    homeTeam: Team,
    awayTeam: Team,
    absentHome: AbsentPlayer[],
    absentAway: AbsentPlayer[],
    xgWeight: number,
  ) => void
  loading: boolean
}

export default function MatchSelector({ onAnalyse, loading }: Props) {
  const [leagues, setLeagues] = useState<League[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [selectedLeague, setSelectedLeague] = useState<League | null>(null)
  const [homeTeam, setHomeTeam] = useState<Team | null>(null)
  const [awayTeam, setAwayTeam] = useState<Team | null>(null)
  const [absentHome, setAbsentHome] = useState<AbsentPlayer[]>([])
  const [absentAway, setAbsentAway] = useState<AbsentPlayer[]>([])
  const [xgWeight, setXgWeight] = useState(0.4)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshingAll, setRefreshingAll] = useState(false)
  const [refreshAllMsg, setRefreshAllMsg] = useState('')
  const [leaguesError, setLeaguesError] = useState('')
  const toast = useToast()

  useEffect(() => {
    leaguesApi.list()
      .then(setLeagues)
      .catch(() => setLeaguesError('Sem dados. Faça um refresh de liga primeiro.'))
  }, [])

  useEffect(() => {
    if (!selectedLeague) { setTeams([]); return }
    teamsApi.byLeague(selectedLeague.id).then(setTeams).catch(() => setTeams([]))
  }, [selectedLeague])

  async function handleRefresh() {
    if (!selectedLeague) return
    setRefreshing(true)
    try {
      const updatedLeague = await leaguesApi.refresh(selectedLeague.api_id)
      setSelectedLeague(updatedLeague)
      setLeagues(prev => prev.map(l => (l.id === updatedLeague.id ? updatedLeague : l)))
      const updatedTeams = await teamsApi.byLeague(selectedLeague.id)
      setTeams(updatedTeams)
      toast.success(`${updatedLeague.name} atualizada.`)
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
      const summary = fail === 0
        ? `Todas as ${ok} ligas atualizadas.`
        : `${ok} OK · ${fail} com erro.`
      setRefreshAllMsg(summary)
      if (fail === 0) toast.success(summary)
      else toast.info(summary)
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

  const canAnalyse = homeTeam && awayTeam && homeTeam.id !== awayTeam.id && !loading

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
          Escolha a liga e os times — o modelo Poisson calcula probabilidades e odds justas
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
              title="Atualiza todas as 8 ligas suportadas (~30s)"
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

        {leaguesError && !leagues.length ? (
          <div className="space-y-2">
            <p className="text-xs text-yellow-400">{leaguesError}</p>
            <p className="text-xs text-surface-400">
              Use o botão "Atualizar dados" após selecionar uma liga para carregar os times via API-Football.
            </p>
          </div>
        ) : null}

        {/* League picker — visual grid with crests, falls back to select on tiny screens */}
        {leagues.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {leagues.map(l => {
              const active = selectedLeague?.id === l.id
              return (
                <button
                  key={l.id}
                  onClick={() => {
                    setSelectedLeague(l); setHomeTeam(null); setAwayTeam(null)
                  }}
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

      {/* Times */}
      {selectedLeague && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="card space-y-3"
        >
          <p className="label flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-brand-500/20 text-brand-300 grid place-items-center text-[11px] font-bold normal-case">2</span>
            Defina o confronto
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Mandante</label>
              <div className="flex items-center gap-2">
                {homeTeam?.logo_url && (
                  <img src={homeTeam.logo_url} alt="" className="w-8 h-8 object-contain flex-shrink-0" />
                )}
                <div className="relative flex-1">
                  <select
                    value={homeTeam?.id ?? ''}
                    onChange={e => setHomeTeam(teams.find(t => t.id === Number(e.target.value)) ?? null)}
                    className="select-field pr-8"
                  >
                    <option value="">Selecione o mandante...</option>
                    {teams.filter(t => t.id !== awayTeam?.id).map(t => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-surface-400">▾</div>
                </div>
              </div>
            </div>

            <div>
              <label className="text-xs text-surface-400 mb-1 block">Visitante</label>
              <div className="flex items-center gap-2">
                {awayTeam?.logo_url && (
                  <img src={awayTeam.logo_url} alt="" className="w-8 h-8 object-contain flex-shrink-0" />
                )}
                <div className="relative flex-1">
                  <select
                    value={awayTeam?.id ?? ''}
                    onChange={e => setAwayTeam(teams.find(t => t.id === Number(e.target.value)) ?? null)}
                    className="select-field pr-8"
                  >
                    <option value="">Selecione o visitante...</option>
                    {teams.filter(t => t.id !== homeTeam?.id).map(t => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-surface-400">▾</div>
                </div>
              </div>
            </div>
          </div>

          {homeTeam && awayTeam && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center justify-center gap-3 py-2"
            >
              {homeTeam.logo_url && <img src={homeTeam.logo_url} alt="" className="w-6 h-6 object-contain" />}
              <span className="font-semibold text-white">{homeTeam.name}</span>
              <Swords size={18} className="text-brand-500" />
              <span className="font-semibold text-white">{awayTeam.name}</span>
              {awayTeam.logo_url && <img src={awayTeam.logo_url} alt="" className="w-6 h-6 object-contain" />}
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Desfalques */}
      {homeTeam && awayTeam && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          <PlayerAbsenceSelector
            teamId={homeTeam.id}
            teamName={homeTeam.name}
            onAbsentChange={setAbsentHome}
          />
          <PlayerAbsenceSelector
            teamId={awayTeam.id}
            teamName={awayTeam.name}
            onAbsentChange={setAbsentAway}
          />
        </motion.div>
      )}

      {/* xG Weight */}
      {homeTeam && awayTeam && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="card space-y-2"
        >
          <div className="flex items-center justify-between">
            <label className="label">Peso do xG no cálculo</label>
            <span className="text-sm font-mono text-brand-400">{Math.round(xgWeight * 100)}%</span>
          </div>
          <input
            type="range"
            min={0} max={1} step={0.1}
            value={xgWeight}
            onChange={e => setXgWeight(Number(e.target.value))}
            className="w-full accent-brand-500 cursor-pointer"
          />
          <p className="text-xs text-surface-400">
            {xgWeight === 0 && 'Usando apenas gols reais (sem xG).'}
            {xgWeight > 0 && xgWeight < 1 && `${Math.round((1 - xgWeight) * 100)}% gols reais + ${Math.round(xgWeight * 100)}% xG — remove ruído de partidas com sorte.`}
            {xgWeight === 1 && 'Usando apenas xG (ignora gols reais).'}
          </p>
        </motion.div>
      )}

      {/* CTA */}
      {homeTeam && awayTeam && (
        <motion.button
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => onAnalyse(homeTeam, awayTeam, absentHome, absentAway, xgWeight)}
          disabled={!canAnalyse}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
        >
          {loading ? (
            <><Spinner size={20} /> Calculando...</>
          ) : (
            <>Calcular Odds Justas <ChevronRight size={20} /></>
          )}
        </motion.button>
      )}
    </div>
  )
}
