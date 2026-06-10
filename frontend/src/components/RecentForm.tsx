import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, AlertCircle, Home, Plane } from 'lucide-react'
import type { RecentForm as RecentFormData, RecentMatch } from '../types'
import { teamsApi } from '../lib/api'
import Spinner from './Spinner'
import Tooltip from './Tooltip'

interface Props {
  homeTeamId: number
  awayTeamId: number
  homeName: string
  awayName: string
}

const RESULT_STYLE: Record<string, string> = {
  W: 'bg-brand-500 text-white',
  D: 'bg-yellow-500/80 text-surface-900',
  L: 'bg-red-500 text-white',
}

function FormStreak({ form }: { form: string }) {
  if (!form) return <span className="text-xs text-surface-400">sem dados</span>
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
      <div className="bg-surface-900/50 rounded-lg px-2.5 py-2 cursor-help">
        <div className="text-[10px] uppercase tracking-wide text-surface-400 leading-tight">{label}</div>
        <div className="text-sm font-mono font-bold text-white mt-0.5">{value}</div>
      </div>
    </Tooltip>
  )
}

function MatchRow({ m }: { m: RecentMatch }) {
  const date = new Date(m.date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  return (
    <div className="flex items-center gap-2 py-1.5 text-sm">
      <span className="text-[11px] text-surface-400 w-10 flex-shrink-0 tabular-nums">{date}</span>
      <Tooltip content={m.is_home ? 'Em casa' : 'Fora'}>
        {m.is_home
          ? <Home size={12} className="text-surface-500 flex-shrink-0" />
          : <Plane size={12} className="text-surface-500 flex-shrink-0" />}
      </Tooltip>
      {m.opponent_crest && (
        <img src={m.opponent_crest} alt="" className="w-4 h-4 object-contain flex-shrink-0" />
      )}
      <span className="text-surface-200 truncate flex-1 min-w-0">{m.opponent}</span>
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
    </div>
  )
}

function TeamColumn({ teamId, name }: { teamId: number; name: string }) {
  const [data, setData] = useState<RecentFormData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true); setError(false)
    teamsApi.recent(teamId, 6)
      .then(d => { if (alive) setData(d) })
      .catch(() => { if (alive) setError(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [teamId])

  return (
    <div className="bg-surface-800/40 border border-surface-700 rounded-xl p-3.5 flex flex-col gap-3 min-w-0">
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
          Forma indisponível (verifique a chave de dados no servidor)
        </div>
      )}

      {data && !loading && (
        <>
          <div className="grid grid-cols-4 gap-1.5">
            <MiniStat label="PPG" value={data.summary.ppg.toFixed(2)} tip="Pontos por jogo nos últimos jogos" />
            <MiniStat label="Médias" value={`${data.summary.avg_goals_for}/${data.summary.avg_goals_against}`} tip="Média de gols marcados / sofridos por jogo" />
            <MiniStat label="O2.5" value={`${data.summary.over_25_pct}%`} tip="% de jogos com mais de 2.5 gols" />
            <MiniStat label="BTTS" value={`${data.summary.btts_pct}%`} tip="% de jogos em que ambos marcaram" />
          </div>

          <div className="flex items-center gap-3 text-[11px] text-surface-400 px-0.5">
            <span><b className="text-brand-400">{data.summary.wins}</b>V</span>
            <span><b className="text-yellow-400">{data.summary.draws}</b>E</span>
            <span><b className="text-red-400">{data.summary.losses}</b>D</span>
            <span className="ml-auto">CS: <b className="text-surface-200">{data.summary.clean_sheets}</b></span>
            <span>S/ marcar: <b className="text-surface-200">{data.summary.failed_to_score}</b></span>
          </div>

          <div className="border-t border-surface-700 pt-1 divide-y divide-surface-700/50">
            {data.matches.map(m => <MatchRow key={m.match_id} m={m} />)}
          </div>
        </>
      )}
    </div>
  )
}

export default function RecentForm({ homeTeamId, awayTeamId, homeName, awayName }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
    >
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} className="text-brand-500" />
        <h3 className="font-semibold text-white">Forma recente</h3>
        <span className="text-xs text-surface-400">· últimos jogos de cada time</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <TeamColumn teamId={homeTeamId} name={homeName} />
        <TeamColumn teamId={awayTeamId} name={awayName} />
      </div>
    </motion.div>
  )
}
