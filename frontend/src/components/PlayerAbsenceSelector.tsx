import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UserX, ChevronDown, ChevronUp } from 'lucide-react'
import type { Player, AbsentPlayer } from '../types'
import { teamsApi } from '../lib/api'
import Tooltip from './Tooltip'

interface Props {
  teamId: number
  teamName: string
  onAbsentChange: (absent: AbsentPlayer[]) => void
}

export default function PlayerAbsenceSelector({ teamId, teamName, onAbsentChange }: Props) {
  const [players, setPlayers] = useState<Player[]>([])
  const [absent, setAbsent] = useState<Set<number>>(new Set())
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    teamsApi.players(teamId)
      .then(setPlayers)
      .catch(() => setPlayers([]))
      .finally(() => setLoading(false))
  }, [teamId])

  function toggle(player: Player) {
    const next = new Set(absent)
    if (next.has(player.id)) {
      next.delete(player.id)
    } else {
      next.add(player.id)
    }
    setAbsent(next)
    onAbsentChange(
      players
        .filter(p => next.has(p.id))
        .map(p => ({ player_id: p.id, goal_contribution_pct: p.goal_contribution_pct }))
    )
  }

  const totalImpact = players
    .filter(p => absent.has(p.id))
    .reduce((acc, p) => acc + p.goal_contribution_pct, 0)

  return (
    <div className="card">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <UserX size={16} className="text-surface-400" />
          <span className="text-sm font-semibold text-white">{teamName} — Desfalques</span>
          {absent.size > 0 && (
            <span className="badge badge-yellow">{absent.size} ausente{absent.size > 1 ? 's' : ''}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {absent.size > 0 && (
            <Tooltip content={`Redução de ${(totalImpact * 100).toFixed(0)}% na força de ataque`}>
              <span className="text-xs text-yellow-400 font-mono cursor-help">
                λ ×{(1 - totalImpact).toFixed(2)}
              </span>
            </Tooltip>
          )}
          {expanded ? <ChevronUp size={16} className="text-surface-400" /> : <ChevronDown size={16} className="text-surface-400" />}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-1">
              {loading && <p className="text-xs text-surface-400">Carregando jogadores...</p>}
              {!loading && players.length === 0 && (
                <p className="text-xs text-surface-400">
                  Sem dados de jogadores. Adicione manualmente via API.
                </p>
              )}
              {players.map(p => (
                <label
                  key={p.id}
                  className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-surface-700
                             cursor-pointer transition-colors group"
                >
                  <input
                    type="checkbox"
                    checked={absent.has(p.id)}
                    onChange={() => toggle(p)}
                    className="accent-brand-500 w-4 h-4"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-surface-300 group-hover:text-white truncate block">
                      {p.name}
                    </span>
                    <span className="text-xs text-surface-400">
                      {p.position} · G+A: {p.goals + p.assists}
                    </span>
                  </div>
                  <Tooltip content={`Participou de ${(p.goal_contribution_pct * 100).toFixed(1)}% dos gols do time`}>
                    <span className="text-xs font-mono text-brand-400 cursor-help">
                      {(p.goal_contribution_pct * 100).toFixed(0)}%
                    </span>
                  </Tooltip>
                </label>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
