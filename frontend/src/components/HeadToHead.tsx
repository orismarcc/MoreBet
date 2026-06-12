import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, Swords } from 'lucide-react'
import type { H2HMatch, MatchRef } from '../types'
import { matchesApi } from '../lib/api'
import MatchDetailModal from './MatchDetailModal'
import Spinner from './Spinner'

interface Props {
  homeApiId: number
  awayApiId: number
}

export default function HeadToHead({ homeApiId, awayApiId }: Props) {
  const [matches, setMatches] = useState<H2HMatch[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<MatchRef | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    matchesApi.h2h(homeApiId, awayApiId, 3)
      .then(m => { if (alive) setMatches(m) })
      .catch(() => { if (alive) setMatches([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [homeApiId, awayApiId])

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
    >
      <div className="section-title mb-3">
        <Swords size={16} className="text-brand-400" />
        <h3>Confronto direto</h3>
        <span className="text-xs text-surface-400 font-normal">· últimos encontros</span>
      </div>

      {loading && (
        <div className="flex justify-center py-6"><Spinner size={20} /></div>
      )}

      {!loading && matches && matches.length === 0 && (
        <p className="text-xs text-surface-400 py-2">
          Nenhum confronto direto recente encontrado nas competições disponíveis.
        </p>
      )}

      {!loading && matches && matches.length > 0 && (
        <div className="space-y-1.5">
          {matches.map(m => {
            const date = new Date(m.date).toLocaleDateString('pt-BR', {
              day: '2-digit', month: '2-digit', year: '2-digit',
            })
            const homeWin = m.home_goals > m.away_goals
            const awayWin = m.away_goals > m.home_goals
            return (
              <button
                key={m.match_id}
                onClick={() => setDetail({
                  date: m.date,
                  competition: m.competition,
                  competition_code: m.competition_code,
                  home_name: m.home_name,
                  away_name: m.away_name,
                  home_goals: m.home_goals,
                  away_goals: m.away_goals,
                })}
                title="Ver estatísticas da partida"
                className="w-full flex items-center gap-2 py-2 px-3 rounded-xl bg-surface-700/50
                           hover:bg-surface-700 transition-colors text-left group"
              >
                <span className="text-[11px] text-surface-400 tabular-nums w-14 flex-shrink-0">{date}</span>

                <div className="flex items-center gap-1.5 flex-1 min-w-0 justify-end">
                  <span className={`text-sm truncate ${homeWin ? 'text-white font-semibold' : 'text-surface-300'}`}>
                    {m.home_name}
                  </span>
                  {m.home_crest && <img src={m.home_crest} alt="" className="w-4 h-4 object-contain flex-shrink-0" />}
                </div>

                <span className="font-mono font-bold text-white tabular-nums bg-surface-800 rounded-lg px-2 py-0.5 flex-shrink-0">
                  {m.home_goals}-{m.away_goals}
                </span>

                <div className="flex items-center gap-1.5 flex-1 min-w-0">
                  {m.away_crest && <img src={m.away_crest} alt="" className="w-4 h-4 object-contain flex-shrink-0" />}
                  <span className={`text-sm truncate ${awayWin ? 'text-white font-semibold' : 'text-surface-300'}`}>
                    {m.away_name}
                  </span>
                </div>

                <BarChart3 size={13} className="text-surface-500 group-hover:text-brand-400 transition-colors flex-shrink-0" />
              </button>
            )
          })}
          <p className="text-[10px] text-surface-400 pt-1">
            Toque em um jogo para ver posse, finalizações, escanteios e os gols.
          </p>
        </div>
      )}

      {detail && <MatchDetailModal match={detail} onClose={() => setDetail(null)} />}
    </motion.div>
  )
}
