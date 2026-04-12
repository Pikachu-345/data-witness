import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, ZoomIn, ZoomOut, Maximize2, Crosshair, Network } from 'lucide-react'
import type { GraphData, GraphNode, GraphNodeMetadata } from '../types'

interface Props {
  graphData: GraphData | null
  onFollowUp?: (q: string) => void
}

// ── Node Detail Panel ─────────────────────────────────────────────────────────

const NODE_TYPE_META: Record<string, { label: string; color: string }> = {
  metric:      { label: 'Metric',        color: '#8b5cf6' },
  period:      { label: 'Period',        color: '#a78bfa' },
  delta:       { label: 'Change',        color: '#34d399' },
  contributor: { label: 'Driver',        color: '#c4b5fd' },
  entity:      { label: 'Entity',        color: '#22d3ee' },
  sub:         { label: 'Sub-Component', color: '#a78bfa' },
}

function buildDetails(m: GraphNodeMetadata): [string, string][] {
  const rows: [string, string][] = []
  const nt = m.nodeType ?? ''

  if (nt === 'metric') {
    if (m.unit) rows.push(['Unit', m.unit])
    rows.push(['Role', 'Central metric being analyzed'])
  } else if (nt === 'period') {
    if (m.formattedValue) rows.push(['Value', m.formattedValue])
    if (m.period)         rows.push(['Role', m.period === 'A' ? 'Baseline (Before)' : 'Target (After)'])
    if (m.label)          rows.push(['Period', m.label])
  } else if (nt === 'delta') {
    if (m.direction)      rows.push(['Direction', m.direction.charAt(0).toUpperCase() + m.direction.slice(1)])
    if (m.pctChange != null) rows.push(['% Change', `${m.pctChange >= 0 ? '+' : ''}${m.pctChange.toFixed(1)}%`])
    if (m.absoluteChange) rows.push(['Absolute',   m.absoluteChange])
  } else if (nt === 'contributor') {
    if (m.entity)               rows.push(['Entity',    m.entity])
    if (m.dimension)            rows.push(['Dimension', m.dimension.replace(/_/g, ' ')])
    if (m.delta)                rows.push(['Δ Value',   m.delta])
    if (m.pctOfTotalChange != null)
      rows.push(['Impact', `${m.pctOfTotalChange >= 0 ? '+' : ''}${m.pctOfTotalChange.toFixed(1)}% of change`])
    if (m.rank != null)         rows.push(['Rank',  `#${m.rank} driver`])
  } else if (nt === 'entity') {
    if (m.formattedValue)       rows.push(['Value', m.formattedValue])
    if (m.isWinner != null)     rows.push(['Status', m.isWinner ? '🏆 Winner' : 'Runner-up'])
  } else if (nt === 'sub') {
    if (m.entity)               rows.push(['Entity',    m.entity])
    if (m.dimension)            rows.push(['Dimension', m.dimension.replace(/_/g, ' ')])
    if (m.sharePct != null)     rows.push(['Share', `${m.sharePct.toFixed(1)}%`])
  }

  return rows
}

function NodeDetailPanel({ node, onClose, onFollowUp }: {
  node: GraphNode
  onClose: () => void
  onFollowUp?: (q: string) => void
}) {
  const m = node.metadata ?? {}
  const nt = m.nodeType ?? 'node'
  const typeMeta = NODE_TYPE_META[nt] ?? { label: 'Node', color: '#a78bfa' }
  const details = buildDetails(m)
  const firstLine = node.label.split('\n')[0]

  return (
    <motion.div
      initial={{ opacity: 0, x: 14, scale: 0.96 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 14, scale: 0.96 }}
      transition={{ duration: 0.18 }}
      className="node-detail-panel absolute top-3 right-3 z-20 p-4"
      style={{ width: 210 }}>

      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex-1 min-w-0">
          <span className="badge"
            style={{
              background: `${typeMeta.color}20`,
              border: `1px solid ${typeMeta.color}45`,
              color: typeMeta.color,
              fontSize: 9, padding: '2px 7px',
            }}>
            {typeMeta.label}
          </span>
          <p className="text-sm font-semibold mt-1.5 leading-tight" style={{ color: 'var(--text-primary)' }}>
            {firstLine}
          </p>
        </div>
        <button onClick={onClose}
          style={{ color: 'var(--text-dim)', background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0, padding: 2, lineHeight: 1 }}>
          <X size={13} />
        </button>
      </div>

      {/* Details */}
      {details.length > 0 && (
        <div className="space-y-1.5 mb-3 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
          {details.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3">
              <span className="text-xs flex-shrink-0" style={{ color: 'var(--text-dim)' }}>{k}</span>
              <span className="text-xs font-medium text-right tabular-nums" style={{ color: 'var(--text-secondary)' }}>{v}</span>
            </div>
          ))}
        </div>
      )}

      {/* Tooltip / title fallback */}
      {!details.length && node.title && (
        <p className="text-xs mb-3 pb-3" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
          {node.title}
        </p>
      )}

      {/* Follow-up */}
      {m.followUp && onFollowUp && (
        <button
          onClick={() => { onFollowUp(m.followUp as string); onClose() }}
          className="w-full text-left text-xs py-2 px-3 rounded-lg transition-all"
          style={{
            background: 'rgba(66,20,95,0.06)',
            border: '1px solid rgba(66,20,95,0.2)',
            color: '#42145F',
            cursor: 'pointer',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(109,40,217,0.22)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(109,40,217,0.12)')}>
          💬 {m.followUp as string}
        </button>
      )}
    </motion.div>
  )
}

// ── Legend ────────────────────────────────────────────────────────────────────

const LEGEND_ITEMS = [
  { color: '#42145F', label: 'Metric' },
  { color: '#5a2d7a', label: 'Period / Entity' },
  { color: '#34d399', label: 'Increase / Winner' },
  { color: '#fb7185', label: 'Decrease / Loser' },
  { color: '#1e1738', label: 'Driver / Sub-component', border: '#42145F' },
]

// ── Main Component ────────────────────────────────────────────────────────────

export function GraphPanel({ graphData, onFollowUp }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef   = useRef<any>(null)
  const nodesDataRef = useRef<any>(null)

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    if (!containerRef.current || !graphData?.nodes?.length) return

    import('vis-network/standalone').then(({ Network, DataSet }) => {
      if (!containerRef.current) return

      // Destroy previous
      networkRef.current?.destroy()
      networkRef.current = null

      const nodesData = new DataSet(
        graphData.nodes.map(n => ({
          ...n,
          shadow: { enabled: true, color: `${n.color.background}80`, size: 20, x: 0, y: 4 },
          borderWidth: 3,
          borderWidthSelected: 4,
        })) as any
      )
      nodesDataRef.current = nodesData
      const edgesData = new DataSet(graphData.edges as any)

      const net = new Network(
        containerRef.current,
        { nodes: nodesData as any, edges: edgesData as any },
        {
          physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
              gravitationalConstant: -100,
              centralGravity: 0.008,
              springLength: 180,
              springConstant: 0.06,
              avoidOverlap: 1.3,
            },
            stabilization: { iterations: 250, fit: true },
          },
          interaction: {
            hover: true,
            tooltipDelay: 100,
            navigationButtons: false,
            keyboard: false,
            dragNodes: true,
            zoomView: true,
          },
          nodes: {
            font: { face: 'Inter', multi: false },
            borderWidth: 2,
          },
          edges: {
            font: { face: 'Inter', size: 11, align: 'middle', color: 'rgba(200,180,230,0.85)' },
            smooth: { enabled: true, type: 'curvedCW', roundness: 0.22 },
            color: { inherit: false },
          },
        }
      )

      // Click → select node
      net.on('click', (params: any) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0]
          const raw = nodesDataRef.current?.get(nodeId)
          if (raw) setSelectedNode(raw as GraphNode)
        } else {
          setSelectedNode(null)
        }
      })

      // Disable physics after stabilisation for cleaner UX
      net.on('stabilized', () => {
        net.setOptions({ physics: { enabled: false } })
      })

      networkRef.current = net
    }).catch(() => {/* vis-network unavailable */})

    return () => {
      networkRef.current?.destroy()
      networkRef.current = null
      nodesDataRef.current = null
    }
  }, [graphData])

  // Zoom controls
  const zoomIn  = () => networkRef.current?.moveTo({ scale: (networkRef.current.getScale() || 1) * 1.32 })
  const zoomOut = () => networkRef.current?.moveTo({ scale: (networkRef.current.getScale() || 1) * 0.76 })
  const fitAll  = () => networkRef.current?.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } })

  // Empty state
  if (!graphData?.nodes?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
          style={{ background: 'rgba(109,40,217,0.08)', border: '1px dashed var(--border)' }}>
          <Network size={28} style={{ color: 'var(--text-dim)' }} />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
            Reasoning graph not available
          </p>
          <p className="text-xs max-w-xs" style={{ color: 'var(--text-dim)' }}>
            Ask a change or comparison question to see the AI reasoning chain visualised as an interactive knowledge graph.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 justify-center mt-1">
          {['How did the main metric change over time?', 'Compare two entities on a metric'].map(q => (
            <button key={q}
              onClick={() => onFollowUp?.(q)}
              className="text-xs px-3 py-1.5 rounded-full"
              style={{ background: 'rgba(66,20,95,0.05)', border: '1px solid var(--border)', color: 'var(--text-muted)', cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(66,20,95,0.2)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}>
              {q}
            </button>
          ))}
        </div>
      </div>
    )
  }

  const canvasHeight = isFullscreen ? 'calc(100vh - 200px)' : 520

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <p className="section-label">Reasoning Knowledge Graph</p>
          <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
            {graphData.nodes.length} nodes · {graphData.edges.length} edges
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button className="graph-ctrl-btn" onClick={zoomIn} title="Zoom in"><ZoomIn size={13} /></button>
          <button className="graph-ctrl-btn" onClick={zoomOut} title="Zoom out"><ZoomOut size={13} /></button>
          <button className="graph-ctrl-btn" onClick={fitAll} title="Fit all"><Crosshair size={13} /></button>
          <button className="graph-ctrl-btn" onClick={() => setIsFullscreen(v => !v)} title="Toggle fullscreen">
            <Maximize2 size={13} />
          </button>
        </div>
      </div>

      <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>
        Click any node to see details and ask follow-up questions
      </p>

      {/* Graph canvas + node detail overlay */}
      <div className="relative">
        <div
          ref={containerRef}
          style={{
            height: canvasHeight,
            width: '100%',
            background: 'linear-gradient(180deg, #1a1035, #0f0a20)',
            borderRadius: 16,
            border: '1px solid rgba(124,58,237,0.2)',
            boxShadow: '0 4px 24px rgba(0,0,0,0.2), inset 0 1px 0 rgba(124,58,237,0.1)',
          }}
        />

        {/* Node detail panel */}
        <AnimatePresence>
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
              onFollowUp={onFollowUp}
            />
          )}
        </AnimatePresence>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
        {LEGEND_ITEMS.map(({ color, label, border }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ background: color, border: border ? `1px solid ${border}` : undefined }} />
            <span className="text-xs" style={{ color: 'var(--text-dim)', fontSize: 10 }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
