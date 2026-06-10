import { useState, ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  content: string
  children: ReactNode
}

export default function Tooltip({ content, children }: Props) {
  const [visible, setVisible] = useState(false)

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      <AnimatePresence>
        {visible && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50
                       w-56 bg-surface-600 border border-surface-500 rounded-lg
                       px-3 py-2 text-xs text-surface-300 shadow-xl pointer-events-none"
          >
            {content}
            <div className="absolute top-full left-1/2 -translate-x-1/2 border-4
                           border-transparent border-t-surface-600" />
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  )
}
