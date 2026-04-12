import { motion } from 'framer-motion'
import { Database, BarChart3, Layers, Calendar, Sparkles, ArrowRight, Hash, DollarSign, Percent, Activity } from 'lucide-react'
import type { DatasetInfo } from '../types'

const METRIC_COLORS = ['#7c3aed', '#0ea5e9', '#22c55e', '#f59e0b', '#f43f5e', '#8b5cf6']
const DIM_COLORS = ['#3b82f6', '#14b8a6', '#a855f7', '#f97316', '#06b6d4', '#ec4899', '#84cc16']

const UNIT_ICONS: Record<string, any> = {
  USD: DollarSign, count: Hash, percent: Percent, value: Activity,
}

interface Props {
  dataset: DatasetInfo
  onStartQuerying: () => void
}

export function DatasetProfileView({ dataset, onStartQuerying }: Props) {
  const profile = dataset.profile ?? {}
  const metrics = Object.entries(profile.metrics ?? {})
  const dimensions = Object.entries(profile.dimensions ?? {})
  const timeCol = (profile.time as any)?.order_date?.column ?? null
  const suggested = dataset.suggested_queries ?? []

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
      className="max-w-5xl mx-auto">

      {/* ── Hero header ──────────────────────────────────────────── */}
      <div className="hero-gradient rounded-3xl p-10 mb-10 text-center relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '32px 32px' }} />
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl mx-auto mb-5 flex items-center justify-center"
            style={{ background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(8px)' }}>
            <Database size={32} className="text-white" />
          </div>
          <h2 className="text-3xl md:text-4xl font-black text-white mb-3">Your Data is Ready</h2>
          <p className="text-base text-white/70 max-w-lg mx-auto">
            We've analysed your dataset and auto-detected everything. Here's what we found.
          </p>
          <div className="flex flex-wrap justify-center gap-4 mt-6">
            {[
              { label: 'Rows', value: dataset.row_count.toLocaleString(), icon: '📊' },
              { label: 'Columns', value: dataset.columns.length.toString(), icon: '📋' },
              { label: 'Metrics', value: metrics.length.toString(), icon: '📈' },
              { label: 'Dimensions', value: dimensions.length.toString(), icon: '🏷️' },
            ].map(s => (
              <div key={s.label} className="px-5 py-3 rounded-2xl text-center"
                style={{ background: 'rgba(255,255,255,0.12)', minWidth: 100 }}>
                <div className="text-2xl mb-1">{s.icon}</div>
                <div className="text-xl font-black text-white">{s.value}</div>
                <div className="text-xs text-white/50 font-semibold">{s.label}</div>
              </div>
            ))}
          </div>
          {dataset.date_range?.start && (
            <div className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold"
              style={{ background: 'rgba(255,255,255,0.15)', color: 'white' }}>
              <Calendar size={13} />
              {dataset.date_range.start.slice(0, 10)} → {dataset.date_range.end.slice(0, 10)}
            </div>
          )}
        </div>
      </div>

      {/* ── Metrics section ──────────────────────────────────────── */}
      {metrics.length > 0 && (
        <div className="mb-10">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: '#f3f0ff' }}>
              <BarChart3 size={16} style={{ color: '#7c3aed' }} />
            </div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Detected Metrics</h3>
              <p className="text-xs" style={{ color: 'var(--text-dim)' }}>{metrics.length} numeric fields available for analysis</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {metrics.map(([key, meta]: [string, any], i) => {
              const color = METRIC_COLORS[i % METRIC_COLORS.length]
              const UnitIcon = UNIT_ICONS[meta.unit] || Activity
              return (
                <motion.div key={key}
                  initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.06 }}
                  className="glass glass-hover p-5" style={{ borderLeft: `4px solid ${color}`, borderRadius: 20 }}>
                  <div className="flex items-start justify-between mb-3">
                    <h4 className="text-base font-bold capitalize" style={{ color: 'var(--text-primary)' }}>
                      {key.replace(/_/g, ' ')}
                    </h4>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${color}12` }}>
                      <UnitIcon size={16} style={{ color }} />
                    </div>
                  </div>
                  <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                    Column: <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{meta.column}</span>
                  </p>
                  <div className="flex gap-2">
                    <span className="text-xs font-bold px-3 py-1 rounded-full"
                      style={{ background: `${color}10`, color, border: `1px solid ${color}25` }}>
                      {meta.aggregation}
                    </span>
                    <span className="text-xs font-bold px-3 py-1 rounded-full"
                      style={{ background: '#f3f0ff', color: '#42145F' }}>
                      {meta.unit}
                    </span>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Dimensions section ───────────────────────────────────── */}
      {dimensions.length > 0 && (
        <div className="mb-10">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: '#e0f7ff' }}>
              <Layers size={16} style={{ color: '#0ea5e9' }} />
            </div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Detected Dimensions</h3>
              <p className="text-xs" style={{ color: 'var(--text-dim)' }}>{dimensions.length} categorical fields for grouping & filtering</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {dimensions.map(([key, meta]: [string, any], i) => {
              const color = DIM_COLORS[i % DIM_COLORS.length]
              const vals = (meta.values ?? []) as string[]
              return (
                <motion.div key={key}
                  initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.06 }}
                  className="glass glass-hover p-5" style={{ borderTop: `3px solid ${color}`, borderRadius: 20 }}>
                  <h4 className="text-base font-bold capitalize mb-1" style={{ color: 'var(--text-primary)' }}>
                    {key.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                    Column: <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{meta.column}</span>
                    {vals.length > 0 && ` · ${vals.length} values`}
                  </p>
                  {vals.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {vals.slice(0, 6).map((v: string) => (
                        <span key={v} className="text-xs font-medium px-2.5 py-1 rounded-lg"
                          style={{ background: `${color}08`, color: `${color}`, border: `1px solid ${color}20`, fontSize: 11 }}>
                          {v}
                        </span>
                      ))}
                      {vals.length > 6 && (
                        <span className="text-xs font-medium px-2.5 py-1 rounded-lg"
                          style={{ background: '#f3f0ff', color: 'var(--text-dim)', fontSize: 11 }}>
                          +{vals.length - 6} more
                        </span>
                      )}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Suggested queries ────────────────────────────────────── */}
      {suggested.length > 0 && (
        <div className="mb-10">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: '#fef3c7' }}>
              <Sparkles size={16} style={{ color: '#f59e0b' }} />
            </div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>AI-Generated Questions</h3>
              <p className="text-xs" style={{ color: 'var(--text-dim)' }}>Smart suggestions based on your data structure</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggested.slice(0, 8).map((q, i) => (
              <motion.button key={q}
                initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                onClick={onStartQuerying}
                className="glass glass-hover p-4 text-left flex items-center gap-3 group"
                style={{ borderRadius: 16, cursor: 'pointer' }}>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: '#f3f0ff' }}>
                  <span className="text-xs font-black" style={{ color: '#7c3aed' }}>{i + 1}</span>
                </div>
                <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>{q}</span>
                <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: '#7c3aed' }} />
              </motion.button>
            ))}
          </div>
        </div>
      )}

      {/* ── CTA ──────────────────────────────────────────────────── */}
      <div className="text-center pb-8">
        <motion.button
          whileHover={{ scale: 1.04, y: -2 }}
          whileTap={{ scale: 0.98 }}
          onClick={onStartQuerying}
          className="btn-primary gap-3 text-lg px-14 py-4"
          style={{ borderRadius: 20, fontSize: 16 }}>
          <Sparkles size={20} />
          Start Querying Your Data
          <ArrowRight size={20} />
        </motion.button>
        <p className="text-xs mt-4" style={{ color: 'var(--text-dim)' }}>
          Ask anything in plain English — our AI handles the rest
        </p>
      </div>
    </motion.div>
  )
}
