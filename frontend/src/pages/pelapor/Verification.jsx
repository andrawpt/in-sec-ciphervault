import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadFile, uploadFile, api } from '../../api/client'
import FilePicker from '../../components/FilePicker'
import KycHistory from '../../components/KycHistory'
import VerifyResult from '../../components/VerifyResult'
import { Alert, Field, KycBadge, PageHeader, ProgressBar, Spinner } from '../../components/ui'
import { OFFICER_UNIT } from '../../lib/constants'
import { formatBytes, formatDate } from '../../lib/format'

const EXPLAIN = {
  belum: { kind: 'info', text: 'Upload your ID card scan. Once verified by officers, you can submit reports.' },
  menunggu: { kind: 'info', text: 'Your ID card is awaiting officer verification. Reports can be submitted once verified.' },
  terverifikasi: { kind: 'success', text: 'Your identity is verified. You can submit reports without uploading your ID card again.' },
  ditolak: { kind: 'error', text: 'Verification rejected. Make adjustments according to officer notes and re-upload your ID card.' },
  verifikasi_ulang: {
    kind: 'warn',
    text: 'Officers found potential issues with your identity. Report submission is temporarily disabled until you re-upload your ID card and pass verification.',
  },
}

export default function Verification() {
  const [info, setInfo] = useState(null)
  const [file, setFile] = useState([])
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [check, setCheck] = useState(null)

  const load = useCallback(() => api.get('/me/ktp').then(setInfo).catch((e) => setError(e.message)), [])
  useEffect(() => {
    load()
  }, [load])

  const upload = async () => {
    const st = info.verification.status
    if (st === 'terverifikasi' && !window.confirm('Replacing your ID card will start a new verification. While waiting, you will not be able to create reports. Continue?')) return
    setError('')
    setMsg('')
    setProgress(0)
    try {
      await uploadFile('/me/ktp', { file: file[0] }, setProgress)
      setFile([])
      setMsg('ID card encrypted and submitted for verification.')
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setProgress(null)
    }
  }

  if (!info) return error ? <Alert>{error}</Alert> : <Spinner />
  const v = info.verification
  const ex = EXPLAIN[v.status]
  const needUpload = ['belum', 'ditolak', 'verifikasi_ulang'].includes(v.status)

  return (
    <>
      <PageHeader title="ID Verification" subtitle="Reporter identity is verified once before reports can be submitted." action={<KycBadge status={v.status} />} />
      <div className="mb-4 space-y-2">
        <Alert>{error}</Alert>
        <Alert kind="success">{msg}</Alert>
        <Alert kind={ex.kind}>
          {ex.text}
          {v.status === 'terverifikasi' && (
            <> <Link to="/pelapor/lapor-baru" className="font-medium underline">Create report</Link></>
          )}
        </Alert>
        {v.officer_note && (
          <Alert kind={v.status === 'ditolak' ? 'error' : 'warn'}>
            <span className="font-medium">Officer note:</span> {v.officer_note}
          </Alert>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card space-y-4 p-5">
          <h2 className="font-semibold">{needUpload ? 'Upload ID Card' : 'Your ID Card'}</h2>
          {info.exists && (
            <div className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 truncate">{info.filename}</span>
              <span className="text-xs text-slate-500">{formatBytes(info.size)} · {formatDate(info.created_at)}</span>
              <button className="btn-secondary btn-sm" onClick={() => api.get(`/attachments/${info.id}/verify`).then(setCheck).catch((e) => setError(e.message))}>
                Check 3 ciphers
              </button>
              <button className="btn-secondary btn-sm" onClick={() => downloadFile(`/attachments/${info.id}/download`, info.filename).catch((e) => setError(e.message))}>
                Download
              </button>
            </div>
          )}
          <VerifyResult result={check} />
          <Field label={needUpload ? 'Scan or photo of ID card' : 'Replace ID card'} hint="Make sure the entire card is visible and the ID number is legible.">
            <FilePicker kind="ktp" files={file} onChange={setFile} multiple={false} onError={setError} />
          </Field>
          {progress != null && <ProgressBar value={progress} />}
          <button className="btn-primary" disabled={!file.length || progress != null} onClick={upload}>
            {needUpload ? 'Submit for verification' : 'Replace & resubmit'}
          </button>
          <p className="text-xs leading-relaxed text-slate-500">
            The ID card is encrypted and only you can download it. {OFFICER_UNIT} officers can only view its preview during the <i>pending verification</i> status to match the name and ID number with registration data. Once a decision is made, officer access is closed.
          </p>
        </section>

        <section className="space-y-6">
          <div className="card p-5">
            <h2 className="mb-3 font-semibold">Verification history</h2>
            <KycHistory history={info.history} />
          </div>
          <div className="card p-5">
            <h2 className="mb-1 font-semibold">Officers who have viewed your ID card</h2>
            {info.views.length === 0 ? (
              <p className="text-sm text-slate-500">Never opened yet.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm">
                {info.views.map((w, i) => (
                  <li key={i} className="flex justify-between gap-3">
                    <span>{w.officer}</span>
                    <span className="text-slate-500">{formatDate(w.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </>
  )
}
