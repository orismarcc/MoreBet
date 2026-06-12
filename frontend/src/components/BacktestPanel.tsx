import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FlaskConical, Loader2, TrendingUp, TrendingDown, ChevronDown } from 'lucide-react'
import type { BacktestReport } from '../types'
import { leaguesApi } from '../lib/api'
import Tooltip from './Tooltip'

interface Props {
  leagueApiId: number
  leagueName: string
}

function SkillBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-surface-400">—</span>
  const good = value > 0
  return (
    <span className={`inline-flex items-center gap-1 font-mono font-semibold ${good ? 'text-emerald-400' : 'text-red-400'}`}>
      {good ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
      {(value * 100).toFixed(1)}%
    </span>
  )
}

export default function BacktestPanel({ leagueApiId, leagueName }: Props) {
  const [report, setReport] = useState<BacktestReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  const run = async () => {
    setOpen(true)
    if (report?.league_api_id === leagueApiId) return
    setLoading(true)
    setError('')
    try {
      setReport(await leaguesApi.backtest(leagueApiId))
    } catch {
      setError('Falha ao rodar o backtest — tente novamente em instantes.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="border-t border-surface-600/40 pt-3 mt-1">
      <button
        onClick={() => (open ? setOpen(false) : run())}
        className="flex items-center gap-2 text-xs text-surface-300 hover:text-white transition-colors w-full"
      >
        <FlaskConical size={13} className="text-brand-400" />
        <span className="font-medium">Confiabilidade do modelo nesta liga (backtest)</span>
        <ChevronDown
          size={13}
          className={`ml-auto transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            {loading && (
              <div className="flex items-center gap-2 py-4 text-xs text-surface-400">
                <Loader2 size={14} className="animate-spin text-brand-400" />
                Reprocessando todos os jogos finalizados de {leagueName} (previsão jogo a jogo)…
              </div>
            )}
            {error && <p className="text-xs text-red-400 py-3">{error}</p>}

            {report && !loading && (
              <div className="pt-3 space-y-3">
                <p className="text-[11px] text-surface-400">
                  {report.n_predicted} jogos previstos com dados disponíveis antes de cada partida
                  ({report.n_skipped} pulados por amostra insuficiente).
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="bg-surface-800/60 rounded-lg p-2.5">
                    <Tooltip content="Brier skill score: quanto o modelo supera apostar na frequência da liga. Positivo = modelo agrega informação real.">
                      <p className="text-[10px] text-surface-400 uppercase tracking-wide border-b border-dotted border-surface-600 inline-block cursor-help">Skill 1X2</p>
                    </Tooltip>
                    <p className="mt-1"><SkillBadge value={report.skill_score_1x2} /></p>
                  </div>
                  <div className="bg-surface-800/60 rounded-lg p-2.5">
                    <p className="text-[10px] text-surface-400 uppercase tracking-wide">Acerto 1X2</p>
                    <p className="mt-1 font-mono font-semibold text-white">
                      {report.accuracy_model !== null ? `${(report.accuracy_model * 100).toFixed(1)}%` : '—'}
                      <span className="text-surface-500 font-normal text-[10px]"> vs {report.accuracy_baseline !== null ? `${(report.accuracy_baseline * 100).toFixed(1)}%` : '—'} base</span>
                    </p>
                  </div>
                  <div className="bg-surface-800/60 rounded-lg p-2.5">
                    <Tooltip content="Skill no mercado de mais/menos 2.5 gols — próximo de zero significa que o modelo pouco agrega nesse mercado.">
                      <p className="text-[10px] text-surface-400 uppercase tracking-wide border-b border-dotted border-surface-600 inline-block cursor-help">Skill Over 2.5</p>
                    </Tooltip>
                    <p className="mt-1">
                      <SkillBadge value={
                        report.brier_over25_model && report.brier_over25_baseline
                          ? 1 - report.brier_over25_model / report.brier_over25_baseline
                          : null
                      } />
                    </p>
                  </div>
                  <div className="bg-surface-800/60 rounded-lg p-2.5">
                    <Tooltip content="Skill no mercado ambos marcam.">
                      <p className="text-[10px] text-surface-400 uppercase tracking-wide border-b border-dotted border-surface-600 inline-block cursor-help">Skill BTTS</p>
                    </Tooltip>
                    <p className="mt-1">
                      <SkillBadge value={
                        report.brier_btts_model && report.brier_btts_baseline
                          ? 1 - report.brier_btts_model / report.brier_btts_baseline
                          : null
                      } />
                    </p>
                  </div>
                </div>

                {/* Calibração */}
                {report.calibration.length > 0 && (
                  <div>
                    <p className="text-[10px] text-surface-400 uppercase tracking-wide mb-1.5">
                      Calibração — previsto vs observado (1X2)
                    </p>
                    <div className="space-y-1">
                      {report.calibration.filter(b => b.count >= 10).map(b => (
                        <div key={b.range_low} className="flex items-center gap-2 text-[11px]">
                          <span className="w-14 text-surface-400 font-mono flex-shrink-0">
                            {Math.round(b.range_low * 100)}–{Math.round(b.range_high * 100)}%
                          </span>
                          <div className="flex-1 h-3 bg-surface-800 rounded-sm relative overflow-hidden">
                            <div
                              className="absolute inset-y-0 left-0 bg-brand-500/40"
                              style={{ width: `${b.predicted_avg * 100}%` }}
                            />
                            <div
                              className="absolute inset-y-0 w-0.5 bg-emerald-400"
                              style={{ left: `${b.observed_freq * 100}%` }}
                            />
                          </div>
                          <span className="w-24 text-right text-surface-400 font-mono flex-shrink-0">
                            {(b.predicted_avg * 100).toFixed(0)}% → {(b.observed_freq * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-surface-500 mt-1.5">
                      Barra azul = probabilidade prevista · marca verde = frequência real.
                      Quanto mais próximas, mais calibrado o modelo.
                    </p>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
