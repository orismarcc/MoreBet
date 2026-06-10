import { motion } from 'framer-motion'
import { ReactNode } from 'react'
import Tooltip from './Tooltip'

interface Props {
  label: string
  value: string | number
  sub?: string
  tooltip?: string
  highlight?: 'green' | 'red' | 'yellow' | 'blue' | 'none'
  delay?: number
  icon?: ReactNode
  /** Use 'text' for word-y values so they shrink/wrap instead of overflowing. */
  size?: 'number' | 'text'
}

const highlightColors = {
  green: 'text-brand-400',
  red: 'text-red-400',
  yellow: 'text-yellow-400',
  blue: 'text-blue-400',
  none: 'text-white',
}

export default function StatCard({
  label, value, sub, tooltip, highlight = 'none', delay = 0, icon, size = 'number',
}: Props) {
  const valueClass =
    size === 'number'
      ? 'text-2xl sm:text-3xl font-mono font-bold leading-none tabular-nums'
      : 'text-lg sm:text-xl font-semibold leading-tight break-words'

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="card !p-4 flex flex-col gap-2 min-w-0 h-full"
    >
      <div className="flex items-start gap-1.5 min-w-0">
        {icon && <span className="text-surface-400 flex-shrink-0 mt-0.5">{icon}</span>}
        {tooltip ? (
          <Tooltip content={tooltip}>
            <span className="label cursor-help border-b border-dashed border-surface-500 leading-snug">
              {label}
            </span>
          </Tooltip>
        ) : (
          <span className="label leading-snug">{label}</span>
        )}
      </div>

      <span className={`${valueClass} ${highlightColors[highlight]} min-w-0`}>
        {value}
      </span>

      {sub && <span className="text-xs text-surface-400 leading-snug break-words mt-auto">{sub}</span>}
    </motion.div>
  )
}
