import { useState } from 'react'
import { motion } from 'framer-motion'
import { LogIn, TrendingUp } from 'lucide-react'
import { authApi } from '../lib/api'
import Spinner from '../components/Spinner'

interface Props {
  onLogin: (token: string, email: string) => void
}

export default function Login({ onLogin }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await authApi.login(email, password)
      onLogin(res.access_token, res.email)
    } catch {
      setError('Email ou senha incorretos.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl
                       bg-brand-500/20 border border-brand-500/30 mb-4"
          >
            <TrendingUp size={28} className="text-brand-400" />
          </motion.div>
          <h1 className="text-2xl font-bold text-white">
            More<span className="text-brand-500">Bet</span>
          </h1>
          <p className="text-surface-400 text-sm mt-1">Odds com inteligência</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="card space-y-4">
          <div>
            <label className="label mb-1.5 block">Email</label>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="seu@email.com"
              required
              className="input-field"
            />
          </div>

          <div>
            <label className="label mb-1.5 block">Senha</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="input-field"
            />
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-sm text-red-400"
            >
              {error}
            </motion.p>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="btn-primary w-full flex items-center justify-center gap-2 py-3"
          >
            {loading ? <Spinner size={18} /> : <LogIn size={18} />}
            Entrar
          </button>
        </form>
      </motion.div>
    </div>
  )
}
