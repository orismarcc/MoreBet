import { motion } from 'framer-motion'
import Tooltip from './Tooltip'

interface Props {
  homeProb: number
  drawProb: number
  awayProb: number
  homeName: string
  awayName: string
}

export default function ProbBar({ homeProb, drawProb, awayProb, homeName, awayName }: Props) {
  const fmt = (p: number) => `${(p * 100).toFixed(1)}%`

  return (
    <div className="card">
      <p className="label mb-3">Probabilidades 1X2</p>

      <div className="flex items-center gap-1 h-10 rounded-lg overflow-hidden">
        <Tooltip content={`${homeName}: ${fmt(homeProb)}`}>
          <motion.div
            className="h-full bg-brand-500 flex items-center justify-center cursor-help"
            initial={{ width: 0 }}
            animate={{ width: `${homeProb * 100}%` }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 }}
          >
            <span className="text-xs font-bold text-white px-1 truncate">{fmt(homeProb)}</span>
          </motion.div>
        </Tooltip>

        <Tooltip content={`Empate: ${fmt(drawProb)}`}>
          <motion.div
            className="h-full bg-surface-500 flex items-center justify-center cursor-help"
            initial={{ width: 0 }}
            animate={{ width: `${drawProb * 100}%` }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
          >
            <span className="text-xs font-semibold text-surface-300 px-1">{fmt(drawProb)}</span>
          </motion.div>
        </Tooltip>

        <Tooltip content={`${awayName}: ${fmt(awayProb)}`}>
          <motion.div
            className="h-full bg-red-500 flex items-center justify-center cursor-help"
            initial={{ width: 0 }}
            animate={{ width: `${awayProb * 100}%` }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.3 }}
          >
            <span className="text-xs font-bold text-white px-1 truncate">{fmt(awayProb)}</span>
          </motion.div>
        </Tooltip>
      </div>

      <div className="flex justify-between mt-2 text-xs text-surface-400">
        <span>{homeName}</span>
        <span>Empate</span>
        <span>{awayName}</span>
      </div>
    </div>
  )
}
