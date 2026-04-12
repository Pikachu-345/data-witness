import type { QueryResponse, ChangeResult, CompareResult, CounterfactualResult } from '../types'

interface Props { result: QueryResponse; eli5: boolean }

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtNum(v: number, unit: string): string {
  const prefix = (unit === 'USD' || unit === '$') ? '$' : ''
  const suffix = unit === 'percent' ? '%' : unit === 'count' ? '' : unit === 'ratio' ? '' : ''
  const abs = Math.abs(v)
  let s: string
  if (abs >= 1_000_000) s = `${(v / 1_000_000).toFixed(2)}M`
  else if (abs >= 1_000) s = `${(v / 1_000).toFixed(1)}K`
  else s = v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return `${prefix}${s}${suffix}`
}

function isStatSummary(table: Record<string, unknown>[]): boolean {
  if (!table?.length) return false
  const firstRow = table[0]
  const keys = Object.keys(firstRow)
  // detect if first column is named 'Statistic' and contains stat names
  if (keys[0] === 'Statistic') {
    const statVals = new Set(table.map(r => String(r['Statistic']).toLowerCase()))
    return ['count', 'mean', 'std'].every(s => statVals.has(s))
  }
  return false
}

// ── Change metrics ────────────────────────────────────────────────────────────

function ChangeMetrics({ comp }: { comp: ChangeResult }) {
  const up   = comp.direction === 'increase'
  const sign = comp.absolute_change >= 0 ? '+' : ''

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
      <MetricCard
        label={comp.period_a.label ?? 'Period A'}
        value={fmtNum(comp.period_a.value, comp.metric_unit)}
        sub={comp.metric_label} />
      <MetricCard
        label={comp.period_b.label ?? 'Period B'}
        value={fmtNum(comp.period_b.value, comp.metric_unit)}
        sub={comp.metric_label} />
      <MetricCard
        label="Change"
        value={`${sign}${comp.pct_change.toFixed(1)}%`}
        sub={`${sign}${fmtNum(comp.absolute_change, comp.metric_unit)}`}
        accent={up ? 'var(--success)' : 'var(--error)'}
        trend={up ? 'up' : 'down'} />
      {comp.contributors[0] && (
        <MetricCard
          label="Top Driver"
          value={comp.contributors[0].entity}
          sub={`${comp.contributors[0].pct_of_total_change >= 0 ? '+' : ''}${comp.contributors[0].pct_of_total_change.toFixed(1)}% · ${comp.contributors[0].dimension}`}
          accent="var(--purple-400)" />
      )}
    </div>
  )
}

// ── Compare metrics ───────────────────────────────────────────────────────────

function CompareMetrics({ comp }: { comp: CompareResult }) {
  const isAWinner = comp.entity_a.label === comp.winner
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
      <MetricCard
        label={comp.entity_a.label}
        value={fmtNum(comp.entity_a.value, comp.metric_unit)}
        sub={comp.metric_label}
        accent={isAWinner ? 'var(--success)' : 'var(--error)'}
        trend={isAWinner ? 'up' : 'down'} />
      <MetricCard
        label={comp.entity_b.label}
        value={fmtNum(comp.entity_b.value, comp.metric_unit)}
        sub={comp.metric_label}
        accent={!isAWinner ? 'var(--success)' : 'var(--error)'}
        trend={!isAWinner ? 'up' : 'down'} />
      <MetricCard
        label="Difference"
        value={`${comp.pct_diff.toFixed(1)}%`}
        sub={fmtNum(Math.abs(comp.absolute_diff), comp.metric_unit)} />
      <MetricCard
        label="Winner"
        value={comp.winner}
        sub={`${comp.metric_label} leader`}
        accent="var(--success)"
        trend="up" />
    </div>
  )
}

// ── Metric card ───────────────────────────────────────────────────────────────

function BreakdownMetrics({ comp }: { comp: any }) {
  const comps = (comp.components ?? []) as any[]
  const colors = ['#7c3aed', '#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

  return (
    <div className="mb-5">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
        <MetricCard label="Total" value={fmtNum(comp.total_value ?? 0, comp.metric_unit ?? '')} sub={comp.metric_label} accent="#7c3aed" />
        <MetricCard label="Broken by" value={comp.dimension_label ?? comp.dimension ?? '-'} sub={`${comp.component_count} components`} />
        <MetricCard label="Concentration" value={comp.concentration ?? '-'} sub={`Top 3 = ${comp.top_3_share_pct ?? 0}%`}
          accent={comp.concentration === 'highly concentrated' ? '#ef4444' : comp.concentration === 'well distributed' ? '#22c55e' : '#f59e0b'} />
      </div>
      {comps.length > 0 && (
        <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
          <table className="data-table">
            <thead><tr><th>#</th><th>Entity</th><th>Value</th><th>Share</th><th style={{ width: '40%' }}>Distribution</th></tr></thead>
            <tbody>
              {comps.slice(0, 10).map((c: any, i: number) => (
                <tr key={i}>
                  <td className="tabular-nums font-bold" style={{ color: colors[i % colors.length] }}>{c.rank}</td>
                  <td className="font-semibold">{c.entity}</td>
                  <td className="tabular-nums">{fmtNum(c.value, comp.metric_unit ?? '')}</td>
                  <td className="tabular-nums font-semibold" style={{ color: '#42145F' }}>{c.share_pct.toFixed(1)}%</td>
                  <td>
                    <div className="w-full rounded-full h-2.5" style={{ background: '#f3f0ff' }}>
                      <div className="h-2.5 rounded-full transition-all" style={{ width: `${Math.min(c.share_pct, 100)}%`, background: colors[i % colors.length] }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SummarizeMetrics({ comp }: { comp: any }) {
  const summaries = (comp.metric_summaries ?? []) as any[]
  const trend = comp.trend as any
  const tb = comp.top_bottom as any

  return (
    <div className="space-y-5 mb-5">
      {/* Stat cards */}
      {summaries.map((s: any) => (
        <div key={s.metric} className="glass p-5" style={{ borderLeft: '4px solid #7c3aed' }}>
          <p className="text-sm font-bold mb-3" style={{ color: '#42145F' }}>{s.metric_label} ({s.unit})</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <MetricCard label="Total" value={fmtNum(s.sum, s.unit)} />
            <MetricCard label="Average" value={fmtNum(s.mean, s.unit)} sub={`Median: ${fmtNum(s.median, s.unit)}`} />
            <MetricCard label="Range" value={`${fmtNum(s.min, s.unit)} — ${fmtNum(s.max, s.unit)}`} sub={`Std Dev: ${fmtNum(s.std, s.unit)}`} />
            <MetricCard label="Volatility" value={`${s.cv}%`}
              accent={s.cv > 100 ? '#ef4444' : s.cv > 50 ? '#f59e0b' : '#22c55e'}
              sub={s.anomaly_count > 0 ? `${s.anomaly_count} anomalies (${s.anomaly_pct}%)` : 'No anomalies'} />
          </div>
        </div>
      ))}

      {/* Trend */}
      {trend && (
        <div className="glass p-4 flex items-center gap-4">
          <div className="text-2xl">{trend.direction === 'upward' ? '📈' : trend.direction === 'downward' ? '📉' : '➡️'}</div>
          <div>
            <p className="text-sm font-bold" style={{ color: '#42145F' }}>
              Trend: {trend.direction} ({trend.pct_change >= 0 ? '+' : ''}{trend.pct_change}%)
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Over {trend.periods} periods · First half avg: {fmtNum(trend.first_half_avg, '')} → Second half: {fmtNum(trend.second_half_avg, '')}
            </p>
          </div>
        </div>
      )}

      {/* Top/Bottom performers */}
      {tb && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="glass p-4">
            <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#22c55e' }}>
              Top Performers ({tb.dimension})
            </p>
            {(tb.top ?? []).map((t: any, i: number) => (
              <div key={i} className="flex justify-between py-1.5 text-sm">
                <span className="font-medium">{t.entity}</span>
                <span className="tabular-nums font-semibold" style={{ color: '#22c55e' }}>{t.share_pct}%</span>
              </div>
            ))}
          </div>
          <div className="glass p-4">
            <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#ef4444' }}>
              Bottom Performers ({tb.dimension})
            </p>
            {(tb.bottom ?? []).map((t: any, i: number) => (
              <div key={i} className="flex justify-between py-1.5 text-sm">
                <span className="font-medium">{t.entity}</span>
                <span className="tabular-nums font-semibold" style={{ color: '#ef4444' }}>{t.share_pct}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CounterfactualMetrics({ comp }: { comp: CounterfactualResult }) {
  const actual = comp.actual
  const cf = comp.counterfactual
  const sign = actual.pct_change >= 0 ? '+' : ''
  const cfSign = cf.pct_change >= 0 ? '+' : ''

  return (
    <div className="space-y-3 mb-5">
      <div className="glass p-4" style={{ borderLeft: '3px solid #d97706' }}>
        <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: '#a16207' }}>
          Counterfactual: Without {comp.entity_removed} ({comp.dimension})
        </p>
        <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
          The {comp.metric_label} change would have been <strong>{cfSign}{cf.pct_change.toFixed(1)}%</strong> instead of <strong>{sign}{actual.pct_change.toFixed(1)}%</strong>
        </p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Actual Change"
          value={`${sign}${actual.pct_change.toFixed(1)}%`}
          sub={`${sign}${fmtNum(actual.absolute_change, comp.metric_unit)}`}
          accent={actual.direction === 'increase' ? 'var(--success)' : 'var(--error)'}
          trend={actual.direction === 'increase' ? 'up' : 'down'} />
        <MetricCard
          label={`Without ${comp.entity_removed}`}
          value={`${cfSign}${cf.pct_change.toFixed(1)}%`}
          sub={`${cfSign}${fmtNum(cf.absolute_change, comp.metric_unit)}`}
          accent="#d97706" />
        <MetricCard
          label={`${comp.entity_removed} Impact`}
          value={fmtNum(Math.abs(comp.entity_impact.delta), comp.metric_unit)}
          sub={`${comp.entity_impact.pct_of_total_change >= 0 ? '+' : ''}${comp.entity_impact.pct_of_total_change.toFixed(1)}% of change`}
          accent="var(--text-secondary)" />
        <MetricCard
          label="Impact Rank"
          value={`#${comp.entity_impact.rank}`}
          sub={`in ${comp.dimension}`}
          accent="var(--text-secondary)" />
      </div>
    </div>
  )
}

function MetricCard({ label, value, sub, accent, trend }: {
  label: string
  value: string
  sub?: string
  accent?: string
  trend?: 'up' | 'down'
}) {
  return (
    <div className="metric-card">
      <p className="text-xs mb-1.5" style={{ color: 'var(--text-dim)' }}>{label}</p>
      <p className="text-xl font-bold mb-1 tabular-nums" style={{ color: accent ?? 'var(--text-primary)' }}>
        {trend === 'up'   && <span className="text-sm mr-1" style={{ color: 'var(--success)' }}>▲</span>}
        {trend === 'down' && <span className="text-sm mr-1" style={{ color: 'var(--error)' }}>▼</span>}
        {value}
      </p>
      {sub && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{sub}</p>}
    </div>
  )
}

// ── Statistical summary (for describe() results) ──────────────────────────────

function StatSummaryTable({ table }: { table: Record<string, unknown>[] }) {
  const keys   = Object.keys(table[0])
  const statCol = keys[0]
  const numCols = keys.slice(1)

  const formatCell = (v: unknown): string => {
    const n = Number(v)
    if (isNaN(n)) return String(v ?? '')
    if (String(table.find(r => true)?.[statCol])?.toLowerCase() === 'count') return Math.round(n).toLocaleString()
    if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
    if (Math.abs(n) >= 1_000)     return `${(n / 1_000).toFixed(2)}K`
    return n.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
        Statistical Summary
      </p>
      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--border)' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Statistic</th>
              {numCols.map(k => <th key={k}>{k}</th>)}
            </tr>
          </thead>
          <tbody>
            {table.map((row, i) => (
              <tr key={i}>
                <td style={{ color: 'var(--purple-400)', fontWeight: 600 }}>{String(row[statCol])}</td>
                {numCols.map(k => (
                  <td key={k} className="tabular-nums">{formatCell(row[k])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Regular result table ──────────────────────────────────────────────────────

function ResultTable({ table }: { table: Record<string, unknown>[] }) {
  const keys = Object.keys(table[0])
  const isNumeric = (v: unknown) => typeof v === 'number' || (typeof v === 'string' && !isNaN(Number(v)) && v !== '')

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
          Result Table
        </p>
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{table.length} rows</span>
      </div>
      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--border)' }}>
        <table className="data-table">
          <thead>
            <tr>{keys.map(k => <th key={k}>{k}</th>)}</tr>
          </thead>
          <tbody>
            {table.slice(0, 100).map((row, i) => (
              <tr key={i}>
                {keys.map(k => {
                  const v = row[k]
                  const n = Number(v)
                  const isNum = isNumeric(v)
                  return (
                    <td key={k} className={isNum ? 'tabular-nums' : ''}>
                      {isNum && !isNaN(n)
                        ? (Math.abs(n) >= 1_000_000 ? `${(n/1_000_000).toFixed(2)}M`
                          : Math.abs(n) >= 1_000 ? `${(n/1_000).toFixed(1)}K`
                          : n.toLocaleString('en-US', { maximumFractionDigits: 2 }))
                        : String(v ?? '')}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.length > 100 && (
        <p className="text-xs mt-1.5" style={{ color: 'var(--text-dim)' }}>
          Showing 100 of {table.length} rows
        </p>
      )}
    </div>
  )
}

// ── Main AnswerPanel ──────────────────────────────────────────────────────────

export function AnswerPanel({ result, eli5 }: Props) {
  const narrative = eli5 ? result.eli5_narrative : result.narrative
  const comp = result.computation_result

  return (
    <div className="space-y-5">
      {/* Narrative */}
      {narrative && (
        <div>
          <p className="section-label mb-2">
            {eli5 ? '📖 Plain English' : '📊 Analyst Summary'}
          </p>
          <div className="answer-narrative">{narrative}</div>
        </div>
      )}

      {/* Key metric cards for reasoning queries */}
      {comp?.type === 'change'         && <ChangeMetrics         comp={comp as ChangeResult} />}
      {comp?.type === 'compare'        && <CompareMetrics        comp={comp as CompareResult} />}
      {comp?.type === 'counterfactual' && <CounterfactualMetrics comp={comp as CounterfactualResult} />}
      {comp?.type === 'breakdown'      && <BreakdownMetrics      comp={comp as any} />}
      {comp?.type === 'summarize'      && <SummarizeMetrics      comp={comp as any} />}

      {/* Scalar result */}
      {result.result_scalar != null && (
        <div className="glass p-6 text-center">
          <p className="text-4xl font-bold gradient-text tabular-nums">
            {result.result_scalar.toLocaleString('en-US', { maximumFractionDigits: 2 })}
          </p>
        </div>
      )}

      {/* Table result */}
      {result.result_table && result.result_table.length > 0 && (
        isStatSummary(result.result_table)
          ? <StatSummaryTable table={result.result_table} />
          : <ResultTable table={result.result_table} />
      )}

      {/* Period note */}
      {result.period_note && (
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          ℹ {result.period_note}
        </p>
      )}
    </div>
  )
}
