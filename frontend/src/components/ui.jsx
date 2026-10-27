import { KYC, STATUS } from '../lib/constants'

export function StatusBadge({ status }) {
  const s = STATUS[status] ?? { label: status, cls: 'bg-slate-100 text-slate-700 ring-slate-300' }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      {s.label}
    </span>
  )
}

export function Alert({ kind = 'error', children }) {
  if (!children) return null
  const cls = {
    error: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    info: 'border-sky-200 bg-sky-50 text-sky-800',
    warn: 'border-amber-200 bg-amber-50 text-amber-900',
  }[kind]
  return <div className={`rounded-lg border px-3 py-2 text-sm ${cls}`}>{children}</div>
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-700" />
      {label}
    </div>
  )
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Field({ label, hint, error, children }) {
  return (
    <div>
      {label && <label className="label">{label}</label>}
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function ProgressBar({ value }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
      <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  )
}

export function LockIcon({ className = 'h-4 w-4' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden="true">
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 1 1 8 0v4" />
    </svg>
  )
}

export function ShieldIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3Zm-1.1 13.7-3.6-3.6 1.4-1.4 2.2 2.2 4.8-4.8 1.4 1.4-6.2 6.2Z" />
    </svg>
  )
}

export function KycBadge({ status }) {
  const s = KYC[status] ?? KYC.belum
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      {s.label}
    </span>
  )
}

export function LengthHint({ value = '', min = 0, max, unit = 'characters', exact = false }) {
  const len = value.trim().length
  const short = min > 0 && len < min
  const rule = exact ? `must be ${min} ${unit}` : [min > 0 && `min. ${min}`, max && `max. ${max}`].filter(Boolean).join(' · ')
  const cls = len === 0 ? 'text-slate-500' : short ? 'text-amber-700' : 'text-emerald-700'
  return (
    <p className={`mt-1 flex justify-between gap-3 text-xs ${cls}`} aria-live="polite">
      <span>
        {rule}
        {len > 0 && short ? ` · ${min - len} more needed` : ''}
        {len > 0 && !short && min > 0 ? ' · ✓' : ''}
      </span>
      <span className="shrink-0 tabular-nums">
        {len}
        {max ? `/${max}` : ''}
      </span>
    </p>
  )
}
