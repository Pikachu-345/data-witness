import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Award, AlertTriangle, PieChart, GitBranch, ArrowRight } from 'lucide-react'
import { getSmartInsights } from '../api/client'

const ICONS: Record<string, any> = {
  trend: TrendingUp, top: Award, anomaly: AlertTriangle,
  distribution: PieChart, correlation: GitBranch, info: TrendingUp,
}
const COLORS: Record<string, string> = {
  trend: '#0ea5e9', top: '#22c55e', anomaly: '#f59e0b',
  distribution: '#7c3aed', correlation: '#f43f5e', info: '#3b82f6',
}

interface Props { sessionId: string; onExplore: (q: string) => void }

export function SmartInsightsPanel({ sessionId, onExplore }: Props) {
  const [insights, setInsights] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getSmartInsights(sessionId)
      .then(res => setInsights(res.insights || []))
      .catch(() => setInsights([]))
      .finally(() => setLoading(false))
  }, [sessionId])

  if (loading) {
    return (
      <div className="mb-8">
        <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--text-dim)' }}>
          Discovering insights...
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass p-5 animate-pulse" style={{ height: 100, borderRadius: 20 }} />
          ))}
        </div>
      </div>
    )
  }

  if (!insights.length) return null

  return (
    <div className="mb-8">
      <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--text-dim)' }}>
        🧠 AI-Discovered Insights
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {insights.map((ins, i) => {
          const Icon = ICONS[ins.type] || TrendingUp
          const color = COLORS[ins.type] || '#7c3aed'
          return (
            <motion.div key={i}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="glass glass-hover p-5 cursor-pointer group"
              style={{ borderLeft: `4px solid ${color}`, borderRadius: 20 }}
              onClick={() => onExplore(ins.action_query)}>
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: `${color}12` }}>
                  <Icon size={20} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color }}>{ins.title}</p>
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                    {ins.insight_text}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-1 text-xs font-semibold opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color }}>
                Explore <ArrowRight size={12} />
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
