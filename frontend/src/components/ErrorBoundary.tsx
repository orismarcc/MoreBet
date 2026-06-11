import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the original stack visible in the console for debugging.
    console.error('Unhandled error in MoreBet UI:', error, info.componentStack)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen bg-surface-900 flex items-center justify-center px-4">
        <div className="card max-w-md text-center space-y-4">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl
                          bg-red-500/20 border border-red-500/30 mx-auto">
            <AlertTriangle size={28} className="text-red-400" />
          </div>
          <h1 className="text-lg font-bold text-white">Algo deu errado</h1>
          <p className="text-sm text-surface-400">
            A tela quebrou de forma inesperada. O erro foi logado no console do navegador.
          </p>
          <pre className="text-[11px] text-left text-red-300 bg-surface-900 rounded-lg p-3 overflow-auto max-h-32">
            {this.state.error.message}
          </pre>
          <button onClick={this.reset} className="btn-primary w-full">
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }
}
