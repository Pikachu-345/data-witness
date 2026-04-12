import type { QueryResponse } from '../types'

interface Props { result: QueryResponse }

export function AuditPanel({ result }: Props) {
  const comp = result.computation_result
  const isReasoning = result.intent === 'change' || result.intent === 'compare'

  return (
    <div className="space-y-5">
      {/* Confidence / method badge */}
      <div className="flex items-center gap-3">
        {isReasoning ? (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                  style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', color: '#6ee7b7' }}>
              ⬤ High Confidence — Deterministic Computation
            </span>
          </div>
        ) : result.confidence ? (
          <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold`}
                style={{
                  background: result.confidence.color === 'green' ? 'rgba(16,185,129,0.15)'
                    : result.confidence.color === 'orange' ? 'rgba(245,158,11,0.15)' : 'rgba(244,63,94,0.15)',
                  border: `1px solid ${result.confidence.color === 'green' ? 'rgba(16,185,129,0.3)'
                    : result.confidence.color === 'orange' ? 'rgba(245,158,11,0.3)' : 'rgba(244,63,94,0.3)'}`,
                  color: result.confidence.color === 'green' ? '#6ee7b7'
                    : result.confidence.color === 'orange' ? '#fcd34d' : '#fca5a5',
                }}>
            ⬤ {result.confidence.label} — {result.confidence.score}/100
          </span>
        ) : null}
        {isReasoning && (
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            All numbers computed directly by pandas — LLM only interprets pre-computed results
          </p>
        )}
      </div>

      {/* Exact code for general queries */}
      {result.code && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
            Exact Query Executed
          </p>
          <pre className="code-panel">{result.code}</pre>
        </div>
      )}

      {/* Computation summary for reasoning queries */}
      {comp && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
            Computation Detail (raw JSON)
          </p>
          <div className="code-panel" style={{ maxHeight: 400, overflowY: 'auto' }}>
            {JSON.stringify(comp, null, 2)}
          </div>
        </div>
      )}

      {/* Metric definitions for general queries */}
      {result.metrics_used && result.metrics_used.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
            Metric Definitions Used
          </p>
          <div className="space-y-2">
            {result.metrics_used.map((m, i) => (
              <div key={i} className="glass p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold" style={{ color: 'var(--purple-primary)' }}>{m.name}</span>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({m.column})</span>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(109,40,217,0.2)', color: 'var(--text-muted)' }}>{m.unit}</span>
                </div>
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{m.definition}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data quality */}
      {comp?.type === 'change' && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
            Data Quality
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="glass p-3 text-sm">
              <span style={{ color: 'var(--text-muted)' }}>Period A rows: </span>
              <span style={{ color: 'var(--text-secondary)' }}>{(comp as any).data_quality?.period_a_rows?.toLocaleString()}</span>
            </div>
            <div className="glass p-3 text-sm">
              <span style={{ color: 'var(--text-muted)' }}>Period B rows: </span>
              <span style={{ color: 'var(--text-secondary)' }}>{(comp as any).data_quality?.period_b_rows?.toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
