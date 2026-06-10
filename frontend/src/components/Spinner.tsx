import { motion } from 'framer-motion'

interface Props { size?: number; className?: string }

export default function Spinner({ size = 24, className = '' }: Props) {
  return (
    <motion.div
      className={`rounded-full border-2 border-surface-600 border-t-brand-500 ${className}`}
      style={{ width: size, height: size }}
      animate={{ rotate: 360 }}
      transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
    />
  )
}
