import { motion } from 'framer-motion'
import type { ScoreProb } from '../types'
import Tooltip from './Tooltip'

interface Props {
  topScores: ScoreProb[]
  homeName: string
  awayName: string
}

const MAX_GOALS = 5

function buildMatrix(topScores: ScoreProb[]): number[][] {
  const matrix: number[][] = Array.from({ length: MAX_GOALS + 1 }, () =>
    new Array(MAX_GOALS + 1).fill(0)
  )
  for (const s of topScores) {
    if (s.home <= MAX_GOALS && s.away <= MAX_GOALS) {
      matrix[s.home][s.away] = s.prob
    }
  }
  return matrix
}

function probToIntensity(prob: number, max: number): number {
  return max > 0 ? prob / max : 0
}

function probToColor(intensity: number): string {
  const r = Math.round(15 + intensity * (34 - 15))
  const g = Math.round(17 + intensity * (197 - 17))
  const b = Math.round(23 + intensity * (94 - 23))
  return `rgba(${r}, ${g}, ${b}, ${0.15 + intensity * 0.85})`
}

export default function ScoreHeatmap({ topScores, homeName, awayName }: Props) {
  const matrix = buildMatrix(topScores)
  const maxProb = Math.max(...topScores.map(s => s.prob))
  const cols = Array.from({ length: MAX_GOALS + 1 }, (_, i) => i)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <p className="label">Matriz de Placares</p>
        <span className="text-xs text-surface-400">Probabilidade por resultado exato</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-surface-400 font-medium pb-2 pr-2 text-left w-16">
                {homeName.slice(0, 8)} ↓ / {awayName.slice(0, 8)} →
              </th>
              {cols.map(a => (
                <th key={a} className="text-surface-400 font-medium pb-2 text-center w-12">
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cols.map((h, ri) => (
              <tr key={h}>
                <td className="text-surface-400 font-medium pr-2 py-1 text-center">{h}</td>
                {cols.map((a, ci) => {
                  const prob = matrix[h][a]
                  const intensity = probToIntensity(prob, maxProb)
                  const isTopScore = topScores.slice(0, 3).some(
                    s => s.home === h && s.away === a
                  )
                  return (
                    <motion.td
                      key={a}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.3, delay: (ri * 6 + ci) * 0.015 }}
                      className="py-1 text-center"
                    >
                      <Tooltip content={`${h}x${a} — ${(prob * 100).toFixed(2)}%`}>
                        <span
                          className={`w-10 sm:w-11 h-8 rounded flex items-center justify-center
                                      font-mono font-semibold cursor-default transition-transform
                                      hover:scale-110 ${isTopScore ? 'ring-1 ring-brand-400' : ''}`}
                          style={{ backgroundColor: probToColor(intensity) }}
                        >
                          {prob > 0.001 ? `${(prob * 100).toFixed(1)}` : '—'}
                        </span>
                      </Tooltip>
                    </motion.td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-2 mt-3">
        <span className="text-xs text-surface-400">Intensidade:</span>
        <div className="flex gap-0.5">
          {[0.1, 0.3, 0.5, 0.7, 1.0].map(v => (
            <div
              key={v}
              className="w-6 h-3 rounded-sm"
              style={{ backgroundColor: probToColor(v) }}
            />
          ))}
        </div>
        <span className="text-xs text-brand-400">Maior probabilidade</span>
      </div>
    </div>
  )
}
