import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { TrendingUp, AlertCircle, Minus } from 'lucide-react'
import type { FairOdds, ValueCheckResult } from '../types'
import { matchesApi } from '../lib/api'
import Spinner from './Spinner'
import Tooltip from './Tooltip'

interface Props {
  fairOdds: FairOdds
  homeName: string
  awayName: string
}

const MARKET_OPTIONS = (home: string, away: string) => [
  { key: 'home_win',                 label: `Vitória ${home}` },
  { key: 'draw',                     label: 'Empate' },
  { key: 'away_win',                 label: `Vitória ${away}` },
  { key: 'home_or_draw',             label: `${home} ou Empate (1X)` },
  { key: 'away_or_draw',             label: `${away} ou Empate (X2)` },
  { key: 'home_or_away',             label: `${home} ou ${away} (12)` },
  { key: 'over_05',                  label: 'Over 0.5 Gols' },
  { key: 'over_15',                  label: 'Over 1.5 Gols' },
  { key: 'over_25',                  label: 'Over 2.5 Gols' },
  { key: 'over_35',                  label: 'Over 3.5 Gols' },
  { key: 'over_45',                  label: 'Over 4.5 Gols' },
  { key: 'under_15',                 label: 'Under 1.5 Gols' },
  { key: 'under_25',                 label: 'Under 2.5 Gols' },
  { key: 'under_35',                 label: 'Under 3.5 Gols' },
  { key: 'btts_yes',                 label: 'BTTS Sim' },
  { key: 'btts_no',                  label: 'BTTS Não' },
  { key: 'ah_home_minus_half',       label: `${home} -0.5 AH` },
  { key: 'ah_home_minus_one_half',   label: `${home} -1.5 AH` },
  { key: 'ah_home_plus_half',        label: `${home} +0.5 AH` },
  { key: 'ah_away_minus_half',       label: `${away} -0.5 AH` },
  { key: 'ah_away_minus_one_half',   label: `${away} -1.5 AH` },
  { key: 'ah_away_plus_half',        label: `${away} +0.5 AH` },
  { key: 'btts_and_over_25',         label: 'BTTS Sim + Over 2.5' },
  { key: 'btts_and_under_25',        label: 'BTTS Sim + Under 2.5' },
  { key: 'home_and_over_25',         label: `${home} vence + Over 2.5` },
  { key: 'away_and_over_25',         label: `${away} vence + Over 2.5` },
]

export default function ValueFinder({ fairOdds, homeName, awayName }: Props) {
  const [market, setMarket] = useState('home_win')
  const [bookieOdds, setBookieOdds] = useState('')
  const [result, setResult] = useState<ValueCheckResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fairOdd = fairOdds[market as keyof FairOdds] ?? 0
  const options = MARKET_OPTIONS(homeName, awayName)

  async function handleCheck() {
    const bookie = parseFloat(bookieOdds)
    if (!bookie || bookie <= 1) {
      setError('Digite uma odd válida (maior que 1.00)')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await matchesApi.checkValue({ market, fair_odds: fairOdd, bookie_odds: bookie })
      setResult(res)
    } catch {
      setError('Erro ao verificar valor.')
    } finally {
      setLoading(false)
    }
  }

  const evColor = result
    ? result.ev_pct > 5 ? 'text-brand-400'
    : result.ev_pct > 0 ? 'text-yellow-400'
    : 'text-red-400'
    : ''

  const EvIcon = result
    ? result.ev_pct > 0 ? TrendingUp
    : result.ev_pct < 0 ? AlertCircle
    : Minus
    : Minus

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <p className="label">Verificador de Valor (EV)</p>
        <Tooltip content="EV% = (odd_casa / odd_justa − 1) × 100. Positivo = valor a longo prazo.">
          <span className="text-xs text-surface-400 border-b border-dashed border-surface-500 cursor-help">
            O que é EV?
          </span>
        </Tooltip>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="label mb-1.5 block">Mercado</label>
          <div className="relative">
            <select
              value={market}
              onChange={e => { setMarket(e.target.value); setResult(null) }}
              className="select-field pr-8"
            >
              {options.map(o => (
                <option key={o.key} value={o.key}>{o.label}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-surface-400">▾</div>
          </div>
        </div>

        <div>
          <label className="label mb-1.5 block">
            Odd da casa de apostas
          </label>
          <input
            type="number"
            step="0.01"
            min="1.01"
            placeholder="ex: 2.10"
            value={bookieOdds}
            onChange={e => { setBookieOdds(e.target.value); setResult(null) }}
            onKeyDown={e => e.key === 'Enter' && handleCheck()}
            className="input-field"
          />
        </div>
      </div>

      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 p-3 bg-surface-700/50 rounded-lg">
        <span className="label whitespace-nowrap">Odd Justa Calculada:</span>
        <span className="text-xl font-bold font-mono text-brand-400 tabular-nums">
          {fairOdd.toFixed(3)}
        </span>
        <span className="text-xs text-surface-400">
          (probabilidade: {((1 / fairOdd) * 100).toFixed(1)}%)
        </span>
      </div>

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      <button
        onClick={handleCheck}
        disabled={!bookieOdds || loading}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {loading ? <Spinner size={18} /> : <TrendingUp size={18} />}
        Verificar Valor
      </button>

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ duration: 0.35 }}
            className={`rounded-xl border p-4 ${
              result.ev_pct > 5
                ? 'border-brand-500/50 bg-brand-500/10 animate-pulse-green'
                : result.ev_pct > 0
                ? 'border-yellow-500/40 bg-yellow-500/5'
                : 'border-red-500/30 bg-red-500/5'
            }`}
          >
            <div className="flex items-start gap-3">
              <EvIcon
                size={22}
                className={`mt-0.5 flex-shrink-0 ${evColor}`}
              />
              <div className="flex-1">
                <p className={`font-semibold text-sm ${evColor}`}>{result.verdict}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-surface-400">
                  <span>
                    Odd justa: <strong className="text-white font-mono">{result.fair_odds.toFixed(3)}</strong>
                  </span>
                  <span>
                    Odd casa: <strong className="text-white font-mono">{result.bookie_odds.toFixed(2)}</strong>
                  </span>
                  <span>
                    EV: <strong className={`font-mono ${evColor}`}>
                      {result.ev_pct > 0 ? '+' : ''}{result.ev_pct.toFixed(2)}%
                    </strong>
                  </span>
                </div>
                {result.has_value && result.kelly_pct > 0 && (
                  <div className="mt-3 pt-3 border-t border-surface-700/60 text-xs">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <Tooltip content="Kelly Criterion: fração do bankroll que maximiza o crescimento geométrico no longo prazo. Full Kelly = agressivo. 1/4 Kelly = conservador (recomendado para a maioria).">
                        <span className="text-surface-400 border-b border-dashed border-surface-500 cursor-help">
                          Tamanho sugerido (Kelly)
                        </span>
                      </Tooltip>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1">
                      <span>Full Kelly: <strong className="text-white font-mono">{(result.kelly_pct * 100).toFixed(2)}%</strong> do bankroll</span>
                      <span>1/4 Kelly: <strong className="text-brand-400 font-mono">{(result.quarter_kelly_pct * 100).toFixed(2)}%</strong> (recomendado)</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
