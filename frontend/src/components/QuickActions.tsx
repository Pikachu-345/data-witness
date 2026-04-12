import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { TrendingUp, Award, BarChart3, GitBranch, X } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line, Cell } from 'recharts'
import { quickAction } from '../api/client'

const ACTIONS = [
  { action: 'trends', icon: TrendingUp, label: 'Show Trends', desc: 'Time series of primary metric', color: '#0ea5e9' },
  { action: 'top10', icon: Award, label: 'Top 10', desc: 'Highest values by dimension', color: '#22c55e' },
  { action: 'distribution', icon: BarChart3, label: 'Distribution', desc: 'Histogram of metric values', color: '#f59e0b' },
  { action: 'correlation', icon: GitBranch, label: 'Correlations', desc: 'Metric relationships', color: '#f43f5e' },
]

interface Props { sessionId: string }

export function QuickActions({ sessionId }: Props) {
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (action: string) => {
    setLoading(action); setError(null)
    try {
      const res = await quickAction(sessionId, { action })
      setResult(res)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Action failed')
      setResult(null)
    } finally { setLoading(null) }
  }

  const tooltipStyle = {
    contentStyle: { background: 'white', border: '1px solid #e2d9f3', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' },
    labelStyle: { color: '#42145F', fontWeight: 700 },
  }

  return (
    <div className="mb-6">
      <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--text-dim)' }}>
        ⚡ Quick Analytics
      </p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        {ACTIONS.map(a => (
          <button key={a.action} onClick={() => run(a.action)} disabled={loading === a.action}
            className="glass glass-hover p-4 text-left transition-all"
            style={{ borderTop: `3px solid ${a.color}`, borderRadius: 20, cursor: 'pointer', background: 'white' }}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${a.color}12` }}>
                {loading === a.action
                  ? <div className="spinner" style={{ width: 14, height: 14, borderTopColor: a.color }} />
                  : <a.icon size={16} style={{ color: a.color }} />}
              </div>
              <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{a.label}</span>
            </div>
            <p className="text-xs" style={{ color: 'var(--text-dim)' }}>{a.desc}</p>
          </button>
        ))}
      </div>

      {error && <p className="text-xs font-semibold mb-3" style={{ color: 'var(--error)' }}>{error}</p>}

      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="glass p-6" style={{ borderRadius: 20 }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{result.title}</h3>
              <button onClick={() => setResult(null)} style={{ color: 'var(--text-dim)', cursor: 'pointer', background: 'none', border: 'none' }}>
                <X size={16} />
              </button>
            </div>

            {(result.chart_type === 'line') && (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={result.data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(66,20,95,0.08)" />
                  <XAxis dataKey="x" tick={{ fill: '#7c6b96', fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                  <YAxis tick={{ fill: '#7c6b96', fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} />
                  <Line type="monotone" dataKey="y" stroke="#7c3aed" strokeWidth={2.5} dot={{ fill: '#7c3aed', r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}

            {(result.chart_type === 'bar') && (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={result.data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(66,20,95,0.08)" />
                  <XAxis dataKey="x" tick={{ fill: '#7c6b96', fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                  <YAxis tick={{ fill: '#7c6b96', fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} />
                  <Bar dataKey="y" radius={[6, 6, 0, 0]}>
                    {result.data.map((_: any, i: number) => (
                      <Cell key={i} fill={['#7c3aed', '#0ea5e9', '#22c55e', '#f59e0b', '#f43f5e', '#8b5cf6', '#14b8a6', '#ec4899'][i % 8]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}

            {(result.chart_type === 'heatmap') && result.data?.matrix && (
              <div className="overflow-x-auto" style={{ borderRadius: 12 }}>
                <table className="data-table">
                  <thead>
                    <tr><th></th>{(result.data.columns as string[]).map((c: string) => <th key={c}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {(result.data.matrix as number[][]).map((row: number[], i: number) => (
                      <tr key={i}>
                        <td className="font-bold">{result.data.columns[i]}</td>
                        {row.map((v: number, j: number) => (
                          <td key={j} className="tabular-nums text-center" style={{
                            background: i === j ? '#f3f0ff' : v > 0.5 ? `rgba(34,197,94,${Math.abs(v) * 0.3})` : v < -0.5 ? `rgba(239,68,68,${Math.abs(v) * 0.3})` : undefined,
                            fontWeight: Math.abs(v) > 0.5 ? 700 : 400,
                          }}>{v.toFixed(2)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {result.stats && (
              <div className="flex gap-4 mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                {Object.entries(result.stats).map(([k, v]) => (
                  <span key={k}><strong>{k}:</strong> {typeof v === 'number' ? (v as number).toLocaleString() : String(v)}</span>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
