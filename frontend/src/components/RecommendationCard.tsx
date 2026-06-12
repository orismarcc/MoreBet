import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, AlertTriangle, ShieldCheck, ShieldAlert, Shield,
  Info, Loader2, Ban, RefreshCw,
} from 'lucide-react'
import type {
  CalculateMatchPayload, RecommendationReport, RecommendationConfidence,
} from '../types'
import { matchesApi } from '../lib/api'
import Tooltip from './Tooltip'

interface Props {
  payload: CalculateMatchPayload
}

const CONFIDENCE_STYLE: Record<RecommendationConfidence, {
  label: string
  chip: string
  icon: typeof ShieldCheck
}> = {
  alta: {
    label: 'Confiança alta',
    chip: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    icon: ShieldCheck,
  },
  media: {
    label: 'Confiança média',
    chip: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    icon: Shield,
  },
  baixa: {
    label: 'Confiança baixa',
    chip: 'bg-surface-600/40 text-surface-300 border-surface-500/40',
    icon: ShieldAlert,
  },
}

export default function RecommendationCard({ payload }: Props) {
  const [report, setReport] = useState<RecommendationReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      setReport(await matchesApi.recommend(payload))
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(detail ?? 'Falha ao gerar a recomendação. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.18 }}
      className="card"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-brand-400" />
          <p className="label">Recomendação do Analista (IA)</p>
        </div>
        {report && (
          <button
            onClick={generate}
            disabled={loading}
            className="btn-ghost py-1 px-2.5 text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={12} /> Regenerar
          </button>
        )}
      </div>
      <p className="text-xs text-surface-400 mb-4">
        Agente lê o modelo, a forma recente, o H2H e o backtest da liga — e só
        recomenda o que os dados sustentam. A odd mínima já embute margem de
        valor: <strong className="text-surface-300">aposte apenas se a casa pagar acima dela</strong>,
        e trate confiança média/baixa como observação, não aposta.
      </p>

      {!report && !loading && (
        <button onClick={generate} className="btn-primary w-full sm:w-auto flex items-center justify-center gap-2">
          <Sparkles size={16} /> Gerar análise do agente
        </button>
      )}

      {loading && (
        <div className="flex items-center gap-3 py-6 justify-center text-surface-300">
          <Loader2 size={20} className="animate-spin text-brand-400" />
          <span className="text-sm">
            Cruzando modelo, forma, H2H e backtest… isso leva até 1 minuto.
          </span>
        </div>
      )}

      {error && !loading && (
        <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <AnimatePresence>
        {report && !loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-4"
          >
            {/* Leitura geral */}
            <p className="text-sm text-surface-200 leading-relaxed bg-surface-800/60 rounded-lg p-3 border border-surface-600/40">
              {report.summary}
            </p>

            {report.no_bet && report.recommendations.length === 0 && (
              <div className="flex items-center gap-2 bg-surface-700/40 border border-surface-500/40 rounded-lg p-3 text-sm text-surface-200">
                <Ban size={16} className="text-red-400 flex-shrink-0" />
                <span>
                  <strong>Sem aposta recomendada.</strong> Nenhum mercado deste
                  confronto tem suporte suficiente nos dados.
                </span>
              </div>
            )}

            {/* Recomendações */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              {report.recommendations.map((rec, i) => {
                const style = CONFIDENCE_STYLE[rec.confidence]
                const ConfIcon = style.icon
                return (
                  <motion.div
                    key={rec.market}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08 }}
                    className="bg-surface-800/60 border border-surface-600/50 rounded-xl p-4 flex flex-col gap-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-semibold text-white text-sm leading-snug">
                        {rec.market_label}
                      </p>
                      <span className={`flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border flex-shrink-0 ${style.chip}`}>
                        <ConfIcon size={11} /> {style.label}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-sm flex-wrap">
                      <div>
                        <p className="text-[11px] text-surface-400">Prob. modelo</p>
                        <p className="font-mono font-semibold text-brand-300">
                          {(rec.model_probability * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div>
                        <Tooltip content="Odd justa + margem de valor (+4% de EV). Aposte SOMENTE se a casa pagar acima deste número — abaixo dele a aposta não tem vantagem matemática.">
                          <p className="text-[11px] text-surface-400 border-b border-dotted border-surface-500 cursor-help">
                            Apostar acima de
                          </p>
                        </Tooltip>
                        <p className="font-mono font-semibold text-emerald-400">
                          {rec.min_bookie_odds.toFixed(2)}
                        </p>
                      </div>
                      <div>
                        <Tooltip content="Fração da banca sugerida (1/4 do critério de Kelly na odd mínima) — disciplina de stake protege contra sequências ruins.">
                          <p className="text-[11px] text-surface-400 border-b border-dotted border-surface-500 cursor-help">
                            Stake sugerido
                          </p>
                        </Tooltip>
                        <p className="font-mono font-semibold text-amber-300">
                          {(rec.suggested_stake_pct * 100).toFixed(2)}%
                        </p>
                      </div>
                    </div>

                    <p className="text-xs text-surface-300 leading-relaxed flex-1">
                      {rec.rationale}
                    </p>

                    {rec.caveats.length > 0 && (
                      <ul className="space-y-1">
                        {rec.caveats.map((c, j) => (
                          <li key={j} className="flex items-start gap-1.5 text-[11px] text-amber-300/90">
                            <AlertTriangle size={11} className="flex-shrink-0 mt-0.5" />
                            <span>{c}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </motion.div>
                )
              })}
            </div>

            {/* Qualidade dos dados */}
            {report.data_quality_notes.length > 0 && (
              <div className="bg-surface-800/40 border border-surface-600/40 rounded-lg p-3">
                <p className="flex items-center gap-1.5 text-[11px] font-medium text-surface-400 uppercase tracking-wide mb-2">
                  <Info size={12} /> Qualidade dos dados
                </p>
                <ul className="space-y-1">
                  {report.data_quality_notes.map((n, i) => (
                    <li key={i} className="text-xs text-surface-300 flex items-start gap-1.5">
                      <span className="text-surface-500 mt-0.5">•</span>
                      <span>{n}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[10px] text-surface-500">
              Gerado por {report.model_id}{report.cached ? ' (cache)' : ''} ·
              apostas envolvem risco — nada aqui é garantia de lucro.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
