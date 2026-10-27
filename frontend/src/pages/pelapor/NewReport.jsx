import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, uploadFile } from '../../api/client'
import FilePicker from '../../components/FilePicker'
import { ShareToggle } from '../../components/access'
import { Alert, Field, KycBadge, LengthHint, PageHeader, ProgressBar, Spinner } from '../../components/ui'
import { CATEGORIES, OFFICER_UNIT, categoryLabel } from '../../lib/constants'

const STEPS = ['Incident category', 'Chronology', 'Evidence', 'Submit']

function localToday() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function NewReport() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    category: '', incident_date: '', title: '', chronology: '', incident_url: '', scammer_account: '', consent: false,
  })
  const [docs, setDocs] = useState([])
  const [videos, setVideos] = useState([])
  const [notShared, setNotShared] = useState(() => new Set())
  const [kyc, setKyc] = useState(null)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const shareExtra = (f) => (
    <ShareToggle
      checked={!notShared.has(f)}
      onChange={(on) =>
        setNotShared((prev) => {
          const next = new Set(prev)
          on ? next.delete(f) : next.add(f)
          return next
        })
      }
    />
  )
  const evidence = [...docs, ...videos]
  const sharedCount = evidence.filter((f) => !notShared.has(f)).length

  useEffect(() => {
    api.get('/me/ktp').then((k) => setKyc(k.verification)).catch((e) => setError(e.message))
  }, [])

  const canNext = [
    () => form.category,
    () => form.title.trim().length >= 5 && form.chronology.trim().length >= 20,
    () => true,
    () => form.consent,
  ][step]()

  const submit = async () => {
    setError('')
    const queue = [
      ...docs.map((f) => ({ f, kind: 'dokumen' })),
      ...videos.map((f) => ({ f, kind: 'video' })),
    ]
    setProgress(queue.map(({ f, kind }) => ({ name: f.name, kind, value: 0, status: 'waiting' })))
    const update = (i, patch) => setProgress((p) => p.map((x, j) => (j === i ? { ...x, ...patch } : x)))

    let reportId
    try {
      const body = { ...form, incident_date: form.incident_date || null, incident_url: form.incident_url || null, scammer_account: form.scammer_account || null }
      reportId = (await api.post('/reports', body)).id
    } catch (e) {
      setProgress(null)
      return setError(e.message)
    }
    let failed = 0
    for (let i = 0; i < queue.length; i++) {
      const { f, kind } = queue[i]
      update(i, { status: 'uploading' })
      try {
        await uploadFile(`/reports/${reportId}/attachments`, { kind, file: f, share: String(!notShared.has(f)) }, (v) => update(i, { value: v, status: v >= 1 ? 'encrypting' : 'uploading' }))
        update(i, { value: 1, status: 'saved' })
      } catch (e) {
        failed++
        update(i, { status: `failed: ${e.message}` })
      }
    }
    if (failed === 0) navigate(`/pelapor/laporan/${reportId}`)
    else setError(`Report submitted, but ${failed} files failed to upload. You can add them from the report page.`)
    setForm((f) => ({ ...f, _doneId: reportId }))
  }

  if (!kyc) return error ? <Alert>{error}</Alert> : <Spinner />
  if (!kyc.can_create_report) {
    return (
      <>
        <PageHeader title="Create Report" />
        <div className="card mx-auto max-w-xl space-y-4 p-8 text-center">
          <KycBadge status={kyc.status} />
          <h2 className="text-lg font-semibold text-slate-900">
            {kyc.status === 'verifikasi_ulang' ? 'Report creation temporarily closed' : 'ID verification required'}
          </h2>
          <p className="text-sm text-slate-600">
            {{
              belum: 'Before submitting a report, upload your ID card for verification by officers. Required only once; subsequent reports do not require an ID card.',
              menunggu: 'Your ID card is being verified by officers. You can create a report once verified.',
              ditolak: 'ID verification was rejected. Please re-upload your ID card according to the officer note.',
              verifikasi_ulang: 'Officers requested re-verification of your identity. Re-upload your ID card to re-enable report submission.',
            }[kyc.status]}
          </p>
          {kyc.officer_note && <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">Officer note: {kyc.officer_note}</p>}
          <Link to="/pelapor/verifikasi" className="btn-primary">
            {kyc.status === 'menunggu' ? 'View verification status' : 'Go to ID verification page'}
          </Link>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader title="Create Report" subtitle="Fill in as completely as possible. All data is encrypted before storage." />
      <ol className="mb-6 flex flex-wrap gap-2 text-xs">
        {STEPS.map((s, i) => (
          <li
            key={s}
            className={`rounded-full px-3 py-1 font-medium ${
              i === step ? 'bg-brand-solid text-white' : i < step ? 'bg-brand-100 text-brand-800' : 'bg-slate-100 text-slate-500'
            }`}
          >
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      <div className="card space-y-5 p-6">
        <Alert>{error}</Alert>

        {step === 0 && (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              {CATEGORIES.map((c) => (
                <label
                  key={c.value}
                  className={`cursor-pointer rounded-lg border p-3 ${
                    form.category === c.value ? 'border-brand-600 bg-brand-50' : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <input type="radio" name="category" value={c.value} className="sr-only" checked={form.category === c.value} onChange={set('category')} />
                  <div className="text-sm font-medium text-slate-800">{c.label}</div>
                  <div className="text-xs text-slate-500">{c.hint}</div>
                </label>
              ))}
            </div>
            <Field label="Incident date (optional)">
              <input type="date" className="input max-w-xs" max={localToday()} value={form.incident_date} onChange={set('incident_date')} />
            </Field>
          </>
        )}

        {step === 1 && (
          <>
            <Alert kind="info">
              Write as much as you feel comfortable sharing. You are not required to provide details that cause distress, and additional information can be added later via messages to officers.
            </Alert>
            <Field label="Short title">
              <input className="input" maxLength={120} placeholder="Example: Sexually suggestive messages from a senior in class group" value={form.title} onChange={set('title')} />
              <LengthHint value={form.title} min={5} max={120} />
            </Field>
            <Field label="Chronology">
              <textarea className="input min-h-40" maxLength={5000} placeholder="What happened, when, where, and who was involved." value={form.chronology} onChange={set('chronology')} />
              <LengthHint value={form.chronology} min={20} max={5000} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Post link / incident location (optional)">
                <input className="input" maxLength={2048} placeholder="https://instagram.com/p/… or Building C 2nd floor" value={form.incident_url} onChange={set('incident_url')} />
                <LengthHint value={form.incident_url} max={2048} />
              </Field>
              <Field label="Perpetrator (optional)">
                <input className="input" maxLength={200} placeholder="Name, student ID, or social media handle" value={form.scammer_account} onChange={set('scammer_account')} />
                <LengthHint value={form.scammer_account} max={200} />
              </Field>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <Field label="Document evidence" hint="Chat screenshots, written timeline, medical/forensic report, etc.">
              <FilePicker kind="dokumen" files={docs} onChange={setDocs} onError={setError} extra={shareExtra} />
            </Field>
            <Field label="Video evidence" hint="Incident footage, or screen recording of chat/posts.">
              <FilePicker kind="video" files={videos} onChange={setVideos} onError={setError} extra={shareExtra} />
            </Field>
          </>
        )}

        {step === 3 && (
          <>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Category</dt><dd className="font-medium">{categoryLabel(form.category)}</dd></div>
              <div><dt className="text-slate-500">Title</dt><dd className="font-medium">{form.title}</dd></div>
              <div><dt className="text-slate-500">Documents</dt><dd>{docs.length} files</dd></div>
              <div><dt className="text-slate-500">Videos</dt><dd>{videos.length} files</dd></div>
              <div className="sm:col-span-2">
                <dt className="text-slate-500">Officer access to evidence</dt>
                <dd>
                  {evidence.length === 0
                    ? 'No evidence'
                    : `${sharedCount} of ${evidence.length} files viewable by officers` +
                      (sharedCount < evidence.length ? '; the rest can only be viewed if you approve an officer request.' : '.')}
                  {' '}ID card scan is not shared.
                </dd>
              </div>
            </dl>
            <label className="flex gap-3 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
              <input type="checkbox" className="mt-0.5" checked={form.consent} onChange={set('consent')} />
              <span>
                I consent to the contents of this report (chronology, link/location, and perpetrator identity) being read by {OFFICER_UNIT} officers for handling purposes. My identity is displayed masked to officers. Files I authorize may be viewed by officers (without downloading) until the report is closed, and this permission can be revoked at any time.
              </span>
            </label>
            {progress && (
              <ul className="space-y-3">
                {progress.map((p, i) => (
                  <li key={i} className="text-sm">
                    <div className="mb-1 flex justify-between gap-2">
                      <span className="truncate">{p.name}</span>
                      <span className={`shrink-0 text-xs ${p.status.startsWith('failed') ? 'text-red-600' : 'text-slate-500'}`}>{p.status}</span>
                    </div>
                    <ProgressBar value={p.value} />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        <div className="flex justify-between border-t border-slate-100 pt-4">
          <button className="btn-secondary" disabled={step === 0 || progress} onClick={() => setStep(step - 1)}>
            Back
          </button>
          {form._doneId ? (
            <Link className="btn-primary" to={`/pelapor/laporan/${form._doneId}`}>View report</Link>
          ) : step < STEPS.length - 1 ? (
            <button className="btn-primary" disabled={!canNext} onClick={() => { setError(''); setStep(step + 1) }}>
              Next
            </button>
          ) : (
            <button className="btn-primary" disabled={!canNext || progress} onClick={submit}>
              {progress ? 'Submitting…' : 'Submit report'}
            </button>
          )}
        </div>
      </div>
    </>
  )
}
