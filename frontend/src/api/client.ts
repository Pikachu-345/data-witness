import axios from 'axios'
import type { DatasetInfo, QueryResponse } from '../types'

const api = axios.create({ baseURL: '/api', timeout: 90000 })

export async function uploadDataset(file: File): Promise<DatasetInfo> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<DatasetInfo>('/upload', form)
  return data
}

export async function useSampleDataset(): Promise<DatasetInfo> {
  const { data } = await api.get<DatasetInfo>('/sample')
  return data
}

export async function runQuery(
  question: string, sessionId: string, eli5Mode: boolean,
  filters?: Record<string, string>, dateRange?: { start: string; end: string } | null,
): Promise<QueryResponse> {
  const { data } = await api.post<QueryResponse>('/query', {
    question, session_id: sessionId, eli5_mode: eli5Mode,
    filters: filters && Object.keys(filters).length > 0 ? filters : undefined,
    date_range: dateRange ?? undefined,
  })
  return data
}

export async function getSmartInsights(sessionId: string): Promise<any> {
  const { data } = await api.post(`/insights/${sessionId}`)
  return data
}

export async function quickAction(sessionId: string, params: { action: string; metric?: string; dimension?: string }): Promise<any> {
  const { data } = await api.post(`/quick-action/${sessionId}`, params)
  return data
}

export async function getDataPreview(
  sessionId: string, page = 0, pageSize = 50,
  sortCol?: string, sortDir?: string, search?: string,
): Promise<any> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (sortCol) params.set('sort_col', sortCol)
  if (sortDir) params.set('sort_dir', sortDir)
  if (search) params.set('search', search)
  const { data } = await api.get(`/data/${sessionId}?${params}`)
  return data
}

export async function buildChart(sessionId: string, params: {
  x_column: string; y_metric: string; chart_type: string; aggregation: string; top_n?: number
}): Promise<any> {
  const { data } = await api.post(`/chart-builder/${sessionId}`, params)
  return data
}
