import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import AuthShell from '../components/AuthShell'
import { Alert, Field } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { OFFICER_UNIT } from '../lib/constants'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={user.role === 'petugas' ? '/petugas' : '/pelapor'} replace />

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const me = await login(form.email, form.password)
      navigate(me.role === 'petugas' ? '/petugas' : '/pelapor')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Sign In" subtitle={`For reporters and ${OFFICER_UNIT} officers.`}>
      <form onSubmit={submit} className="card space-y-4 p-6">
        <Alert>{error}</Alert>
        <Field label="Email">
          <input
            className="input"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field label="Password">
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        <button className="btn-primary w-full" disabled={busy}>
          {busy ? 'Processing…' : 'Sign In'}
        </button>
        <p className="text-center text-sm text-slate-500">
          Don't have an account?{' '}
          <Link to="/daftar" className="font-medium text-brand-700 hover:underline">
            Register as a reporter
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
