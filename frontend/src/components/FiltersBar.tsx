import { useState } from 'react'
import { Filter, X, ChevronDown, ChevronUp } from 'lucide-react'

interface Props {
  profile: Record<string, any>
  filters: Record<string, string>
  dateRange: { start: string; end: string } | null
  datasetDateRange: { start: string; end: string } | null
  onFiltersChange: (f: Record<string, string>) => void
  onDateRangeChange: (d: { start: string; end: string } | null) => void
}

export function FiltersBar({ profile, filters, dateRange, datasetDateRange, onFiltersChange, onDateRangeChange }: Props) {
  const [expanded, setExpanded] = useState(false)
  const dims = Object.entries(profile.dimensions ?? {})
  const hasTime = !!profile.time?.order_date

  const activeCount = Object.keys(filters).length + (dateRange ? 1 : 0)

  const clearAll = () => { onFiltersChange({}); onDateRangeChange(null) }

  return (
    <div className="mb-4">
      <button onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-xl transition-all"
        style={{
          background: activeCount > 0 ? '#f3f0ff' : 'white',
          border: `1px solid ${activeCount > 0 ? '#d4bfe6' : 'var(--border)'}`,
          color: activeCount > 0 ? '#42145F' : 'var(--text-muted)',
          cursor: 'pointer',
        }}>
        <Filter size={13} />
        Filters {activeCount > 0 && <span className="px-1.5 py-0.5 rounded-full text-white text-xs" style={{ background: '#7c3aed', fontSize: 10 }}>{activeCount}</span>}
        {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {expanded && (
        <div className="glass p-4 mt-2 flex flex-wrap items-end gap-3" style={{ borderRadius: 16 }}>
          {dims.map(([key, meta]: [string, any]) => (
            <div key={key} className="flex flex-col gap-1">
              <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>
                {key.replace(/_/g, ' ')}
              </label>
              <select
                value={filters[key] ?? ''}
                onChange={e => {
                  const v = e.target.value
                  const next = { ...filters }
                  if (v) next[key] = v; else delete next[key]
                  onFiltersChange(next)
                }}
                className="text-sm px-3 py-2 rounded-xl"
                style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-primary)', minWidth: 120, outline: 'none' }}>
                <option value="">All</option>
                {(meta.values ?? []).map((v: string) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
          ))}

          {hasTime && datasetDateRange && (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>From</label>
                <input type="date" value={dateRange?.start ?? ''}
                  min={datasetDateRange.start.slice(0, 10)}
                  max={datasetDateRange.end.slice(0, 10)}
                  onChange={e => onDateRangeChange({ start: e.target.value, end: dateRange?.end ?? datasetDateRange.end.slice(0, 10) })}
                  className="text-sm px-3 py-2 rounded-xl"
                  style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-primary)', outline: 'none' }} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-dim)', fontSize: 10 }}>To</label>
                <input type="date" value={dateRange?.end ?? ''}
                  min={datasetDateRange.start.slice(0, 10)}
                  max={datasetDateRange.end.slice(0, 10)}
                  onChange={e => onDateRangeChange({ start: dateRange?.start ?? datasetDateRange.start.slice(0, 10), end: e.target.value })}
                  className="text-sm px-3 py-2 rounded-xl"
                  style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-primary)', outline: 'none' }} />
              </div>
            </>
          )}

          {activeCount > 0 && (
            <button onClick={clearAll}
              className="flex items-center gap-1 text-xs font-bold px-3 py-2 rounded-xl"
              style={{ color: '#ef4444', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer' }}>
              <X size={12} /> Clear all
            </button>
          )}
        </div>
      )}
    </div>
  )
}
