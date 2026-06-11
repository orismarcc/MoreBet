import { motion } from 'framer-motion'
import { Activity } from 'lucide-react'
import TeamFormPanel from './TeamFormPanel'

interface Props {
  homeTeamId: number
  awayTeamId: number
  homeName: string
  awayName: string
}

export default function RecentForm({ homeTeamId, awayTeamId, homeName, awayName }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
    >
      <div className="section-title mb-4">
        <Activity size={16} className="text-brand-400" />
        <h3>Forma recente</h3>
        <span className="text-xs text-surface-400 font-normal">· últimos jogos de cada time</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <TeamFormPanel source={{ kind: 'db', id: homeTeamId }} name={homeName} />
        <TeamFormPanel source={{ kind: 'db', id: awayTeamId }} name={awayName} />
      </div>
    </motion.div>
  )
}
