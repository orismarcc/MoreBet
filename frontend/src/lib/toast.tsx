import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'

type ToastKind = 'success' | 'error' | 'info'

interface Toast {
  id: number
  kind: ToastKind
  message: string
}

interface ToastApi {
  push: (kind: ToastKind, message: string) => void
  success: (m: string) => void
  error: (m: string) => void
  info: (m: string) => void
}

const ToastCtx = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}

const ICON = { success: CheckCircle2, error: AlertCircle, info: Info } as const
const COLOR = {
  success: 'border-brand-500/40 bg-brand-500/10 text-brand-300',
  error:   'border-red-500/40   bg-red-500/10   text-red-300',
  info:    'border-blue-500/40  bg-blue-500/10  text-blue-300',
} as const

function ToastItem({ t, onClose }: { t: Toast; onClose: () => void }) {
  const Icon = ICON[t.kind]
  useEffect(() => {
    const id = setTimeout(onClose, 4500)
    return () => clearTimeout(id)
  }, [onClose])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.97 }}
      transition={{ duration: 0.2 }}
      className={`flex items-start gap-2 border rounded-xl px-3 py-2.5 text-sm shadow-lg
                  backdrop-blur bg-surface-800/95 ${COLOR[t.kind]}`}
    >
      <Icon size={16} className="mt-0.5 flex-shrink-0" />
      <span className="flex-1 text-surface-100">{t.message}</span>
      <button onClick={onClose} className="text-surface-400 hover:text-white">
        <X size={14} />
      </button>
    </motion.div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const push = useCallback((kind: ToastKind, message: string) => {
    setToasts(prev => [...prev, { id: Date.now() + Math.random(), kind, message }])
  }, [])

  const api: ToastApi = {
    push,
    success: m => push('success', m),
    error:   m => push('error', m),
    info:    m => push('info', m),
  }

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[min(360px,calc(100vw-2rem))]">
        <AnimatePresence>
          {toasts.map(t => (
            <ToastItem
              key={t.id}
              t={t}
              onClose={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
            />
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  )
}
