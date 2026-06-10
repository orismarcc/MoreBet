import { motion } from 'framer-motion'
import type { Markets, FairOdds } from '../types'
import Tooltip from './Tooltip'

interface Props {
  markets: Markets
  fairOdds: FairOdds
  homeName: string
  awayName: string
}

interface MarketRow {
  label: string
  prob: number
  odds: number
  tooltip: string
}

function pct(p: number) { return `${(p * 100).toFixed(1)}%` }
function odd(o: number) { return o.toFixed(2) }

export default function MarketsGrid({ markets, fairOdds, homeName, awayName }: Props) {
  const sections: { title: string; rows: MarketRow[] }[] = [
    {
      title: 'Resultado Final (1X2)',
      rows: [
        { label: `Vitória ${homeName}`, prob: markets.home_win, odds: fairOdds.home_win, tooltip: 'Probabilidade de vitória do mandante' },
        { label: 'Empate', prob: markets.draw, odds: fairOdds.draw, tooltip: 'Probabilidade de empate' },
        { label: `Vitória ${awayName}`, prob: markets.away_win, odds: fairOdds.away_win, tooltip: 'Probabilidade de vitória do visitante' },
      ],
    },
    {
      title: 'Dupla Chance',
      rows: [
        { label: `${homeName} ou Empate`, prob: markets.home_or_draw, odds: fairOdds.home_or_draw, tooltip: '1X — mandante não perde' },
        { label: `${awayName} ou Empate`, prob: markets.away_or_draw, odds: fairOdds.away_or_draw, tooltip: 'X2 — visitante não perde' },
        { label: `${homeName} ou ${awayName}`, prob: markets.home_or_away, odds: fairOdds.home_or_away, tooltip: '12 — sem empate' },
      ],
    },
    {
      title: 'Gols Over/Under',
      rows: [
        { label: 'Over 0.5', prob: markets.over_05, odds: fairOdds.over_05, tooltip: 'Ao menos 1 gol na partida' },
        { label: 'Over 1.5', prob: markets.over_15, odds: fairOdds.over_15, tooltip: 'Ao menos 2 gols na partida' },
        { label: 'Over 2.5', prob: markets.over_25, odds: fairOdds.over_25, tooltip: 'Ao menos 3 gols na partida' },
        { label: 'Over 3.5', prob: markets.over_35, odds: fairOdds.over_35, tooltip: 'Ao menos 4 gols na partida' },
        { label: 'Under 2.5', prob: markets.under_25, odds: fairOdds.under_25, tooltip: 'Menos de 3 gols na partida' },
        { label: 'Under 3.5', prob: markets.under_35, odds: fairOdds.under_35, tooltip: 'Menos de 4 gols na partida' },
      ],
    },
    {
      title: 'Ambos Marcam (BTTS)',
      rows: [
        { label: 'BTTS Sim', prob: markets.btts_yes, odds: fairOdds.btts_yes, tooltip: 'Ambos os times marcam ao menos 1 gol' },
        { label: 'BTTS Não', prob: markets.btts_no, odds: fairOdds.btts_no, tooltip: 'Ao menos um time não marca' },
      ],
    },
    {
      title: 'Asian Handicap',
      rows: [
        { label: `${homeName} -0.5`, prob: markets.ah_home_minus_half, odds: fairOdds.ah_home_minus_half, tooltip: 'Mandante vence por 1 ou mais gols' },
        { label: `${awayName} -0.5`, prob: markets.ah_away_minus_half, odds: fairOdds.ah_away_minus_half, tooltip: 'Visitante vence por 1 ou mais gols' },
      ],
    },
  ]

  return (
    <div className="card">
      <p className="label mb-4">Todos os Mercados — Odds Justas</p>
      <div className="space-y-5">
        {sections.map((section, si) => (
          <div key={section.title}>
            <p className="text-xs font-semibold text-surface-400 mb-2">{section.title}</p>
            <div className="space-y-1">
              {section.rows.map((row, ri) => (
                <motion.div
                  key={row.label}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: (si * 6 + ri) * 0.04 }}
                  className="flex items-center justify-between py-2 px-3 rounded-lg
                             bg-surface-700/50 hover:bg-surface-700 transition-colors group"
                >
                  <Tooltip content={row.tooltip}>
                    <span className="text-sm text-surface-300 group-hover:text-white
                                     transition-colors cursor-help">
                      {row.label}
                    </span>
                  </Tooltip>
                  <div className="flex items-center gap-4">
                    <div className="w-20 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-brand-500 rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${row.prob * 100}%` }}
                        transition={{ duration: 0.6, delay: (si * 6 + ri) * 0.04 + 0.2 }}
                      />
                    </div>
                    <span className="text-xs text-surface-400 w-10 text-right font-mono">
                      {pct(row.prob)}
                    </span>
                    <span className="text-sm font-bold font-mono text-brand-400 w-12 text-right">
                      {odd(row.odds)}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
