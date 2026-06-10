import { motion } from 'framer-motion'
import Tooltip from './Tooltip'

interface Props {
  lambdaHome: number
  lambdaAway: number
  homeName: string
  awayName: string
  homeModifier: number
  awayModifier: number
}

export default function LambdaDisplay({
  lambdaHome, lambdaAway, homeName, awayName, homeModifier, awayModifier,
}: Props) {
  const maxLambda = Math.max(lambdaHome, lambdaAway, 3)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <p className="label">Gols Esperados (λ)</p>
        <Tooltip content="λ (lambda) é a média de gols esperados de cada time neste confronto, calculada pelo modelo de Poisson com forças de ataque/defesa normalizadas pelas médias da liga.">
          <span className="text-xs text-surface-400 border-b border-dashed border-surface-500 cursor-help">
            Como é calculado?
          </span>
        </Tooltip>
      </div>

      <div className="space-y-4">
        {[
          { name: homeName, lambda: lambdaHome, modifier: homeModifier, color: 'bg-brand-500' },
          { name: awayName, lambda: lambdaAway, modifier: awayModifier, color: 'bg-red-500' },
        ].map(({ name, lambda, modifier, color }) => (
          <div key={name}>
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <span className="text-sm text-surface-300 truncate min-w-0">{name}</span>
              <div className="flex items-center gap-2 flex-shrink-0">
                {modifier < 1 && (
                  <Tooltip content={`Redução de ${((1 - modifier) * 100).toFixed(0)}% por desfalques`}>
                    <span className="text-xs text-yellow-400 font-mono cursor-help">
                      ×{modifier.toFixed(2)}
                    </span>
                  </Tooltip>
                )}
                <span className="text-xl font-bold font-mono text-white">{lambda.toFixed(3)}</span>
              </div>
            </div>
            <div className="h-2.5 bg-surface-600 rounded-full overflow-hidden">
              <motion.div
                className={`h-full ${color} rounded-full`}
                initial={{ width: 0 }}
                animate={{ width: `${(lambda / maxLambda) * 100}%` }}
                transition={{ duration: 0.7, ease: 'easeOut', delay: 0.1 }}
              />
            </div>
            <p className="text-xs text-surface-400 mt-1">
              {lambda.toFixed(2)} gols esperados · P(0 gols) = {(Math.exp(-lambda) * 100).toFixed(1)}%
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
