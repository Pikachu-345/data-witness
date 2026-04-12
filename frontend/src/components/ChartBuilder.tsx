import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, BarChart3 } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line, PieChart, Pie, Cell, ScatterChart, Scatter } from 'recharts'
import { buildChart } from '../api/client'

const COLORS = ['#7c3aed', '#0ea5e9', '#22c55e', '#f59e0b', '#f43f5e', '#8b5cf6', '#14b8a6', '#ec4899']

interface Props { sessionId: string; profile: Record<string, any> }

export function ChartBuilder({ sessionId, profile }: Props) {
  const metrics = Object.keys(profile.metrics ?? {})
  const dims = Object.keys(profile.dimensions ?? {})
  const hasTime = !!profile.time?.order_date

  const [xCol, setXCol] = useState(dims[0] ?? '')
  const [yMetric, setYMetric] = useState(metrics[0] ?? '')
  const [chartType, setChartType] = useState('bar')
  const [agg, setAgg] = useState('sum')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const build = async () => {
    setLoading(true); setError(null)
    try {
      const res = await buildChart(sessionId, { x_column: xCol, y_metric: yMetric, chart_type: chartType, aggregation: agg })
      setResult(res)
    } catch (e: any) { setError(e.response?.data?.detail || 'Failed to build chart') }
    finally { setLoading(false) }
  }

  const tooltipStyle = {
    contentStyle: { background: 'white', border: '1px solid #e2d9f3', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' },
    labelStyle: { color: '#42145F', fontWeight: 700 },
  }

  const selectStyle = {
    border: '1px solid var(--border)', background: 'white', color: 'var(--text-primary)',
    borderRadius: 12, padding: '10px 14px', fontSize: 13, outline: 'none', minWidth: 140,
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <BarChart3 size={20} style={{ color: '#7c3aed' }} />
        <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Chart Builder</h3>
      </div>

      {/* Controls */}
      <div className="glass p-5 mb-6 flex flex-wrap items-end gap-4" style={{ borderRadius: 20 }}>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>X-Axis</label>
          <select value={xCol} onChange={e => setXCol(e.target.value)} style={selectStyle}>
            {hasTime && <option value="__time__">Time (Monthly)</option>}
            {dims.map(d => <option key={d} value={d}>{d.replace(/_/g, ' ')}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>Y-Axis</label>
          <select value={yMetric} onChange={e => setYMetric(e.target.value)} style={selectStyle}>
            {metrics.map(m => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>Type</label>
          <select value={chartType} onChange={e => setChartType(e.target.value)} style={selectStyle}>
            <option value="bar">Bar Chart</option>
            <option value="line">Line Chart</option>
            <option value="pie">Pie Chart</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>Aggregation</label>
          <select value={agg} onChange={e => setAgg(e.target.value)} style={selectStyle}>
            <option value="sum">Sum</option>
            <option value="mean">Average</option>
            <option value="count">Count</option>
            <option value="median">Median</option>
          </select>
        </div>
        <button onClick={build} disabled={loading}
          className="btn-primary gap-2" style={{ borderRadius: 14, padding: '10px 24px' }}>
          {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Play size={14} />}
          Build
        </button>
      </div>

      {error && <p className="text-sm font-semibold mb-4" style={{ color: 'var(--error)' }}>{error}</p>}

      {/* Chart result */}
      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="glass p-6" style={{ borderRadius: 20 }}>
            <p className="text-sm font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
              {yMetric.replace(/_/g, ' ')} by {xCol === '__time__' ? 'Time' : xCol.replace(/_/g, ' ')} ({agg})
            </p>

            {result.chart_type === 'bar' && (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={result.data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(66,20,95,0.08)" />
                  <XAxis dataKey="x" tick={{ fill: '#7c6b96', fontSize: 10 }} angle={-30} textAnchor="end" height={70} />
                  <YAxis tick={{ fill: '#7c6b96', fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} />
                  <Bar dataKey="y" radius={[8, 8, 0, 0]}>
                    {result.data.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}

            {result.chart_type === 'line' && (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={result.data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(66,20,95,0.08)" />
                  <XAxis dataKey="x" tick={{ fill: '#7c6b96', fontSize: 10 }} angle={-30} textAnchor="end" height={70} />
                  <YAxis tick={{ fill: '#7c6b96', fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} />
                  <Line type="monotone" dataKey="y" stroke="#7c3aed" strokeWidth={2.5} dot={{ fill: '#7c3aed', r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}

            {result.chart_type === 'pie' && (
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie data={result.data} dataKey="y" nameKey="x" cx="50%" cy="50%" outerRadius={120} label={({ x, percent }: any) => `${x} (${(percent*100).toFixed(0)}%)`}>
                    {result.data.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
