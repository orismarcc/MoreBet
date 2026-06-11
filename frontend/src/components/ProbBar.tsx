import { motion } from 'framer-motion'

interface Props {
  homeProb: number
  drawProb: number
  awayProb: number
  homeName: string
  awayName: string
}

export default function ProbBar({ homeProb, drawProb, awayProb, homeName, awayName }: Props) {
  const fmt = (p: number) => `${(p * 100).toFixed(1)}%`

  const segments = [
    { key: 'home', label: homeName, prob: homeProb, bar: 'bg-brand-500',  dot: 'bg-brand-500',  text: 'text-brand-300' },
    { key: 'draw', label: 'Empate', prob: drawProb, bar: 'bg-surface-500', dot: 'bg-surface-500', text: 'text-surface-300' },
    { key: 'away', label: awayName, prob: awayProb, bar: 'bg-red-500',    dot: 'bg-red-500',    text: 'text-red-300' },
  ]

  return (
    <div className="card">
      <p className="label mb-3">Probabilidades 1X2</p>

      {/* Barra empilhada — larguras aplicadas direto nos segmentos */}
      <div className="flex h-9 rounded-lg overflow-hidden gap-px">
        {segments.map((s, i) => (
          <motion.div
            key={s.key}
            title={`${s.label}: ${fmt(s.prob)}`}
            className={`h-full ${s.bar} flex items-center justify-center min-w-0`}
            initial={{ width: 0 }}
            animate={{ width: `${s.prob * 100}%` }}
            transition={{ duration: 0.7, ease: 'easeOut', delay: 0.1 + i * 0.08 }}
          >
            {s.prob >= 0.12 && (
              <span className={`text-xs font-bold px-1 truncate ${
                s.key === 'draw' ? 'text-surface-200' : 'text-white'
              }`}>
                {fmt(s.prob)}
              </span>
            )}
          </motion.div>
        ))}
      </div>

      {/* Legenda com valores — garante leitura mesmo em segmentos estreitos */}
      <div className="grid grid-cols-3 gap-2 mt-3">
        {segments.map(s => (
          <div key={s.key} className="flex items-center gap-1.5 min-w-0">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.dot}`} />
            <span className="text-xs text-surface-400 truncate">{s.label}</span>
            <span className={`text-xs font-mono font-semibold tabular-nums ml-auto ${s.text}`}>
              {fmt(s.prob)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
