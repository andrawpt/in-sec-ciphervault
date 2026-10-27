import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import EventTimeline from '../../components/EventTimeline'
import SecureViewer from '../../components/SecureViewer'
import { AccessBadge } from '../../components/access'
import { useAuth } from '../../context/AuthContext'
import { Alert, KycBadge, LengthHint, LockIcon, PageHeader, Spinner, StatusBadge } from '../../components/ui'
import { STATUS } from '../../lib/constants'
import { formatBytes, formatDate } from '../../lib/format'

export default function CaseDetail() {
  const { id } = useParams()
  const [c, setCase] = useState(null)
  const [error, setError] = useState('')
  const [nextStatus, setNextStatus] = useState('')
  const [statusNote, setStatusNote] = useState('')
  const [note, setNote] = useState('')
  const [copied, setCopied] = useState('')
  const { user } = useAuth()
  const [viewing, setViewing] = useState(null)
  const [requesting, setRequesting] = useState(null)
  const [reason, setReason] = useState('')

  const load = useCallback(
    () =>
      api.get(`/officer/reports/${id}`).then((d) => {
        setCase(d)
        setNextStatus(d.allowed_transitions[0] ?? '')
      }).catch((e) => setError(e.message)),
    [id],
  )
  useEffect(() => {
    load()
  }, [load])

  const act = async (fn) => {
    setError('')
    try {
      await fn()
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const copy = (text, key) => {
    navigator.clipboard?.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(''), 1500)
  }

  const closeViewer = useCallback(() => {
    setViewing(null)
    load()
  }, [load])

  if (!c) return error ? <Alert>{error}</Alert> : <Spinner />

  return (
    <>
      <Link to="/petugas" className="text-sm text-brand-700 hover:underline">← Queue</Link>
      <PageHeader title={c.title} subtitle={`${c.category_label} · received ${formatDate(c.created_at)}`} action={<StatusBadge status={c.status} />} />
      <Alert>{error}</Alert>
      {viewing && <SecureViewer source={viewing} officerName={user.full_name} onClose={closeViewer} />}

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card space-y-4 p-5">
            <h2 className="font-semibold">Incident details</h2>
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              {[['Link / incident location', 'incident_url'], ['Perpetrator', 'scammer_account']].map(([label, k]) => (
                <div key={k}>
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="mt-0.5 flex items-start gap-2">
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs break-all text-slate-800">{c[k] || '–'}</code>
                    {c[k] && (
                      <button className="text-xs text-brand-700 hover:underline" onClick={() => copy(c[k], k)}>
                        {copied === k ? 'copied' : 'copy'}
                      </button>
                    )}
                  </dd>
                </div>
              ))}
              <div><dt className="text-slate-500">Incident date</dt><dd>{formatDate(c.incident_date, false)}</dd></div>
            </dl>
            <p className="text-xs text-slate-500">Links are displayed as text and cannot be clicked, to prevent officers from accidentally opening or spreading malicious content.</p>
          </section>

          <section className="card p-5">
            <h2 className="mb-2 font-semibold">Chronology</h2>
            <p className="text-sm whitespace-pre-wrap text-slate-800">{c.chronology}</p>
          </section>

          <section className="card p-5">
            <h2 className="mb-1 font-semibold">Attachments</h2>
            <p className="mb-3 flex items-center gap-1.5 text-xs text-slate-500">
              <LockIcon className="h-3.5 w-3.5" /> Only files permitted by the reporter can be viewed (preview, no download) during the open report status. Every access is logged and visible to the reporter.
            </p>
            {c.attachments.length === 0 ? (
              <p className="text-sm text-slate-500">No attachments.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {c.attachments.map((a) => {
                  const acc = a.access
                  const canRequest = !['selesai', 'ditolak'].includes(c.status) && ['none', 'denied', 'revoked'].includes(acc.status)
                  return (
                    <li key={a.id} className="py-3">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs capitalize">{a.kind}</span>
                        <span className="min-w-0 flex-1 truncate">
                          {acc.officer_can_view ? a.filename : <span className="text-slate-500">Attachment {a.no} · {a.mime}</span>}
                        </span>
                        <span className="text-xs text-slate-500">{formatBytes(a.size)}</span>
                        <AccessBadge status={acc.status} />
                        {acc.officer_can_view ? (
                          <button className="btn-primary btn-sm" onClick={() => setViewing({ path: `/officer/attachments/${a.id}/preview`, title: a.filename, openedAt: Date.now() })}>View</button>
                        ) : canRequest ? (
                          <button className="btn-secondary btn-sm" onClick={() => { setRequesting(a.id); setReason('') }}>Request access</button>
                        ) : (
                          <LockIcon className="h-4 w-4 text-slate-400" />
                        )}
                      </div>
                      {!acc.officer_can_view && acc.reason_blocked && acc.status !== 'none' && (
                        <p className="mt-1 text-xs text-slate-500">{acc.reason_blocked}</p>
                      )}
                      {requesting === a.id && (
                        <form
                          className="mt-2 space-y-2 rounded-lg bg-slate-50 p-3"
                          onSubmit={(e) => {
                            e.preventDefault()
                            act(async () => {
                              await api.post(`/officer/attachments/${a.id}/request-access`, { reason })
                              setRequesting(null)
                            })
                          }}
                        >
                          <textarea
                            className="input min-h-16"
                            placeholder="Reason (read by reporter), e.g. matching recording contents with chronology before summoning the reported party"
                            minLength={10}
                            maxLength={500}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                          />
                          <LengthHint value={reason} min={10} max={500} />
                          <div className="flex gap-2">
                            <button className="btn-primary btn-sm" disabled={reason.trim().length < 10}>Send request</button>
                            <button type="button" className="btn-secondary btn-sm" onClick={() => setRequesting(null)}>Cancel</button>
                          </div>
                        </form>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </div>

        <aside className="space-y-6">
          <section className="card space-y-2 p-5 text-sm">
            <h2 className="font-semibold">Reporter (masked)</h2>
            {[['Name', 'name'], ['National ID', 'nik'], ['Phone', 'phone'], ['Email', 'email']].map(([l, k]) => (
              <div key={k} className="flex justify-between gap-3">
                <span className="text-slate-500">{l}</span>
                <span className="font-mono text-xs">{c.reporter[k] ?? '–'}</span>
              </div>
            ))}
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Identity</span>
              <KycBadge status={c.reporter.identity.status} />
            </div>
            <Link to={`/petugas/verifikasi/${c.reporter.user_id}`} className="block pt-1 text-xs text-brand-700 hover:underline">
              Verification history / report identity issue →
            </Link>
          </section>

          {c.allowed_transitions.length > 0 && (
            <section className="card space-y-3 p-5">
              <h2 className="font-semibold">Change status</h2>
              <select className="input" value={nextStatus} onChange={(e) => setNextStatus(e.target.value)}>
                {c.allowed_transitions.map((s) => <option key={s} value={s}>{STATUS[s].label}</option>)}
              </select>
              <textarea className="input min-h-16" placeholder="Note for reporter (optional)" maxLength={2000} value={statusNote} onChange={(e) => setStatusNote(e.target.value)} />
              <LengthHint value={statusNote} max={2000} />
              <button
                className="btn-primary btn-sm w-full"
                onClick={() =>
                  act(async () => {
                    await api.patch(`/officer/reports/${id}/status`, { status: nextStatus, note: statusNote || null })
                    setStatusNote('')
                  })
                }
              >
                Save status
              </button>
            </section>
          )}

          <section className="card space-y-4 p-5">
            <h2 className="font-semibold">History & messages</h2>
            <EventTimeline events={c.events} />
            <form
              className="space-y-2 border-t border-slate-100 pt-4"
              onSubmit={(e) => {
                e.preventDefault()
                act(async () => {
                  await api.post(`/officer/reports/${id}/notes`, { note })
                  setNote('')
                })
              }}
            >
              <textarea className="input min-h-16" placeholder="Ask reporter / follow-up notes…" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
              <LengthHint value={note} min={1} max={2000} />
              <button className="btn-secondary btn-sm" disabled={!note.trim()}>Send message</button>
            </form>
          </section>
        </aside>
      </div>
    </>
  )
}
