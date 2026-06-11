import { motion } from 'framer-motion'
import { ArrowLeft, Swords } from 'lucide-react'
import type { MatchAnalysis } from '../types'
import ProbBar from '../components/ProbBar'
import LambdaDisplay from '../components/LambdaDisplay'
import ScoreHeatmap from '../components/ScoreHeatmap'
import MarketsGrid from '../components/MarketsGrid'
import ValueFinder from '../components/ValueFinder'
import RecentForm from '../components/RecentForm'
import StatCard from '../components/StatCard'

interface Props {
  analysis: MatchAnalysis
  onBack: () => void
}

export default function AnalysisDashboard({ analysis, onBack }: Props) {
  const { home_team: home, away_team: away, markets, fair_odds, top_scores } = analysis

  const topScore = top_scores[0]
  const combinedLambda = analysis.lambda_home + analysis.lambda_away
  const bttsPct = markets.btts_yes * 100
  const bttsFavoured = markets.btts_yes > 0.5
  // Quem domina quando há resultado (descontando empate)
  const resultProb = 1 - markets.draw
  const homeDom = resultProb > 0 ? (markets.home_win / resultProb) * 100 : 50
  const favHome = homeDom >= 50
  const domPct = favHome ? homeDom : 100 - homeDom
  const favName = favHome ? home.name : away.name

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      {/* Header da análise — fica abaixo do header global (h-14) */}
      <div className="sticky top-14 z-20 bg-surface-900/95 backdrop-blur border-b border-surface-600/60 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3">
        <div className="flex items-center gap-3 max-w-5xl mx-auto">
          <button onClick={onBack} className="btn-ghost py-1.5 px-3 flex items-center gap-1.5 text-sm flex-shrink-0">
            <ArrowLeft size={16} /> <span className="hidden xs:inline">Voltar</span>
          </button>
          <div className="flex items-center gap-2 flex-1 min-w-0 justify-center sm:justify-start">
            {home.logo_url && <img src={home.logo_url} alt="" className="w-6 h-6 object-contain flex-shrink-0" />}
            <span className="font-semibold text-white truncate">{home.name}</span>
            <Swords size={14} className="text-brand-400 flex-shrink-0" />
            <span className="font-semibold text-white truncate">{away.name}</span>
            {away.logo_url && <img src={away.logo_url} alt="" className="w-6 h-6 object-contain flex-shrink-0" />}
          </div>
        </div>
      </div>

      {/* Resumo rápido */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Placar mais provável"
          value={`${topScore.home}×${topScore.away}`}
          sub={`${(topScore.prob * 100).toFixed(1)}% de chance`}
          tooltip="O placar com maior probabilidade individual segundo a matriz de Poisson"
          highlight="green"
          delay={0}
        />
        <StatCard
          label="Gols esperados (total)"
          value={combinedLambda.toFixed(2)}
          sub={`${home.short_name ?? 'Casa'} ${analysis.lambda_home.toFixed(2)} · ${away.short_name ?? 'Fora'} ${analysis.lambda_away.toFixed(2)}`}
          tooltip="Soma dos lambdas (λ) de cada time — a expectativa total de gols na partida"
          highlight="blue"
          delay={0.05}
        />
        <StatCard
          label="Ambos marcam (BTTS)"
          value={`${bttsPct.toFixed(0)}%`}
          sub={bttsFavoured ? 'Provável — tendência de sim' : 'Improvável — tendência de não'}
          tooltip="Probabilidade de ambos os times marcarem ao menos 1 gol"
          highlight={bttsFavoured ? 'yellow' : 'none'}
          delay={0.1}
        />
        <StatCard
          label="Dominância (sem empate)"
          value={`${domPct.toFixed(0)}%`}
          sub={`${favName} vence quando há resultado`}
          tooltip="Descontando a chance de empate, com que frequência o favorito vence"
          highlight={favHome ? 'green' : 'red'}
          delay={0.15}
        />
      </div>

      {/* Probabilidades + λ | Heatmap — lado a lado no desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-5"
        >
          <ProbBar
            homeProb={markets.home_win}
            drawProb={markets.draw}
            awayProb={markets.away_win}
            homeName={home.name}
            awayName={away.name}
          />
          <LambdaDisplay
            lambdaHome={analysis.lambda_home}
            lambdaAway={analysis.lambda_away}
            homeName={home.name}
            awayName={away.name}
            homeModifier={analysis.home_modifier}
            awayModifier={analysis.away_modifier}
          />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          <ScoreHeatmap
            topScores={top_scores}
            homeName={home.name}
            awayName={away.name}
          />
        </motion.div>
      </div>

      {/* Forma recente dos dois times */}
      <RecentForm
        homeTeamId={home.id}
        awayTeamId={away.id}
        homeName={home.name}
        awayName={away.name}
      />

      {/* Value Finder | Mercados — lado a lado no desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5 items-start">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="lg:col-span-2 lg:sticky lg:top-[120px]"
        >
          <ValueFinder
            fairOdds={fair_odds}
            homeName={home.name}
            awayName={away.name}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="lg:col-span-3"
        >
          <MarketsGrid
            markets={markets}
            fairOdds={fair_odds}
            homeName={home.name}
            awayName={away.name}
          />
        </motion.div>
      </div>
    </motion.div>
  )
}
