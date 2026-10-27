import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { Alert, PageHeader, Spinner, StatusBadge } from '../../components/ui'
import { formatDate } from '../../lib/format'

export default function Dashboard() {
  const [reports, setReports] = useState(null)
  const [ktp, setKtp] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get('/reports'), api.get('/me/ktp')])
      .then(([r, k]) => {
        setReports(r)
        setKtp(k)
      })
      .catch((e) => setError(e.message))
  }, [])

  return (
    <>
      <PageHeader
        title="My Reports"
        subtitle="Track report statuses and reply to officer inquiries."
        action={
          <Link to="/pelapor/lapor-baru" className="btn-primary">
            + New report
          </Link>
        }
      />
      <Alert>{error}</Alert>
      {ktp && ktp.verification.status !== 'terverifikasi' && (
        <div className="mb-4">
          <Alert kind={ktp.verification.status === 'menunggu' ? 'info' : 'warn'}>
            {{
              belum: 'ID verification is required before you can submit a report.',
              menunggu: 'Your ID card is being verified by officers. Reports can be submitted once verified.',
              ditolak: 'ID verification was rejected. Re-upload your ID card to submit reports.',
              verifikasi_ulang: 'Officers requested ID re-verification. Report submission is temporarily disabled.',
            }[ktp.verification.status]}{' '}
            <Link to="/pelapor/verifikasi" className="font-medium underline">
              Open ID verification
            </Link>
          </Alert>
        </div>
      )}
      {!reports ? (
        <Spinner />
      ) : reports.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="font-medium text-slate-700">No reports yet.</p>
          <p className="mt-1 text-sm text-slate-500">Experienced or witnessed incidents on campus? Report here securely.</p>
          <Link to="/pelapor/lapor-baru" className="btn-primary mt-4">
            Submit first report
          </Link>
        </div>
      ) : (
        <div className="grid gap-3">
          {reports.map((r) => (
            <Link key={r.id} to={`/pelapor/laporan/${r.id}`} className="card flex flex-wrap items-center gap-4 p-4 hover:border-brand-600">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-slate-900">{r.title}</div>
                <div className="mt-0.5 text-xs text-slate-500">
                  {r.category_label} · submitted {formatDate(r.created_at)} · {r.attachment_count} attachments
                </div>
              </div>
              <StatusBadge status={r.status} />
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
