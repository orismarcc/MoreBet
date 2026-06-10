import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Calendar, ChevronRight, Filter, RefreshCw, Search } from 'lucide-react'
import type { UpcomingFixture } from '../types/fixtures'
import type { Team } from '../types'
import { fixturesApi, teamsApi } from '../lib/api'
import Spinner from '../components/Spinner'

interface Props {
  onAnalyse: (homeTeam: Team, awayTeam: Team) => void
}

const LEAGUE_OPTIONS = [
  { id: 39,  name: 'Premier League',    flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿' },
  { id: 140, name: 'La Liga',           flag: '🇪🇸' },
  { id: 135, name: 'Serie A',           flag: '🇮🇹' },
  { id: 78,  name: 'Bundesliga',        flag: '🇩🇪' },
  { id: 61,  name: 'Ligue 1',           flag: '🇫🇷' },
  { id: 71,  name: 'Brasileirão',       flag: '🇧🇷' },
  { id: 94,  name: 'Primeira Liga',     flag: '🇵🇹' },
  { id: 88,  name: 'Eredivisie',        flag: '🇳🇱' },
]

function formatDate(iso: string) {
  const d = new Date(iso)
  return {
    date: d.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' }),
    time: d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
  }
}

function groupByDate(fixtures: UpcomingFixture[]) {
  const groups: Record<string, UpcomingFixture[]> = {}
  for (const f of fixtures) {
    const key = new Date(f.match_date).toLocaleDateString('pt-BR', {
      weekday: 'long', day: '2-digit', month: 'long',
    })
    if (!groups[key]) groups[key] = []
    groups[key].push(f)
  }
  return groups
}

export default function UpcomingFixtures({ onAnalyse }: Props) {
  const [fixtures, setFixtures] = useState<UpcomingFixture[]>([])
  const [loading, setLoading] = useState(false)
  const [days, setDays] = useState(7)
  const [selectedLeagues, setSelectedLeagues] = useState<Set<number>>(new Set())
  const [search, setSearch] = useState('')
  const [loadingAnalysis, setLoadingAnalysis] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    try {
      const data = await fixturesApi.upcoming(days, [...selectedLeagues])
      setFixtures(data)
    } catch {
      setFixtures([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [days, selectedLeagues])

  function toggleLeague(id: number) {
    setSelectedLeagues(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return fixtures
    const q = search.toLowerCase()
    return fixtures.filter(f =>
      f.home_team_name.toLowerCase().includes(q) ||
      f.away_team_name.toLowerCase().includes(q) ||
      f.league_name.toLowerCase().includes(q)
    )
  }, [fixtures, search])

  const grouped = groupByDate(filtered)

  async function handleAnalyse(f: UpcomingFixture) {
    if (!f.home_db_id || !f.away_db_id) return
    setLoadingAnalysis(f.fixture_id)
    try {
      const [home, away] = await Promise.all([
        teamsApi.get(f.home_db_id),
        teamsApi.get(f.away_db_id),
      ])
      onAnalyse(home, away)
    } finally {
      setLoadingAnalysis(null)
    }
  }

  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar size={18} className="text-brand-500" />
          <h2 className="font-semibold text-white">Próximos Jogos</h2>
        </div>
        <button onClick={load} disabled={loading} className="btn-ghost py-1.5 px-3 flex items-center gap-1.5 text-xs">
          {loading ? <Spinner size={13} /> : <RefreshCw size={13} />}
          Atualizar
        </button>
      </div>

      {/* Filters */}
      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-surface-400" />
          <span className="label">Filtros</span>
        </div>

        {/* Days */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-400 w-20">Próximos</span>
          <div className="flex gap-1">
            {[3, 5, 7, 10, 14].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  days === d
                    ? 'bg-brand-500 text-white'
                    : 'bg-surface-700 text-surface-400 hover:text-white'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {/* Leagues */}
        <div>
          <span className="text-xs text-surface-400 block mb-2">Competições (vazio = todas)</span>
          <div className="flex flex-wrap gap-1.5">
            {LEAGUE_OPTIONS.map(l => (
              <button
                key={l.id}
                onClick={() => toggleLeague(l.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs
                            font-medium transition-all border ${
                  selectedLeagues.has(l.id)
                    ? 'bg-brand-500/20 border-brand-500/50 text-brand-400'
                    : 'bg-surface-700 border-surface-600 text-surface-400 hover:text-white'
                }`}
              >
                <span>{l.flag}</span> {l.name}
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Buscar time ou liga..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field pl-9 py-2 text-sm"
          />
        </div>
      </div>

      {/* Results */}
      {loading && (
        <div className="flex justify-center py-10">
          <Spinner size={32} />
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-10 text-surface-400 text-sm">
          Nenhum jogo encontrado para os filtros selecionados.
        </div>
      )}

      <AnimatePresence>
        {!loading && Object.entries(grouped).map(([dateLabel, dayFixtures], gi) => (
          <motion.div
            key={dateLabel}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: gi * 0.05 }}
            className="space-y-2"
          >
            <div className="flex items-center gap-2 px-1">
              <div className="h-px flex-1 bg-surface-700" />
              <span className="text-xs font-semibold text-surface-400 capitalize">{dateLabel}</span>
              <div className="h-px flex-1 bg-surface-700" />
            </div>

            {dayFixtures.map((f, fi) => {
              const { time } = formatDate(f.match_date)
              const canAnalyse = !!f.home_db_id && !!f.away_db_id
              const isLoading = loadingAnalysis === f.fixture_id

              return (
                <motion.div
                  key={f.fixture_id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: gi * 0.05 + fi * 0.03 }}
                  className="card py-3 flex items-center gap-3 hover:border-surface-500 transition-colors"
                >
                  {/* League */}
                  <div className="w-7 flex-shrink-0 text-center">
                    {f.league_logo
                      ? <img src={f.league_logo} alt={f.league_name} className="w-6 h-6 object-contain mx-auto" />
                      : <span className="text-xs text-surface-400">{f.league_name.slice(0, 2)}</span>
                    }
                  </div>

                  {/* Teams */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {f.home_team_logo && (
                          <img src={f.home_team_logo} alt={f.home_team_name} className="w-5 h-5 object-contain flex-shrink-0" />
                        )}
                        <span className="text-sm font-medium text-white truncate">{f.home_team_name}</span>
                      </div>
                      <span className="text-xs text-surface-400 font-mono flex-shrink-0">vs</span>
                      <div className="flex items-center gap-2 min-w-0 justify-end">
                        <span className="text-sm font-medium text-white truncate">{f.away_team_name}</span>
                        {f.away_team_logo && (
                          <img src={f.away_team_logo} alt={f.away_team_name} className="w-5 h-5 object-contain flex-shrink-0" />
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-surface-400">{time}</span>
                      {f.round && <span className="text-xs text-surface-500">· {f.round}</span>}
                      {f.venue && <span className="text-xs text-surface-500 truncate">· {f.venue}</span>}
                    </div>
                  </div>

                  {/* Analyse button */}
                  <button
                    onClick={() => handleAnalyse(f)}
                    disabled={!canAnalyse || isLoading}
                    title={!canAnalyse ? 'Carregue os dados desta liga primeiro' : 'Analisar este jogo'}
                    className={`flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg
                                text-xs font-medium transition-all ${
                      canAnalyse
                        ? 'bg-brand-500/20 text-brand-400 hover:bg-brand-500/30 border border-brand-500/30'
                        : 'bg-surface-700 text-surface-500 border border-surface-600 cursor-not-allowed'
                    }`}
                  >
                    {isLoading ? <Spinner size={12} /> : <ChevronRight size={14} />}
                    {canAnalyse ? 'Analisar' : 'Sem dados'}
                  </button>
                </motion.div>
              )
            })}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
