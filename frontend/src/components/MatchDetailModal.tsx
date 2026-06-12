import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, Goal, X } from 'lucide-react'
import type { MatchDetails, MatchRef } from '../types'
import { matchesApi } from '../lib/api'
import Spinner from './Spinner'

interface Props {
  match: MatchRef
  onClose: () => void
}

function StatRow({ label, suffix, home, away }: {
  label: string; suffix: string; home: string | null; away: string | null
}) {
  const h = parseFloat(home ?? '')
  const a = parseFloat(away ?? '')
  const hasNumbers = !Number.isNaN(h) && !Number.isNaN(a)
  const total = hasNumbers ? h + a : 0
  const homePct = hasNumbers && total > 0 ? (h / total) * 100 : 50

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="font-mono font-bold text-white w-12 tabular-nums">
          {home ?? '—'}{home != null ? suffix : ''}
        </span>
        <span className="text-xs text-surface-400 text-center flex-1 px-2">{label}</span>
        <span className="font-mono font-bold text-white w-12 text-right tabular-nums">
          {away ?? '—'}{away != null ? suffix : ''}
        </span>
      </div>
      {hasNumbers && total > 0 ? (
        <div className="flex h-1.5 rounded-full overflow-hidden gap-px bg-surface-700">
          <div className="bg-brand-500 rounded-l-full" style={{ width: `${homePct}%` }} />
          <div className="bg-red-500 rounded-r-full" style={{ width: `${100 - homePct}%` }} />
        </div>
      ) : (
        <div className="h-1.5 rounded-full bg-surface-700" />
      )}
    </div>
  )
}

export default function MatchDetailModal({ match, onClose }: Props) {
  const [data, setData] = useState<MatchDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    matchesApi.details(match)
      .then(d => { if (alive) setData(d) })
      .catch(() => { if (alive) setError(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // trava o scroll do body enquanto aberto
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const dateLabel = new Date(match.date).toLocaleDateString('pt-BR', {
    day: '2-digit', month: 'long', year: 'numeric',
  })

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-6"
      >
        <motion.div
          key="panel"
          initial={{ opacity: 0, y: 40, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ type: 'spring', damping: 28, stiffness: 350 }}
          onClick={e => e.stopPropagation()}
          className="bg-surface-800 border border-surface-600 w-full sm:max-w-lg
                     rounded-t-2xl sm:rounded-2xl max-h-[88vh] overflow-y-auto"
        >
          {/* Cabeçalho */}
          <div className="sticky top-0 bg-surface-800/95 backdrop-blur border-b border-surface-600 px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-white font-semibold flex-wrap">
                  <span className="truncate max-w-[40%]">{match.home_name}</span>
                  <span className="font-mono text-lg tabular-nums bg-surface-700 px-2 py-0.5 rounded-lg flex-shrink-0">
                    {match.home_goals} × {match.away_goals}
                  </span>
                  <span className="truncate max-w-[40%]">{match.away_name}</span>
                </div>
                <p className="text-xs text-surface-400 mt-1 truncate">
                  {dateLabel}{match.competition ? ` · ${match.competition}` : ''}
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label="Fechar"
                className="text-surface-400 hover:text-white p-1.5 rounded-lg hover:bg-surface-700 flex-shrink-0"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="px-5 py-4 space-y-5">
            {loading && (
              <div className="flex flex-col items-center gap-2 py-10">
                <Spinner size={26} />
                <p className="text-xs text-surface-400">Buscando estatísticas...</p>
              </div>
            )}

            {(error || (data && !data.found)) && !loading && (
              <div className="flex items-start gap-2.5 text-sm text-surface-300 py-6">
                <AlertCircle size={17} className="text-yellow-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p>Estatísticas detalhadas indisponíveis para esta partida.</p>
                  {data?.reason && <p className="text-xs text-surface-400 mt-1">{data.reason}</p>}
                </div>
              </div>
            )}

            {data?.found && (
              <>
                {/* Gols */}
                {data.goals.length > 0 && (
                  <div>
                    <p className="label mb-2 flex items-center gap-1.5">
                      <Goal size={13} className="text-brand-400" /> Gols
                    </p>
                    <div className="space-y-1.5">
                      {data.goals.map((g, i) => (
                        <div
                          key={i}
                          className={`flex items-center gap-2 text-sm ${
                            g.side === 'away' ? 'flex-row-reverse text-right' : ''
                          }`}
                        >
                          <span className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${
                            g.side === 'home' ? 'bg-brand-500/20 text-brand-300' : 'bg-red-500/20 text-red-300'
                          }`}>
                            {g.minute || '—'}
                          </span>
                          <span className="text-white truncate">{g.player ?? 'Gol'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Estatísticas */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="label">Estatísticas</p>
                    <div className="flex items-center gap-3 text-[11px] text-surface-400">
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-brand-500" /> {match.home_name.split(' ')[0]}
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-red-500" /> {match.away_name.split(' ')[0]}
                      </span>
                    </div>
                  </div>
                  <div className="space-y-3.5">
                    {data.stat_labels.map(s => (
                      <StatRow
                        key={s.key}
                        label={s.label}
                        suffix={s.suffix}
                        home={data.home_stats[s.key] ?? null}
                        away={data.away_stats[s.key] ?? null}
                      />
                    ))}
                  </div>
                </div>

                <p className="text-[10px] text-surface-400 text-right">Fonte: {data.source}</p>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  )
}
