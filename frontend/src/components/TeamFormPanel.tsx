import { useEffect, useState } from 'react'
import { AlertCircle, BarChart3, CalendarClock, Home, Plane } from 'lucide-react'
import type { MatchRef, RecentForm as RecentFormData, RecentMatch, UpcomingTeamMatch } from '../types'
import { teamsApi } from '../lib/api'
import MatchDetailModal from './MatchDetailModal'
import Spinner from './Spinner'
import Tooltip from './Tooltip'

export type TeamSource =
  | { kind: 'db'; id: number }
  | { kind: 'api'; apiId: number }

interface Props {
  source: TeamSource
  name: string
  /** Nome real do time para consultas (quando `name` é um título de seção). */
  queryName?: string
  /** Quantos jogos finalizados buscar (padrão 6). */
  limit?: number
  /** Busca e exibe também os próximos jogos do time. */
  withUpcoming?: boolean
  /** Sem moldura própria — para embutir dentro de outro card. */
  bare?: boolean
}

const RESULT_STYLE: Record<string, string> = {
  W: 'bg-brand-500 text-white',
  D: 'bg-yellow-500/80 text-surface-900',
  L: 'bg-red-500 text-white',
}

export function FormStreak({ form }: { form: string }) {
  if (!form) return null
  return (
    <div className="flex gap-1">
      {form.split('').map((r, i) => (
        <span
          key={i}
          className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold ${
            RESULT_STYLE[r] ?? 'bg-surface-600'
          }`}
        >
          {r}
        </span>
      ))}
    </div>
  )
}

function MiniStat({ label, value, tip }: { label: string; value: string; tip: string }) {
  return (
    <Tooltip content={tip}>
      <div className="bg-surface-900/50 rounded-lg px-1.5 py-2 cursor-help min-w-0 text-center">
        <div className="text-[10px] uppercase tracking-wide text-surface-400 leading-tight truncate">{label}</div>
        <div className="text-xs font-mono font-bold text-white mt-0.5 tabular-nums">{value}</div>
      </div>
    </Tooltip>
  )
}

function MatchRow({ m, onOpen }: { m: RecentMatch; onOpen: () => void }) {
  const date = new Date(m.date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  return (
    <button
      onClick={onOpen}
      title="Ver estatísticas da partida"
      className="w-full flex items-center gap-2 py-1.5 text-sm text-left rounded-lg
                 hover:bg-surface-700/60 transition-colors px-1 -mx-1 group"
    >
      <span className="text-[11px] text-surface-400 w-10 flex-shrink-0 tabular-nums">{date}</span>
      {m.is_home
        ? <Home size={12} className="text-surface-400 flex-shrink-0" />
        : <Plane size={12} className="text-surface-400 flex-shrink-0" />}
      {m.opponent_crest && (
        <img src={m.opponent_crest} alt="" className="w-4 h-4 object-contain flex-shrink-0" />
      )}
      <span className="text-surface-200 truncate flex-1 min-w-0">{m.opponent}</span>
      <BarChart3 size={12} className="text-surface-500 group-hover:text-brand-400 transition-colors flex-shrink-0" />
      {m.competition_code && (
        <span className="hidden sm:inline text-[10px] text-surface-400 bg-surface-700 px-1.5 py-0.5 rounded flex-shrink-0">
          {m.competition_code}
        </span>
      )}
      <span className="font-mono font-semibold text-white tabular-nums flex-shrink-0">
        {m.goals_for}-{m.goals_against}
      </span>
      <span
        className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
          RESULT_STYLE[m.result]
        }`}
      >
        {m.result}
      </span>
    </button>
  )
}

function UpcomingRow({ m }: { m: UpcomingTeamMatch }) {
  const d = new Date(m.date)
  const date = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  const time = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  return (
    <div className="flex items-center gap-2 py-1.5 text-sm">
      <span className="text-[11px] text-surface-400 w-10 flex-shrink-0 tabular-nums">{date}</span>
      <Tooltip content={m.is_home ? 'Em casa' : 'Fora'}>
        {m.is_home
          ? <Home size={12} className="text-surface-400 flex-shrink-0" />
          : <Plane size={12} className="text-surface-400 flex-shrink-0" />}
      </Tooltip>
      {m.opponent_crest && (
        <img src={m.opponent_crest} alt="" className="w-4 h-4 object-contain flex-shrink-0" />
      )}
      <span className="text-surface-200 truncate flex-1 min-w-0">{m.opponent}</span>
      <span className="text-[11px] text-surface-400 truncate hidden sm:block max-w-[120px]">{m.competition}</span>
      <span className="text-xs text-brand-300 font-mono tabular-nums flex-shrink-0">{time}</span>
    </div>
  )
}

export default function TeamFormPanel({ source, name, queryName, limit = 6, withUpcoming = false, bare = false }: Props) {
  const [data, setData] = useState<RecentFormData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [detail, setDetail] = useState<MatchRef | null>(null)

  const teamName = queryName ?? name
  const sourceKey = source.kind === 'db' ? `db:${source.id}` : `api:${source.apiId}`

  function openDetail(m: RecentMatch) {
    setDetail({
      date: m.date,
      competition: m.competition,
      competition_code: m.competition_code,
      home_name: m.is_home ? teamName : m.opponent,
      away_name: m.is_home ? m.opponent : teamName,
      home_goals: m.is_home ? m.goals_for : m.goals_against,
      away_goals: m.is_home ? m.goals_against : m.goals_for,
    })
  }

  useEffect(() => {
    let alive = true
    setLoading(true); setError(false); setData(null)
    const req = source.kind === 'db'
      ? teamsApi.recent(source.id, limit, withUpcoming)
      : teamsApi.recentByApiId(source.apiId, limit, withUpcoming)
    req
      .then(d => { if (alive) setData(d) })
      .catch(() => { if (alive) setError(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey, limit, withUpcoming])

  const wrapper = bare
    ? 'flex flex-col gap-3 min-w-0'
    : 'bg-surface-800/40 border border-surface-600 rounded-xl p-3.5 flex flex-col gap-3 min-w-0'

  return (
    <div className={wrapper}>
      <div className="flex items-center justify-between gap-2 min-w-0">
        <span className="font-semibold text-white truncate">{name}</span>
        {data && <FormStreak form={data.summary.form} />}
      </div>

      {loading && (
        <div className="flex justify-center py-8"><Spinner size={22} /></div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-xs text-surface-400 py-6 justify-center text-center">
          <AlertCircle size={14} className="flex-shrink-0" />
          Dados indisponíveis no momento — tente novamente em instantes.
        </div>
      )}

      {data && !loading && (
        <>
          {data.summary.played > 0 ? (
            <>
              <div className="grid grid-cols-5 gap-1.5">
                <MiniStat label="PPG" value={data.summary.ppg.toFixed(2)} tip="Pontos por jogo no recorte recente" />
                <MiniStat label="Gols" value={`${data.summary.avg_goals_for.toFixed(1)}/${data.summary.avg_goals_against.toFixed(1)}`} tip="Média de gols marcados / sofridos por jogo" />
                <MiniStat label="O1.5" value={`${data.summary.over_15_pct}%`} tip="% de jogos com mais de 1.5 gols (2 ou mais)" />
                <MiniStat label="O2.5" value={`${data.summary.over_25_pct}%`} tip="% de jogos com mais de 2.5 gols (3 ou mais)" />
                <MiniStat label="BTTS" value={`${data.summary.btts_pct}%`} tip="% de jogos em que ambos marcaram" />
              </div>

              <div className="flex items-center gap-3 text-[11px] text-surface-400 px-0.5 flex-wrap">
                <span><b className="text-brand-400">{data.summary.wins}</b>V</span>
                <span><b className="text-yellow-400">{data.summary.draws}</b>E</span>
                <span><b className="text-red-400">{data.summary.losses}</b>D</span>
                <span className="ml-auto">Sem sofrer: <b className="text-surface-200">{data.summary.clean_sheets}</b></span>
                <span>Sem marcar: <b className="text-surface-200">{data.summary.failed_to_score}</b></span>
              </div>

              <div className="border-t border-surface-600 pt-1 divide-y divide-surface-600/50">
                {data.matches.map(m => (
                  <MatchRow key={m.match_id} m={m} onOpen={() => openDetail(m)} />
                ))}
              </div>
            </>
          ) : (
            <p className="text-xs text-surface-400 py-2">
              Ainda sem jogos finalizados no recorte disponível — a forma aparece
              automaticamente conforme as partidas acontecem.
            </p>
          )}

          {withUpcoming && data.upcoming.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-surface-300 mb-1">
                <CalendarClock size={13} className="text-brand-400" />
                Próximos jogos
              </div>
              <div className="divide-y divide-surface-600/50">
                {data.upcoming.map(m => <UpcomingRow key={m.match_id} m={m} />)}
              </div>
            </div>
          )}
        </>
      )}

      {detail && <MatchDetailModal match={detail} onClose={() => setDetail(null)} />}
    </div>
  )
}
