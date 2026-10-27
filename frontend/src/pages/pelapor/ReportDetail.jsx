import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, downloadFile, uploadFile } from '../../api/client'
import CipherSelect from '../../components/CipherSelect'
import EventTimeline from '../../components/EventTimeline'
import FilePicker from '../../components/FilePicker'
import VerifyResult from '../../components/VerifyResult'
import { OwnerAccessPanel, ShareToggle } from '../../components/access'
import { Alert, LengthHint, LockIcon, PageHeader, ProgressBar, Spinner, StatusBadge } from '../../components/ui'
import { STATUS, STATUS_FLOW } from '../../lib/constants'
import { formatBytes, formatDate, formatMs } from '../../lib/format'

function StatusSteps({ status }) {
  if (status === 'ditolak') return <Alert kind="error">Report rejected by officers. See notes in history.</Alert>
  const idx = STATUS_FLOW.indexOf(status)
  return (
    <ol className="grid grid-cols-4 gap-2">
      {STATUS_FLOW.map((s, i) => (
        <li key={s}>
          <div className={`h-1.5 rounded-full ${i <= idx ? 'bg-brand-600' : 'bg-slate-200'}`} />
          <div className={`mt-1 text-xs ${i <= idx ? 'font-medium text-brand-800' : 'text-slate-400'}`}>{STATUS[s].label}</div>
        </li>
      ))}
    </ol>
  )
}

export default function ReportDetail() {
  const { id } = useParams()
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [cipher, setCipher] = useState('AES-256-GCM')
  const [msg, setMsg] = useState('')
  const [verify, setVerify] = useState({})
  const [busy, setBusy] = useState('')
  const [note, setNote] = useState('')
  const [newDocs, setNewDocs] = useState([])
  const [newVideos, setNewVideos] = useState([])
  const [upProgress, setUpProgress] = useState(null)
  const [shareNew, setShareNew] = useState(true)

  const load = useCallback(() => api.get(`/reports/${id}`).then(setReport).catch((e) => setError(e.message)), [id])
  useEffect(() => {
    load()
  }, [load])

  const download = async (a) => {
    setBusy(a.id)
    setMsg('')
    setError('')
    try {
      const m = await downloadFile(`/attachments/${a.id}/download?cipher=${cipher}`, a.filename)
      setMsg(`${m.name} decrypted with ${m.cipher} in ${formatMs(m.decryptMs)}, integrity: ${m.integrity}.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const runVerify = async (a) => {
    setBusy(`v-${a.id}`)
    try {
      const r = await api.get(`/attachments/${a.id}/verify`)
      setVerify((v) => ({ ...v, [a.id]: r }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const sendNote = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/reports/${id}/notes`, { note })
      setNote('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const uploadMore = async () => {
    const queue = [...newDocs.map((f) => ['dokumen', f]), ...newVideos.map((f) => ['video', f])]
    setUpProgress(0)
    try {
      for (let i = 0; i < queue.length; i++) {
        const [kind, file] = queue[i]
        await uploadFile(`/reports/${id}/attachments`, { kind, file, share: String(shareNew) }, (v) => setUpProgress((i + v) / queue.length))
        const drop = kind === 'dokumen' ? setNewDocs : setNewVideos
        drop((list) => list.filter((f) => f !== file))
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setUpProgress(null)
      load()
    }
  }

  if (!report) return error ? <Alert>{error}</Alert> : <Spinner />
  const closed = ['selesai', 'ditolak'].includes(report.status)

  return (
    <>
      <Link to="/pelapor" className="text-sm text-brand-700 hover:underline">← My reports</Link>
      <PageHeader
        title={report.title}
        subtitle={`${report.category_label} · submitted ${formatDate(report.created_at)}`}
        action={<StatusBadge status={report.status} />}
      />
      <div className="space-y-2">
        <Alert>{error}</Alert>
        <Alert kind="success">{msg}</Alert>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card p-5">
            <StatusSteps status={report.status} />
          </section>

          <section className="card space-y-4 p-5">
            <h2 className="font-semibold text-slate-900">Report contents</h2>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Incident date</dt><dd>{formatDate(report.incident_date, false)}</dd></div>
              <div><dt className="text-slate-500">Link / incident location</dt><dd className="break-all">{report.incident_url || '–'}</dd></div>
              <div><dt className="text-slate-500">Perpetrator</dt><dd>{report.scammer_account || '–'}</dd></div>
            </dl>
            <div>
              <div className="text-sm text-slate-500">Chronology</div>
              <p className="mt-1 text-sm whitespace-pre-wrap text-slate-800">{report.chronology}</p>
            </div>
          </section>

          <section className="card p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold text-slate-900">Attachments</h2>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                Download from copy: <CipherSelect value={cipher} onChange={setCipher} />
              </div>
            </div>
            <p className="mb-3 flex items-center gap-1.5 text-xs text-slate-500">
              <LockIcon className="h-3.5 w-3.5" /> Each file is stored three times (AES, DES, RC4). Only you can download it; officers can only view files you have permitted.
            </p>
            {report.attachments.length === 0 && <p className="text-sm text-slate-500">No attachments yet.</p>}
            <ul className="divide-y divide-slate-100">
              {report.attachments.map((a) => (
                <li key={a.id} className="py-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 capitalize">{a.kind}</span>
                    <span className="min-w-0 flex-1 truncate text-sm">{a.filename}</span>
                    <span className="text-xs text-slate-500">{formatBytes(a.size)}</span>
                    <button className="btn-secondary btn-sm" disabled={busy === `v-${a.id}`} onClick={() => runVerify(a)}>
                      {busy === `v-${a.id}` ? 'Checking…' : 'Check 3 ciphers'}
                    </button>
                    <button className="btn-primary btn-sm" disabled={busy === a.id} onClick={() => download(a)}>
                      {busy === a.id ? 'Decrypting…' : 'Download'}
                    </button>
                  </div>
                  <OwnerAccessPanel attachment={a} closed={closed} onChanged={load} onError={setError} />
                  <VerifyResult result={verify[a.id]} />
                </li>
              ))}
            </ul>
            {!closed && (
              <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
                <h3 className="text-sm font-medium">Add evidence</h3>
                <div className="grid gap-3 md:grid-cols-2">
                  <FilePicker kind="dokumen" files={newDocs} onChange={setNewDocs} onError={setError} />
                  <FilePicker kind="video" files={newVideos} onChange={setNewVideos} onError={setError} />
                </div>
                <ShareToggle checked={shareNew} onChange={setShareNew} />
                {upProgress != null && <ProgressBar value={upProgress} />}
                <button className="btn-primary btn-sm" disabled={upProgress != null || newDocs.length + newVideos.length === 0} onClick={uploadMore}>
                  {upProgress != null ? 'Uploading & encrypting…' : 'Upload'}
                </button>
              </div>
            )}
          </section>
        </div>

        <aside className="card h-fit space-y-4 p-5">
          <h2 className="font-semibold text-slate-900">History & messages</h2>
          <EventTimeline events={report.events} />
          {!closed && (
            <form onSubmit={sendNote} className="space-y-2 border-t border-slate-100 pt-4">
              <textarea className="input min-h-20" placeholder="Reply or add information for officers…" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
              <LengthHint value={note} min={1} max={2000} />
              <button className="btn-primary btn-sm" disabled={!note.trim()}>Send message</button>
            </form>
          )}
        </aside>
      </div>
    </>
  )
}
