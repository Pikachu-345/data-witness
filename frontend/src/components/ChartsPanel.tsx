import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, ComposedChart, ReferenceLine, LabelList,
} from 'recharts'
import type { QueryResponse, ChangeResult, CompareResult, Contributor } from '../types'

interface Props { result: QueryResponse }

const PURPLE = '#7c3aed'
const GREEN  = '#22c55e'
const RED    = '#ef4444'
const MUTED  = 'rgba(66,20,95,0.08)'

const axisStyle = { fill: '#7c6b96', fontSize: 11, fontFamily: 'Inter' }
const tooltipStyle = {
  contentStyle: { background: 'white', border: '1px solid #e2d9f3', borderRadius: 12, color: '#1e1033', fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' },
  labelStyle: { color: '#42145F', fontWeight: 700 },
  cursor: { fill: 'rgba(124,58,237,0.04)' },
}

function fmtVal(v: number) {
  if (Math.abs(v) >= 1_000_000) return `${(v/1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000) return `${(v/1_000).toFixed(1)}K`
  return v.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

// ── Waterfall ─────────────────────────────────────────────────────────────────
function buildWaterfall(comp: ChangeResult) {
  const items: { name: string; base: number; val: number; type: string }[] = []
  items.push({ name: comp.period_a.label ?? 'Before', base: 0, val: comp.period_a.value, type: 'total' })

  let running = comp.period_a.value
  for (const c of comp.contributors.slice(0, 5)) {
    const d = c.delta
    items.push({
      name: `${c.entity} (${c.dimension})`,
      base: d >= 0 ? running : running + d,
      val: Math.abs(d),
      type: d >= 0 ? 'pos' : 'neg',
    })
    running += d
  }
  items.push({ name: comp.period_b.label ?? 'After', base: 0, val: comp.period_b.value, type: 'total' })
  return items
}

function WaterfallChart({ comp }: { comp: ChangeResult }) {
  const data = buildWaterfall(comp)
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--text-muted)' }}>
        {comp.metric_label} Waterfall — {comp.period_a.label} → {comp.period_b.label}
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 20, right: 20, bottom: 70, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={MUTED} vertical={false} />
          <XAxis dataKey="name" tick={axisStyle} angle={-30} textAnchor="end" interval={0} />
          <YAxis tick={axisStyle} tickFormatter={fmtVal} />
          <Tooltip {...tooltipStyle} formatter={(v: any, _: any, p: any) => [fmtVal(p.payload.val), p.payload.name]} />
          <Bar dataKey="base" stackId="s" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="val" stackId="s" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.type === 'total' ? PURPLE : d.type === 'pos' ? GREEN : RED} />
            ))}
            <LabelList dataKey="val" position="top" formatter={fmtVal}
                       style={{ fill: '#42145F', fontSize: 10, fontFamily: 'Inter' }} />
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Contributor bar ────────────────────────────────────────────────────────────
function ContributorChart({ contribs }: { contribs: Contributor[] }) {
  const top = [...contribs].sort((a, b) => Math.abs(b.pct_of_total_change) - Math.abs(a.pct_of_total_change)).slice(0, 8)
  const data = top.map(c => ({
    name: `${c.entity} (${c.dimension})`,
    pct: c.pct_of_total_change,
    isPos: c.delta >= 0,
  }))
  const max = Math.max(...data.map(d => Math.abs(d.pct)))

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--text-muted)' }}>
        Top Drivers — % of Total Change
      </p>
      <ResponsiveContainer width="100%" height={Math.max(280, data.length * 38)}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 60, bottom: 5, left: 160 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={MUTED} horizontal={false} />
          <XAxis type="number" domain={[-max * 1.3, max * 1.3]} tick={axisStyle} tickFormatter={v => `${v.toFixed(0)}%`} />
          <YAxis type="category" dataKey="name" tick={{ ...axisStyle, fontSize: 10 }} width={155} />
          <ReferenceLine x={0} stroke="rgba(66,20,95,0.1)" />
          <Tooltip {...tooltipStyle} formatter={(v: any) => [`${(v as number).toFixed(1)}%`, '% of change']} />
          <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.isPos ? GREEN : RED} />)}
            <LabelList dataKey="pct" position="right" formatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                       style={{ fill: '#42145F', fontSize: 10 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Comparison bar ────────────────────────────────────────────────────────────
function ComparisonChart({ comp }: { comp: CompareResult }) {
  const data = [
    { name: comp.entity_a.label, value: comp.entity_a.value, isWinner: comp.entity_a.label === comp.winner },
    { name: comp.entity_b.label, value: comp.entity_b.value, isWinner: comp.entity_b.label === comp.winner },
  ]
  const max = Math.max(comp.entity_a.value, comp.entity_b.value)

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--text-muted)' }}>
        {comp.metric_label} Comparison
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={MUTED} vertical={false} />
          <XAxis dataKey="name" tick={axisStyle} />
          <YAxis tick={axisStyle} tickFormatter={fmtVal} domain={[0, max * 1.2]} />
          <Tooltip {...tooltipStyle} formatter={(v: any) => [fmtVal(v as number), comp.metric_label]} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.isWinner ? GREEN : RED} />)}
            <LabelList dataKey="value" position="top" formatter={fmtVal}
                       style={{ fill: '#42145F', fontSize: 11 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Sub-breakdown table */}
      {comp.sub_breakdown_winner.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
            {comp.winner} — sub-breakdown (explains why they lead)
          </p>
          <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--border)' }}>
            <table className="data-table">
              <thead>
                <tr><th>Entity</th><th>Dimension</th><th>Value</th><th>Share %</th></tr>
              </thead>
              <tbody>
                {comp.sub_breakdown_winner.map((s, i) => (
                  <tr key={i}>
                    <td>{s.entity}</td><td>{s.dimension}</td>
                    <td>{fmtVal(s.value)}</td>
                    <td>{s.share_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Dimension breakdown tables for change queries ─────────────────────────────
function DimensionBreakdowns({ comp }: { comp: ChangeResult }) {
  const dims = Object.entries(comp.top_contributors_by_dimension || {})
  if (!dims.length) return null
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--text-muted)' }}>
        Breakdown by Dimension
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {dims.filter(([, cs]) => cs.length > 0).map(([dim, cs]) => (
          <div key={dim}>
            <p className="text-xs font-medium mb-1 capitalize" style={{ color: 'var(--text-secondary)' }}>
              {dim.replace('_', ' ')}
            </p>
            <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--border)' }}>
              <table className="data-table">
                <thead><tr><th>Entity</th><th>Before</th><th>After</th><th>Δ</th><th>% of change</th></tr></thead>
                <tbody>
                  {cs.slice(0, 5).map((c, i) => (
                    <tr key={i}>
                      <td>{c.entity}</td>
                      <td>{fmtVal(c.value_a)}</td>
                      <td>{fmtVal(c.value_b)}</td>
                      <td style={{ color: c.delta >= 0 ? GREEN : RED }}>
                        {c.delta >= 0 ? '+' : ''}{fmtVal(c.delta)}
                      </td>
                      <td style={{ color: c.pct_of_total_change >= 0 ? GREEN : RED }}>
                        {c.pct_of_total_change >= 0 ? '+' : ''}{c.pct_of_total_change.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main ChartsPanel ──────────────────────────────────────────────────────────
export function ChartsPanel({ result }: Props) {
  const comp = result.computation_result

  if (!comp) {
    return (
      <div className="text-sm text-center py-12" style={{ color: 'var(--text-muted)' }}>
        Charts are available for Change Analysis and Comparison queries.
      </div>
    )
  }

  if (comp.type === 'change') {
    const c = comp as ChangeResult
    return (
      <div className="space-y-8">
        <WaterfallChart comp={c} />
        {c.contributors.length > 0 && <ContributorChart contribs={c.contributors} />}
        <DimensionBreakdowns comp={c} />
      </div>
    )
  }

  if (comp.type === 'compare') {
    return <ComparisonChart comp={comp as CompareResult} />
  }

  return null
}
