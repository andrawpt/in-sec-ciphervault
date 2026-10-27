import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, downloadFile } from '../../api/client'
import CipherSelect from '../../components/CipherSelect'
import { Alert, KycBadge, PageHeader, Spinner } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'
import { formatMs } from '../../lib/format'

export default function Profile() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [cipher, setCipher] = useState('AES-256-GCM')
  const [profile, setProfile] = useState(null)
  const [kyc, setKyc] = useState(null)
  const [error, setError] = useState('')
  const [delPass, setDelPass] = useState('')

  useEffect(() => {
    api.get(`/me/profile?cipher=${cipher}`).then(setProfile).catch((e) => setError(e.message))
  }, [cipher])
  useEffect(() => {
    api.get('/me/ktp').then((k) => setKyc(k.verification)).catch((e) => setError(e.message))
  }, [])

  const act = async (fn) => {
    setError('')
    try {
      await fn()
    } catch (e) {
      setError(e.message)
    }
  }

  const deleteAccount = () =>
    act(async () => {
      if (!window.confirm('All your reports, attachments, ID card, and personal data will be permanently deleted. Continue?')) return
      await api.del('/me', { password: delPass })
      logout()
      navigate('/login')
    })

  return (
    <>
      <PageHeader title="My Data" subtitle="View, download, or delete your personal data (data subject rights under privacy laws)." />
      <div className="mb-4">
        <Alert>{error}</Alert>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">Identity</h2>
            <CipherSelect value={cipher} onChange={setCipher} />
          </div>
          {!profile ? (
            <Spinner />
          ) : (
            <>
              <dl className="space-y-3 text-sm">
                {[['Full Name', 'full_name'], ['National ID (NIK)', 'nik'], ['Phone Number', 'phone'], ['Email', 'email']].map(([l, k]) => (
                  <div key={k} className="flex justify-between gap-4 border-b border-slate-100 pb-2">
                    <dt className="text-slate-500">{l}</dt>
                    <dd className="font-medium">{profile.data[k]}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs text-slate-500">
                Decrypted from copy {profile.cipher} in {formatMs(profile.decrypt_ms)}, integrity verified.
              </p>
            </>
          )}
        </section>

        <section className="card space-y-3 p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold">ID Verification</h2>
            {kyc && <KycBadge status={kyc.status} />}
          </div>
          <p className="text-sm text-slate-500">
            ID card scan, verification history, and officers who have viewed it are on the verification page.
          </p>
          <Link to="/pelapor/verifikasi" className="btn-secondary btn-sm">Open verification page</Link>
        </section>

        <section className="card space-y-3 p-5">
          <h2 className="font-semibold">Download all my data</h2>
          <p className="text-sm text-slate-500">Profile, verification status, report contents, history, and attachment list in a single JSON file.</p>
          <button className="btn-secondary btn-sm" onClick={() => act(() => downloadFile('/me/export', 'my-data.json'))}>
            Download JSON
          </button>
        </section>

        <section className="card space-y-3 border-red-200 p-5">
          <h2 className="font-semibold text-red-700">Delete account</h2>
          <p className="text-sm text-slate-500">
            Encryption keys and all your ciphertext will be deleted, rendering data irrecoverable by anyone.
          </p>
          <input className="input" type="password" placeholder="Password for confirmation" value={delPass} onChange={(e) => setDelPass(e.target.value)} />
          <button className="btn-danger btn-sm" disabled={!delPass} onClick={deleteAccount}>
            Permanently delete account
          </button>
        </section>
      </div>
    </>
  )
}
