export interface DatasetInfo {
  session_id: string
  row_count: number
  columns: string[]
  date_range: { start: string; end: string } | null
  numeric_columns: string[]
  categorical_columns: string[]
  sample_used: boolean
  profile?: Record<string, any> | null
  suggested_queries?: string[] | null
}

export interface GraphNodeMetadata {
  nodeType?: 'metric' | 'period' | 'delta' | 'contributor' | 'entity' | 'sub'
  name?: string
  unit?: string
  description?: string
  period?: 'A' | 'B'
  label?: string
  value?: number
  formattedValue?: string
  direction?: string
  pctChange?: number
  absoluteChange?: string
  entity?: string
  dimension?: string
  delta?: string
  pctOfTotalChange?: number
  rank?: number
  sharePct?: number
  isWinner?: boolean
  followUp?: string
  [key: string]: unknown
}

export interface GraphNode {
  id: string
  label: string
  color: { background: string; border?: string; highlight?: { background?: string } }
  font: { color: string; size: number; bold?: boolean }
  shape: string
  size: number
  title?: string
  metadata?: GraphNodeMetadata
}

export interface GraphEdge {
  from: string
  to: string
  label?: string
  color?: { color: string }
  width?: number
  arrows?: string
  dashes?: boolean
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface PeriodInfo {
  start?: string
  end?: string
  label?: string
  value?: number
}

export interface Contributor {
  dimension: string
  entity: string
  value_a: number
  value_b: number
  delta: number
  pct_of_total_change: number
  rank: number
}

export interface SubBreakdownItem {
  dimension: string
  entity: string
  value: number
  share_pct: number
}

export interface ChangeResult {
  type: 'change'
  metric: string
  metric_label: string
  metric_unit: string
  period_a: PeriodInfo & { value: number }
  period_b: PeriodInfo & { value: number }
  absolute_change: number
  pct_change: number
  direction: 'increase' | 'decrease' | 'no_change'
  contributors: Contributor[]
  top_contributors_by_dimension: Record<string, Contributor[]>
  data_quality: { period_a_rows: number; period_b_rows: number; missing_dates: boolean }
}

export interface CompareResult {
  type: 'compare'
  comparison_type: 'entity' | 'time'
  metric: string
  metric_label: string
  metric_unit: string
  entity_a: { label: string; dimension: string; value: number }
  entity_b: { label: string; dimension: string; value: number }
  absolute_diff: number
  pct_diff: number
  winner: string
  loser: string
  winner_value: number
  loser_value: number
  sub_breakdown_winner: SubBreakdownItem[]
  sub_breakdown_loser: SubBreakdownItem[]
  data_quality: { entity_a_rows: number; entity_b_rows: number }
}

export interface CounterfactualResult {
  type: 'counterfactual'
  metric: string
  metric_label: string
  metric_unit: string
  entity_removed: string
  dimension: string
  actual: {
    period_a_value: number
    period_b_value: number
    absolute_change: number
    pct_change: number
    direction: string
  }
  counterfactual: {
    period_b_value: number
    absolute_change: number
    pct_change: number
    direction: string
  }
  entity_impact: {
    delta: number
    pct_of_total_change: number
    rank: number
  }
  period_a: PeriodInfo & { value: number }
  period_b: PeriodInfo & { value: number }
}

export interface BreakdownResult {
  type: 'breakdown'
  metric: string
  metric_label: string
  metric_unit: string
  dimension: string
  dimension_label: string
  total_value: number
  components: { entity: string; dimension: string; value: number; share_pct: number; rank: number }[]
  top_3_share_pct: number
  concentration: string
  component_count: number
}

export interface SummarizeResult {
  type: 'summarize'
  metric_summaries: {
    metric: string; metric_label: string; unit: string
    count: number; sum: number; mean: number; median: number
    std: number; min: number; max: number; q25: number; q75: number
    cv: number; anomaly_count: number; anomaly_pct: number
  }[]
  trend: { direction: string; pct_change: number; periods: number; first_half_avg: number; second_half_avg: number } | null
  top_bottom: { top: { entity: string; dimension: string; value: number; share_pct: number }[]; bottom: { entity: string; dimension: string; value: number; share_pct: number }[]; dimension: string } | null
  row_count: number
}

export type ComputationResult = ChangeResult | CompareResult | CounterfactualResult | BreakdownResult | SummarizeResult | null

export interface QueryResponse {
  success: boolean
  intent: 'change' | 'compare' | 'general' | string
  narrative: string | null
  eli5_narrative: string | null
  computation_result: ComputationResult
  graph_data: GraphData | null
  code: string | null
  result_table: Record<string, unknown>[] | null
  result_scalar: number | null
  error: string | null
  confidence: { label: string; score: number; color: string; explanation: string } | null
  metrics_used: { name: string; column: string; definition: string; unit: string }[] | null
  period_note: string | null
  follow_ups: string[] | null
}

export interface HistoryItem {
  question: string
  intent: string
  narrative: string | null
  timestamp: string
}
