import { useState, useRef, useEffect, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  content: string
  children: ReactNode
}

const TOOLTIP_WIDTH = 224 // w-56
const GAP = 8
const EDGE = 8
// Espaço mínimo acima do gatilho para abrir para cima — cobre a altura típica
// do tooltip (2-4 linhas) + headers fixos (h-14 + sub-header da análise).
const MIN_SPACE_ABOVE = 150

interface Pos {
  x: number
  y: number
  placement: 'top' | 'bottom'
}

export default function Tooltip({ content, children }: Props) {
  const [pos, setPos] = useState<Pos | null>(null)
  const triggerRef = useRef<HTMLSpanElement>(null)

  const show = () => {
    const el = triggerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const placement: Pos['placement'] =
      rect.top >= MIN_SPACE_ABOVE ? 'top' : 'bottom'
    // Centraliza no gatilho, mas nunca deixa o balão sair da tela
    const half = TOOLTIP_WIDTH / 2
    const x = Math.min(
      Math.max(rect.left + rect.width / 2, half + EDGE),
      window.innerWidth - half - EDGE,
    )
    const y = placement === 'top' ? rect.top - GAP : rect.bottom + GAP
    setPos({ x, y, placement })
  }

  const hide = () => setPos(null)

  // Fecha ao rolar/redimensionar — a posição fixa ficaria defasada
  useEffect(() => {
    if (!pos) return
    window.addEventListener('scroll', hide, true)
    window.addEventListener('resize', hide)
    return () => {
      window.removeEventListener('scroll', hide, true)
      window.removeEventListener('resize', hide)
    }
  }, [pos])

  const isTop = pos?.placement === 'top'

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      {children}
      {createPortal(
        <AnimatePresence>
          {pos && (
            // Wrapper fixo cuida do posicionamento (o motion.div interno
            // sobrescreveria o transform ao animar y/scale)
            <div
              style={{
                position: 'fixed',
                left: pos.x,
                top: pos.y,
                width: TOOLTIP_WIDTH,
                transform: `translate(-50%, ${isTop ? '-100%' : '0'})`,
                zIndex: 80,
                pointerEvents: 'none',
              }}
            >
              <motion.div
                initial={{ opacity: 0, y: isTop ? 6 : -6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: isTop ? 6 : -6, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="relative bg-surface-600 border border-surface-500 rounded-lg
                           px-3 py-2 text-xs text-surface-300 shadow-xl"
              >
                {content}
                <div
                  className={`absolute left-1/2 -translate-x-1/2 border-4 border-transparent ${
                    isTop
                      ? 'top-full border-t-surface-600'
                      : 'bottom-full border-b-surface-600'
                  }`}
                />
              </motion.div>
            </div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </span>
  )
}
