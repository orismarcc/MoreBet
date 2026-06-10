import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ChevronRight, RefreshCw, Swords } from 'lucide-react'
import type { League, Team, AbsentPlayer } from '../types'
import { leaguesApi, teamsApi } from '../lib/api'
import PlayerAbsenceSelector from '../components/PlayerAbsenceSelector'
import Spinner from '../components/Spinner'

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
  const [leaguesError, setLeaguesError] = useState('')

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
      await leaguesApi.refresh(selectedLeague.api_id)
      const updated = await teamsApi.byLeague(selectedLeague.id)
      setTeams(updated)
    } finally {
      setRefreshing(false)
    }
  }

  const canAnalyse = homeTeam && awayTeam && homeTeam.id !== awayTeam.id && !loading

  return (
    <div className="space-y-5">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center pt-6 pb-2"
      >
        <h1 className="text-3xl font-bold text-white mb-1">
          More<span className="text-brand-500">Bet</span>
        </h1>
        <p className="text-surface-400 text-sm">
          Precificação avançada de odds · Modelo Poisson + xG
        </p>
      </motion.div>

      {/* Liga */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="card space-y-3"
      >
        <div className="flex items-center justify-between">
          <p className="label">Liga</p>
          {selectedLeague && (
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="btn-ghost text-xs flex items-center gap-1.5 py-1.5"
            >
              {refreshing ? <Spinner size={14} /> : <RefreshCw size={14} />}
              Atualizar dados
            </button>
          )}
        </div>

        {leaguesError && !leagues.length ? (
          <div className="space-y-2">
            <p className="text-xs text-yellow-400">{leaguesError}</p>
            <p className="text-xs text-surface-400">
              Use o botão "Atualizar dados" após selecionar uma liga para carregar os times via API-Football.
            </p>
          </div>
        ) : null}

        <div className="relative">
          <select
            value={selectedLeague?.id ?? ''}
            onChange={e => {
              const league = leagues.find(l => l.id === Number(e.target.value)) ?? null
              setSelectedLeague(league)
              setHomeTeam(null)
              setAwayTeam(null)
            }}
            className="select-field pr-8"
          >
            <option value="">Selecione uma liga...</option>
            {leagues.map(l => (
              <option key={l.id} value={l.id}>
                {l.name} ({l.country}) — {l.season}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-surface-400">▾</div>
        </div>

        {selectedLeague?.home_goals_avg && (
          <p className="text-xs text-surface-400">
            Médias da liga · MGM: <strong className="text-white">{selectedLeague.home_goals_avg.toFixed(2)}</strong>
            {' '}· MGV: <strong className="text-white">{selectedLeague.away_goals_avg?.toFixed(2)}</strong>
            {' '}· {selectedLeague.total_matches} jogos analisados
          </p>
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
          <p className="label">Times</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-center">
            <div className="relative">
              <label className="text-xs text-surface-400 mb-1 block">Mandante</label>
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
              <div className="pointer-events-none absolute right-3 bottom-2.5 text-surface-400">▾</div>
            </div>

            <div className="flex items-end gap-3">
              <div className="flex-1 relative">
                <label className="text-xs text-surface-400 mb-1 block">Visitante</label>
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
                <div className="pointer-events-none absolute right-3 bottom-2.5 text-surface-400">▾</div>
              </div>
            </div>
          </div>

          {homeTeam && awayTeam && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center justify-center gap-3 py-2"
            >
              <span className="font-semibold text-white">{homeTeam.name}</span>
              <Swords size={18} className="text-brand-500" />
              <span className="font-semibold text-white">{awayTeam.name}</span>
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
