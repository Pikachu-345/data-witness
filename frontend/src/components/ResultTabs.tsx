import { useState, useEffect } from 'react'
import { Sparkles, Network, BarChart2, Shield } from 'lucide-react'
import type { QueryResponse } from '../types'
import { AnswerPanel }  from './AnswerPanel'
import { GraphPanel }   from './GraphPanel'
import { ChartsPanel }  from './ChartsPanel'
import { AuditPanel }   from './AuditPanel'

interface Props {
  result: QueryResponse
  eli5: boolean
  onFollowUp?: (q: string) => void
}

const TABS = [
  { id: 'answer', label: 'Answer',        icon: Sparkles  },
  { id: 'graph',  label: 'Insight Graph', icon: Network   },
  { id: 'charts', label: 'Charts',        icon: BarChart2 },
  { id: 'audit',  label: 'Audit Trail',   icon: Shield    },
]

export function ResultTabs({ result, eli5, onFollowUp }: Props) {
  const isReasoning = ['change', 'compare', 'counterfactual', 'breakdown', 'summarize'].includes(result.intent)
  const [active, setActive] = useState('answer')

  // Auto-switch to graph for reasoning queries, answer for others
  useEffect(() => {
    setActive(isReasoning ? 'graph' : 'answer')
  }, [result.intent, isReasoning])

  const intentLabel =
    result.intent === 'change'         ? 'Change Analysis' :
    result.intent === 'compare'        ? 'Comparison' :
    result.intent === 'counterfactual' ? 'What-If Analysis' :
    result.intent === 'breakdown'      ? 'Breakdown' :
    result.intent === 'summarize'      ? 'Summary' :
    'General Query'

  const intentBadge =
    result.intent === 'change'         ? 'badge-change' :
    result.intent === 'compare'        ? 'badge-compare' :
    result.intent === 'counterfactual' ? 'badge-counterfactual' :
    result.intent === 'breakdown'      ? 'badge-breakdown' :
    result.intent === 'summarize'      ? 'badge-summarize' :
    'badge-general'

  const visibleTabs = TABS.filter(t => {
    if (t.id === 'graph') return true          // always show; GraphPanel handles empty state
    if (t.id === 'charts') return isReasoning  // charts only for reasoning
    return true
  })

  return (
    <div>
      {/* Intent badge + tab bar */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {result.success && (
            <span className={`badge ${intentBadge}`}>
              ⚡ {intentLabel}
            </span>
          )}
          {!result.success && (
            <span className="badge badge-general">Failed</span>
          )}
        </div>

        <div className="flex gap-1 flex-wrap">
          {visibleTabs.map(t => (
            <button key={t.id}
              className={`tab ${active === t.id ? 'active' : ''}`}
              onClick={() => setActive(t.id)}>
              <t.icon size={13} />
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Panel */}
      <div className="glass p-5" style={{ minHeight: 280 }}>
        {!result.success ? (
          <div className="text-sm" style={{ color: 'var(--error)' }}>
            <p className="font-semibold mb-2">Could not process this question.</p>
            <details>
              <summary className="cursor-pointer text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                Show error details
              </summary>
              <pre className="code-panel mt-2 text-xs">{result.error}</pre>
            </details>
          </div>
        ) : (
          <>
            {active === 'answer' && <AnswerPanel result={result} eli5={eli5} />}
            {active === 'graph'  && <GraphPanel  graphData={result.graph_data} onFollowUp={onFollowUp} />}
            {active === 'charts' && <ChartsPanel result={result} />}
            {active === 'audit'  && <AuditPanel  result={result} />}
          </>
        )}
      </div>

      {/* Follow-up suggestions */}
      {result.success && result.follow_ups && result.follow_ups.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--text-dim)' }}>
            What to explore next
          </p>
          <div className="flex flex-wrap gap-2">
            {result.follow_ups.map((q: string, i: number) => (
              <button key={i} onClick={() => onFollowUp?.(q)}
                className="text-sm px-4 py-2.5 rounded-xl font-medium transition-all"
                style={{ background: '#f3f0ff', color: '#42145F', border: '1px solid #e2d9f3', cursor: 'pointer' }}
                onMouseEnter={e => { e.currentTarget.style.background = '#e8e0f8'; e.currentTarget.style.borderColor = '#c4b5fd' }}
                onMouseLeave={e => { e.currentTarget.style.background = '#f3f0ff'; e.currentTarget.style.borderColor = '#e2d9f3' }}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
