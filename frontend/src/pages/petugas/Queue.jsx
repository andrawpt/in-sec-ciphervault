import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { Alert, PageHeader, Spinner, StatusBadge } from '../../components/ui'
import { CATEGORIES, STATUS } from '../../lib/constants'
import { formatDate } from '../../lib/format'

export default function Queue() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ status: '', category: '' })
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString()
    setRows(null)
    api.get(`/officer/reports${q ? `?${q}` : ''}`).then(setRows).catch((e) => setError(e.message))
  }, [filters])

  return (
    <>
      <PageHeader title="Case Queue" subtitle="Newest reports on top. Reporter identity is displayed masked." />
      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input w-auto" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="">All statuses</option>
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className="input w-auto" value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
      <Alert>{error}</Alert>
      {!rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <div className="card p-10 text-center text-sm text-slate-500">No cases found for this filter.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Received</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Reporter</th>
                <th className="px-4 py-3 font-medium">Evidence</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => navigate(`/petugas/kasus/${r.id}`)}>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-500">{formatDate(r.created_at)}</td>
                  <td className="max-w-xs truncate px-4 py-3 font-medium text-slate-900">{r.title}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{r.category_label}</td>
                  <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{r.reporter_name}</td>
                  <td className="px-4 py-3">{r.attachment_count}</td>
                  <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
