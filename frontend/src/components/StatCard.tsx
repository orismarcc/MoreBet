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
}

const highlightColors = {
  green: 'text-brand-400',
  red: 'text-red-400',
  yellow: 'text-yellow-400',
  blue: 'text-blue-400',
  none: 'text-white',
}

export default function StatCard({
  label, value, sub, tooltip, highlight = 'none', delay = 0, icon,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="card flex flex-col gap-1"
    >
      <div className="flex items-center gap-1.5">
        {icon && <span className="text-surface-400">{icon}</span>}
        {tooltip ? (
          <Tooltip content={tooltip}>
            <span className="label cursor-help border-b border-dashed border-surface-500">
              {label}
            </span>
          </Tooltip>
        ) : (
          <span className="label">{label}</span>
        )}
      </div>
      <span className={`text-2xl font-bold font-mono ${highlightColors[highlight]}`}>
        {value}
      </span>
      {sub && <span className="text-xs text-surface-400">{sub}</span>}
    </motion.div>
  )
}
