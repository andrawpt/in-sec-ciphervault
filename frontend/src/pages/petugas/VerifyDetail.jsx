import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import KycHistory from '../../components/KycHistory'
import SecureViewer from '../../components/SecureViewer'
import { Alert, KycBadge, LengthHint, LockIcon, PageHeader, Spinner } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'
import { formatBytes, formatDate } from '../../lib/format'

export default function VerifyDetail() {
  const { userId } = useParams()
  const { user } = useAuth()
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [viewing, setViewing] = useState(null)
  const [checks, setChecks] = useState({ name: false, nik: false, clear: false })
  const [note, setNote] = useState('')
  const [flagReason, setFlagReason] = useState('')

  const load = useCallback(() => api.get(`/officer/verifications/${userId}`).then(setD).catch((e) => setError(e.message)), [userId])
  useEffect(() => {
    load()
  }, [load])
  const closeViewer = useCallback(() => setViewing(null), [])

  const act = async (fn) => {
    setError('')
    try {
      await fn()
      setNote('')
      setFlagReason('')
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (!d) return error ? <Alert>{error}</Alert> : <Spinner />
  const st = d.verification.status
  const allChecked = checks.name && checks.nik && checks.clear

  return (
    <>
      <Link to="/petugas/verifikasi" className="text-sm text-brand-700 hover:underline">← ID Verification</Link>
      <PageHeader title={`Reporter ${d.reporter.name}`} subtitle={d.verification.label} action={<KycBadge status={st} />} />
      <Alert>{error}</Alert>
      {viewing && <SecureViewer source={viewing} officerName={user.full_name} onClose={closeViewer} />}

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {d.can_view_ktp ? (
            <section className="card space-y-4 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">Match ID card with registration data</h2>
                <button
                  className="btn-primary btn-sm"
                  onClick={() => setViewing({ path: `/officer/verifications/${userId}/ktp`, title: 'Reporter ID scan', openedAt: Date.now() })}
                >
                  Open ID card
                </button>
              </div>
              <dl className="grid gap-3 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-2">
                <div><dt className="text-slate-500">Registered name</dt><dd className="font-medium">{d.registered.full_name}</dd></div>
                <div><dt className="text-slate-500">Registered ID (NIK)</dt><dd className="font-mono font-medium">{d.registered.nik}</dd></div>
                <div><dt className="text-slate-500">File</dt><dd>{d.ktp.mime} · {formatBytes(d.ktp.size)}</dd></div>
                <div><dt className="text-slate-500">Uploaded</dt><dd>{formatDate(d.ktp.uploaded_at)}</dd></div>
              </dl>
              <p className="text-xs text-slate-500">
                The complete registration data above and the ID card are only displayed during this verification. After a decision is saved, both become inaccessible.
              </p>
              <fieldset className="space-y-2 text-sm">
                {[['clear', 'ID photo is clear, authentic, and not cropped'], ['name', 'Name on ID card matches registered name'], ['nik', 'ID number on card matches registered ID']].map(([k, label]) => (
                  <label key={k} className="flex items-center gap-2">
                    <input type="checkbox" checked={checks[k]} onChange={(e) => setChecks({ ...checks, [k]: e.target.checked })} />
                    {label}
                  </label>
                ))}
              </fieldset>
              <textarea className="input min-h-16" placeholder="Notes (required if rejecting, read by reporter)" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
              <LengthHint value={note} min={5} max={1000} />
              <p className="-mt-2 text-xs text-slate-500">Minimum 5 characters only required when rejecting.</p>
              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-primary"
                  disabled={!allChecked}
                  onClick={() => act(() => api.post(`/officer/verifications/${userId}/decision`, { decision: 'terverifikasi', note: note || null }))}
                >
                  Verify
                </button>
                <button
                  className="btn-danger"
                  disabled={note.trim().length < 5}
                  onClick={() => act(() => api.post(`/officer/verifications/${userId}/decision`, { decision: 'ditolak', note }))}
                >
                  Reject
                </button>
              </div>
            </section>
          ) : (
            <section className="card flex items-start gap-3 p-5 text-sm text-slate-600">
              <LockIcon className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
              <div>
                <p className="font-medium text-slate-800">Access to ID card closed</p>
                <p className="mt-1">
                  {st === 'belum' && 'Reporter has not uploaded an ID card.'}
                  {st === 'terverifikasi' && `Identity already verified on ${formatDate(d.verification.decided_at)}. If there is a suspected issue, request re-verification below.`}
                  {st === 'ditolak' && 'Verification rejected. Access reopens after reporter re-uploads ID card.'}
                  {st === 'verifikasi_ulang' && 'Waiting for reporter to re-upload ID card. Report creation for this reporter is temporarily suspended.'}
                </p>
              </div>
            </section>
          )}

          {st === 'terverifikasi' && (
            <section className="card space-y-3 border-amber-200 p-5">
              <h2 className="font-semibold">Report suspected identity issue</h2>
              <p className="text-sm text-slate-500">
                Reporter must re-upload ID card and cannot submit new reports until verified again. Existing reports continue unaffected.
              </p>
              <textarea
                className="input min-h-20"
                placeholder="Reason (read by reporter), e.g. name on ID differs from name in attached evidence"
                maxLength={1000}
                value={flagReason}
                onChange={(e) => setFlagReason(e.target.value)}
              />
              <LengthHint value={flagReason} min={10} max={1000} />
              <button
                className="btn-secondary"
                disabled={flagReason.trim().length < 10}
                onClick={() => act(() => api.post(`/officer/verifications/${userId}/flag`, { reason: flagReason }))}
              >
                Request re-verification
              </button>
            </section>
          )}
        </div>

        <aside className="space-y-6">
          <section className="card space-y-2 p-5 text-sm">
            <h2 className="font-semibold">Reporter data (masked)</h2>
            {[['Name', 'name'], ['National ID', 'nik'], ['Phone', 'phone'], ['Email', 'email']].map(([l, k]) => (
              <div key={k} className="flex justify-between gap-3">
                <span className="text-slate-500">{l}</span>
                <span className="font-mono text-xs">{d.reporter[k] ?? '–'}</span>
              </div>
            ))}
          </section>
          <section className="card p-5">
            <h2 className="mb-3 font-semibold">Verification history</h2>
            <KycHistory history={d.history} />
          </section>
          <section className="card p-5 text-sm">
            <h2 className="mb-2 font-semibold">ID card viewed by</h2>
            {d.views.length === 0 ? (
              <p className="text-slate-500">Never opened yet.</p>
            ) : (
              <ul className="space-y-1">
                {d.views.map((v, i) => (
                  <li key={i} className="flex justify-between gap-3">
                    <span>{v.officer}</span>
                    <span className="text-slate-500">{formatDate(v.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </>
  )
}
