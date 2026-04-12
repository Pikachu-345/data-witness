import { useState, useEffect } from 'react'
import { Search, ChevronLeft, ChevronRight, ArrowUp, ArrowDown } from 'lucide-react'
import { getDataPreview } from '../api/client'

interface Props { sessionId: string; columns: string[] }

export function DataPreview({ sessionId, columns }: Props) {
  const [rows, setRows] = useState<Record<string, any>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [loading, setLoading] = useState(false)

  const pageSize = 50
  const totalPages = Math.ceil(total / pageSize)

  useEffect(() => {
    setLoading(true)
    getDataPreview(sessionId, page, pageSize, sortCol, sortDir, search)
      .then(res => { setRows(res.rows); setTotal(res.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [sessionId, page, sortCol, sortDir, search])

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
    setPage(0)
  }

  return (
    <div>
      {/* Search bar */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 flex items-center gap-2 px-4 py-2.5 rounded-xl"
          style={{ background: 'white', border: '1px solid var(--border)' }}>
          <Search size={15} style={{ color: 'var(--text-dim)' }} />
          <input type="text" placeholder="Search across all columns..."
            value={search} onChange={e => { setSearch(e.target.value); setPage(0) }}
            className="flex-1 text-sm outline-none"
            style={{ background: 'transparent', color: 'var(--text-primary)', border: 'none' }} />
        </div>
        <span className="text-xs font-semibold tabular-nums" style={{ color: 'var(--text-dim)' }}>
          {total.toLocaleString()} rows
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto" style={{ borderRadius: 16, border: '1px solid var(--border)' }}>
        <table className="data-table" style={{ opacity: loading ? 0.5 : 1, transition: 'opacity 0.2s' }}>
          <thead>
            <tr>
              <th style={{ width: 50 }}>#</th>
              {columns.map(col => (
                <th key={col} onClick={() => toggleSort(col)}
                  style={{ cursor: 'pointer', userSelect: 'none' }}>
                  <span className="flex items-center gap-1">
                    {col}
                    {sortCol === col && (sortDir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td className="tabular-nums" style={{ color: 'var(--text-dim)' }}>{page * pageSize + i + 1}</td>
                {columns.map(col => (
                  <td key={col} className={typeof row[col] === 'number' ? 'tabular-nums' : ''}>
                    {row[col] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={columns.length + 1} className="text-center py-8" style={{ color: 'var(--text-dim)' }}>
                {loading ? 'Loading...' : 'No data found'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
            className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
            style={{ background: page === 0 ? '#f3f0ff' : 'white', border: '1px solid var(--border)', color: page === 0 ? 'var(--text-dim)' : '#42145F', cursor: page === 0 ? 'default' : 'pointer', opacity: page === 0 ? 0.5 : 1 }}>
            <ChevronLeft size={13} /> Previous
          </button>
          <span className="text-xs font-semibold tabular-nums" style={{ color: 'var(--text-muted)' }}>
            Page {page + 1} of {totalPages}
          </span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
            className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
            style={{ background: page >= totalPages - 1 ? '#f3f0ff' : 'white', border: '1px solid var(--border)', color: page >= totalPages - 1 ? 'var(--text-dim)' : '#42145F', cursor: page >= totalPages - 1 ? 'default' : 'pointer', opacity: page >= totalPages - 1 ? 0.5 : 1 }}>
            Next <ChevronRight size={13} />
          </button>
        </div>
      )}
    </div>
  )
}
