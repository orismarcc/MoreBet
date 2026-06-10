import { motion } from 'framer-motion'
import { ArrowLeft, Swords } from 'lucide-react'
import type { MatchAnalysis } from '../types'
import ProbBar from '../components/ProbBar'
import LambdaDisplay from '../components/LambdaDisplay'
import ScoreHeatmap from '../components/ScoreHeatmap'
import MarketsGrid from '../components/MarketsGrid'
import ValueFinder from '../components/ValueFinder'
import StatCard from '../components/StatCard'

interface Props {
  analysis: MatchAnalysis
  onBack: () => void
}

export default function AnalysisDashboard({ analysis, onBack }: Props) {
  const { home_team: home, away_team: away, markets, fair_odds, top_scores } = analysis

  const topScore = top_scores[0]
  const combinedLambda = analysis.lambda_home + analysis.lambda_away
  const bttsLabel = markets.btts_yes > 0.5 ? 'Sim (favorável)' : 'Não (improvável)'
  const dominance = ((markets.home_win / (1 - markets.draw)) * 100).toFixed(0)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      {/* Header */}
      <div className="sticky top-0 z-10 bg-surface-900/95 backdrop-blur border-b border-surface-700 -mx-4 px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="btn-ghost py-1.5 px-3 flex items-center gap-1.5 text-sm">
            <ArrowLeft size={16} /> Voltar
          </button>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <span className="font-semibold text-white truncate">{home.name}</span>
            <Swords size={14} className="text-brand-500 flex-shrink-0" />
            <span className="font-semibold text-white truncate">{away.name}</span>
          </div>
        </div>
      </div>

      {/* Resumo rápido */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label="Placar mais provável"
          value={`${topScore.home}x${topScore.away}`}
          sub={`${(topScore.prob * 100).toFixed(1)}% de chance`}
          tooltip="O placar com maior probabilidade individual segundo a matriz de Poisson"
          highlight="green"
          delay={0}
        />
        <StatCard
          label="Gols esperados (total)"
          value={combinedLambda.toFixed(2)}
          sub={`${home.name}: ${analysis.lambda_home.toFixed(2)} · ${away.name}: ${analysis.lambda_away.toFixed(2)}`}
          tooltip="Soma dos lambdas de cada time — indica a expectativa total de gols"
          highlight="blue"
          delay={0.05}
        />
        <StatCard
          label="BTTS (ambos marcam)"
          value={bttsLabel}
          sub={`${(markets.btts_yes * 100).toFixed(1)}% de probabilidade`}
          tooltip="Probabilidade de ambos os times marcarem ao menos 1 gol"
          highlight={markets.btts_yes > 0.5 ? 'yellow' : 'none'}
          delay={0.1}
        />
        <StatCard
          label="Dominância (sem empate)"
          value={`${dominance}% ${home.name}`}
          sub={`Quando há resultado, ${home.name} vence ${dominance}% das vezes`}
          tooltip="Percentual de vitória do mandante desconsiderando a probabilidade de empate"
          delay={0.15}
        />
      </div>

      {/* Barra de probabilidades */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <ProbBar
          homeProb={markets.home_win}
          drawProb={markets.draw}
          awayProb={markets.away_win}
          homeName={home.name}
          awayName={away.name}
        />
      </motion.div>

      {/* Lambda */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
        <LambdaDisplay
          lambdaHome={analysis.lambda_home}
          lambdaAway={analysis.lambda_away}
          homeName={home.name}
          awayName={away.name}
          homeModifier={analysis.home_modifier}
          awayModifier={analysis.away_modifier}
        />
      </motion.div>

      {/* Heatmap */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <ScoreHeatmap
          topScores={top_scores}
          homeName={home.name}
          awayName={away.name}
        />
      </motion.div>

      {/* Value Finder */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
        <ValueFinder
          fairOdds={fair_odds}
          homeName={home.name}
          awayName={away.name}
        />
      </motion.div>

      {/* Todos os mercados */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
        <MarketsGrid
          markets={markets}
          fairOdds={fair_odds}
          homeName={home.name}
          awayName={away.name}
        />
      </motion.div>
    </motion.div>
  )
}
