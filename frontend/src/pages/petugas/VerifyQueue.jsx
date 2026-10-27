import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { Alert, KycBadge, PageHeader, Spinner } from '../../components/ui'
import { KYC } from '../../lib/constants'
import { formatDate } from '../../lib/format'

const TABS = ['menunggu', 'verifikasi_ulang', 'ditolak', 'terverifikasi', '']

export default function VerifyQueue() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('menunggu')
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setRows(null)
    api.get(`/officer/verifications${tab ? `?status=${tab}` : ''}`).then(setRows).catch((e) => setError(e.message))
  }, [tab])

  return (
    <>
      <PageHeader title="ID Verification" subtitle="ID cards can only be opened during pending verification status. Once decided, access is closed." />
      <div className="mb-4 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t || 'all'}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === t ? 'bg-brand-50 font-medium text-brand-800' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            {t ? KYC[t].label : 'All'}
          </button>
        ))}
      </div>
      <Alert>{error}</Alert>
      {!rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <div className="card p-10 text-center text-sm text-slate-500">No reporters in this list.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Reporter</th>
                <th className="px-4 py-3 font-medium">ID submitted</th>
                <th className="px-4 py-3 font-medium">Reports</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.user_id} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => navigate(`/petugas/verifikasi/${r.user_id}`)}>
                  <td className="px-4 py-3 font-mono text-xs">
                    {r.name}
                    {r.is_resubmission && r.status === 'menunggu' && (
                      <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 font-sans text-[11px] text-amber-800">resubmission</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{formatDate(r.submitted_at)}</td>
                  <td className="px-4 py-3">{r.report_count}</td>
                  <td className="px-4 py-3"><KycBadge status={r.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
