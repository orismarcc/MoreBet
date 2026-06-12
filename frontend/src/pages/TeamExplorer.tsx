import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ChevronRight, Flag, Search, Shield, Users } from 'lucide-react'
import type { Team, TeamSearchResult } from '../types'
import { teamsApi } from '../lib/api'
import TeamFormPanel from '../components/TeamFormPanel'
import Spinner from '../components/Spinner'
import Tooltip from '../components/Tooltip'

const SUGGESTIONS = ['Brazil', 'Mexico', 'Real Madrid', 'Bayern', 'Cruzeiro', 'Arsenal']

interface ExplorerProps {
  onAnalyse?: (home: Team, away: Team) => void
}

function StatBox({ label, value, tip }: { label: string; value: string; tip: string }) {
  return (
    <Tooltip content={tip}>
      <div className="card !p-4 cursor-help min-w-0">
        <p className="label leading-snug">{label}</p>
        <p className="text-2xl font-mono font-bold text-white mt-1.5 tabular-nums">{value}</p>
      </div>
    </Tooltip>
  )
}

function KindBadge({ kind }: { kind: 'club' | 'national' }) {
  return kind === 'club'
    ? <span className="badge-blue"><Shield size={11} /> Clube</span>
    : <span className="badge-yellow"><Flag size={11} /> Seleção</span>
}

export default function TeamExplorer({ onAnalyse }: ExplorerProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TeamSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [selected, setSelected] = useState<TeamSearchResult | null>(null)
  const [clubStats, setClubStats] = useState<Team | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Busca com debounce
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const q = query.trim()
    if (q.length < 2) {
      setResults([]); setSearched(false); setSearching(false)
      return
    }
    setSearching(true)
    debounceRef.current = setTimeout(() => {
      let alive = true
      teamsApi.search(q)
        .then(r => { if (alive) { setResults(r); setSearched(true) } })
        .catch(() => { if (alive) { setResults([]); setSearched(true) } })
        .finally(() => { if (alive) setSearching(false) })
      return () => { alive = false }
    }, 350)
  }, [query])

  // Stats do clube ao abrir o detalhe
  useEffect(() => {
    setClubStats(null)
    if (selected?.kind === 'club' && selected.db_id) {
      teamsApi.get(selected.db_id).then(setClubStats).catch(() => setClubStats(null))
    }
  }, [selected])

  // ── Detalhe ────────────────────────────────────────────────────────────────
  if (selected) {
    return (
      <motion.div
        key={`detail-${selected.api_id}`}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="space-y-4 pt-4 max-w-3xl mx-auto"
      >
        <button
          onClick={() => setSelected(null)}
          className="btn-ghost py-1.5 px-3 flex items-center gap-1.5 text-sm"
        >
          <ArrowLeft size={16} /> Voltar à busca
        </button>

        {/* Cabeçalho do time */}
        <div className="card flex items-center gap-4">
          {selected.crest ? (
            <img src={selected.crest} alt="" className="w-14 h-14 sm:w-16 sm:h-16 object-contain flex-shrink-0" />
          ) : (
            <div className="w-14 h-14 rounded-2xl bg-surface-700 grid place-items-center flex-shrink-0">
              <Users size={22} className="text-surface-400" />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-lg sm:text-xl font-bold text-white truncate">{selected.name}</h2>
            <p className="text-xs sm:text-sm text-surface-400 truncate">{selected.context}</p>
            <div className="mt-1.5"><KindBadge kind={selected.kind} /></div>
          </div>
        </div>

        {/* Stats do modelo (apenas clubes — vêm do banco) */}
        {selected.kind === 'club' && clubStats && (
          <div>
            <p className="text-xs text-surface-400 mb-2 px-0.5">
              Médias usadas no modelo · forma recente (até 30 jogos)
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <StatBox label="Gols marcados · casa" value={clubStats.home_goals_scored.toFixed(2)}
                tip="Média de gols marcados por jogo como mandante" />
              <StatBox label="Gols sofridos · casa" value={clubStats.home_goals_conceded.toFixed(2)}
                tip="Média de gols sofridos por jogo como mandante" />
              <StatBox label="Gols marcados · fora" value={clubStats.away_goals_scored.toFixed(2)}
                tip="Média de gols marcados por jogo como visitante" />
              <StatBox label="Gols sofridos · fora" value={clubStats.away_goals_conceded.toFixed(2)}
                tip="Média de gols sofridos por jogo como visitante" />
            </div>
          </div>
        )}

        {selected.kind === 'national' && (
          <p className="text-xs text-surface-400 px-0.5">
            Seleções não participam do cálculo de odds enquanto a Copa não tem jogos
            finalizados — abaixo, o histórico disponível e a agenda do time.
          </p>
        )}

        {/* Forma + próximos jogos */}
        <div className="card">
          <TeamFormPanel
            bare
            source={selected.kind === 'club' && selected.db_id
              ? { kind: 'db', id: selected.db_id }
              : { kind: 'api', apiId: selected.api_id }}
            name="Últimos jogos"
            queryName={selected.name}
            myApiId={selected.api_id}
            limit={10}
            withUpcoming
            onAnalyse={onAnalyse}
          />
        </div>
      </motion.div>
    )
  }

  // ── Busca ──────────────────────────────────────────────────────────────────
  return (
    <motion.div
      key="search"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-4 pt-4 max-w-3xl mx-auto"
    >
      <div className="text-center pt-2 pb-1">
        <h1 className="text-2xl font-bold text-white flex items-center justify-center gap-2">
          <Users size={22} className="text-brand-400" /> Times & Seleções
        </h1>
        <p className="text-surface-400 text-sm mt-1">
          Pesquise qualquer clube das 8 ligas ou seleção da Copa para ver estatísticas e últimos jogos
        </p>
      </div>

      <div className="relative">
        <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" />
        <input
          type="text"
          autoFocus
          placeholder="Buscar time... (ex: Cruzeiro, Brazil, Arsenal)"
          value={query}
          onChange={e => setQuery(e.target.value)}
          className="input-field pl-11 py-3 text-base"
        />
        {searching && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2"><Spinner size={16} /></div>
        )}
      </div>

      {/* Sugestões */}
      {!query && (
        <div className="flex flex-wrap items-center gap-1.5 justify-center">
          <span className="text-xs text-surface-400 mr-1">Sugestões:</span>
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => setQuery(s)}
              className="px-3 py-1 rounded-full text-xs font-medium bg-surface-700 border
                         border-surface-600 text-surface-300 hover:text-white hover:border-brand-500/50
                         transition-all"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Resultados */}
      <AnimatePresence mode="popLayout">
        {results.map((t, i) => (
          <motion.button
            key={`${t.kind}-${t.api_id}`}
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ delay: i * 0.03 }}
            onClick={() => setSelected(t)}
            className="card-hover w-full !p-3.5 flex items-center gap-3 text-left"
          >
            {t.crest ? (
              <img src={t.crest} alt="" className="w-9 h-9 object-contain flex-shrink-0" />
            ) : (
              <div className="w-9 h-9 rounded-xl bg-surface-700 grid place-items-center flex-shrink-0">
                <Users size={16} className="text-surface-400" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-white truncate">{t.name}</p>
              <p className="text-xs text-surface-400 truncate">{t.context}</p>
            </div>
            <KindBadge kind={t.kind} />
            <ChevronRight size={16} className="text-surface-400 flex-shrink-0" />
          </motion.button>
        ))}
      </AnimatePresence>

      {searched && !searching && results.length === 0 && query.trim().length >= 2 && (
        <p className="text-center text-sm text-surface-400 py-8">
          Nenhum time encontrado para “{query.trim()}”. Tente o nome em inglês para seleções
          (ex: “Brazil”, “Germany”).
        </p>
      )}
    </motion.div>
  )
}
