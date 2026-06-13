import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ListOrdered } from 'lucide-react'
import type { StandingGroup, StandingRow } from '../types'
import { leaguesApi } from '../lib/api'
import Spinner from './Spinner'
import Tooltip from './Tooltip'

interface Props {
  leagueApiId: number
  /** Click a row to open that team's full profile (same data as a search). */
  onTeamClick?: (row: StandingRow) => void
}

function Table({ rows, onTeamClick }: { rows: StandingGroup['rows']; onTeamClick?: (row: StandingRow) => void }) {
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-surface-400 text-[11px] uppercase tracking-wide">
            <th className="text-left font-medium py-1.5 pl-1 w-6">#</th>
            <th className="text-left font-medium py-1.5">Time</th>
            <th className="text-center font-medium py-1.5 w-8"><Tooltip content="Jogos"><span>J</span></Tooltip></th>
            <th className="text-center font-medium py-1.5 w-8 hidden xs:table-cell"><Tooltip content="Vitórias"><span>V</span></Tooltip></th>
            <th className="text-center font-medium py-1.5 w-8 hidden xs:table-cell"><Tooltip content="Empates"><span>E</span></Tooltip></th>
            <th className="text-center font-medium py-1.5 w-8 hidden xs:table-cell"><Tooltip content="Derrotas"><span>D</span></Tooltip></th>
            <th className="text-center font-medium py-1.5 w-10 hidden sm:table-cell"><Tooltip content="Saldo de gols"><span>SG</span></Tooltip></th>
            <th className="text-center font-semibold py-1.5 w-9 text-surface-200"><Tooltip content="Pontos"><span>Pts</span></Tooltip></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const clickable = !!onTeamClick && r.team_api_id != null
            return (
            <tr
              key={r.team_api_id ?? i}
              onClick={clickable ? () => onTeamClick!(r) : undefined}
              className={`border-t border-surface-700/60 transition-colors ${
                clickable ? 'cursor-pointer hover:bg-brand-500/10' : 'hover:bg-surface-700/30'
              }`}
            >
              <td className="py-1.5 pl-1 text-surface-400 tabular-nums">{r.position}</td>
              <td className="py-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  {r.team_crest && <img src={r.team_crest} alt="" className="w-4 h-4 object-contain flex-shrink-0" />}
                  <span className={`truncate ${clickable ? 'text-white hover:text-brand-300' : 'text-white'}`}>{r.team_name}</span>
                </div>
              </td>
              <td className="text-center text-surface-300 tabular-nums">{r.played}</td>
              <td className="text-center text-surface-300 tabular-nums hidden xs:table-cell">{r.won}</td>
              <td className="text-center text-surface-300 tabular-nums hidden xs:table-cell">{r.draw}</td>
              <td className="text-center text-surface-300 tabular-nums hidden xs:table-cell">{r.lost}</td>
              <td className="text-center text-surface-300 tabular-nums hidden sm:table-cell">
                {r.goal_difference != null && r.goal_difference > 0 ? '+' : ''}{r.goal_difference}
              </td>
              <td className="text-center font-semibold text-white tabular-nums">{r.points}</td>
            </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function LeagueStandings({ leagueApiId, onTeamClick }: Props) {
  const [groups, setGroups] = useState<StandingGroup[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true); setError(false); setGroups(null)
    leaguesApi.standings(leagueApiId)
      .then(g => { if (alive) setGroups(g) })
      .catch(() => { if (alive) setError(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [leagueApiId])

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
    >
      <div className="section-title mb-3">
        <ListOrdered size={16} className="text-brand-400" />
        <h3>Classificação</h3>
      </div>

      {loading && <div className="flex justify-center py-6"><Spinner size={22} /></div>}
      {error && !loading && (
        <p className="text-xs text-surface-400 py-3">Classificação indisponível para esta liga no momento.</p>
      )}
      {groups && !loading && groups.length === 0 && (
        <p className="text-xs text-surface-400 py-3">Sem tabela publicada ainda para esta competição.</p>
      )}
      {groups && !loading && groups.length > 0 && (
        <div className="space-y-4">
          {groups.map((g, i) => (
            <div key={g.group ?? i}>
              {g.group && (
                <p className="text-xs font-semibold text-surface-300 mb-1">{g.group}</p>
              )}
              <Table rows={g.rows} onTeamClick={onTeamClick} />
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}
