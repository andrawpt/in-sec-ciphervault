import { useState } from 'react'
import { api } from '../api/client'
import { OFFICER_UNIT } from '../lib/constants'
import { formatDate } from '../lib/format'

export const SHARE_TEXT = `${OFFICER_UNIT} officers may view this file (without downloading) to verify and follow up on the report, until the report is closed. Access can be revoked at any time.`

export const ACCESS_LABEL = {
  none: { text: 'Not shared', cls: 'bg-slate-100 text-slate-600' },
  granted: { text: 'Shared with officers', cls: 'bg-emerald-50 text-emerald-700' },
  requested: { text: 'Officer requested access', cls: 'bg-amber-50 text-amber-800' },
  denied: { text: 'Request denied', cls: 'bg-red-50 text-red-700' },
  revoked: { text: 'Access revoked', cls: 'bg-slate-100 text-slate-600' },
}

export function AccessBadge({ status }) {
  const s = ACCESS_LABEL[status] ?? ACCESS_LABEL.none
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${s.cls}`}>{s.text}</span>
}

export function ShareToggle({ checked, onChange }) {
  return (
    <label className="mt-1.5 flex cursor-pointer items-start gap-2 text-xs text-slate-600">
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="font-medium text-slate-700">Allow officers to view this file.</span> {SHARE_TEXT}
      </span>
    </label>
  )
}

export function OwnerAccessPanel({ attachment, closed, onChanged, onError }) {
  const [busy, setBusy] = useState(false)
  const [showLog, setShowLog] = useState(false)
  const acc = attachment.access
  const act = async (action) => {
    setBusy(true)
    try {
      await api.put(`/attachments/${attachment.id}/access`, { action })
      onChanged()
    } catch (e) {
      onError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-slate-500">Officer access:</span>
        <AccessBadge status={acc.status} />
        {closed && acc.status === 'granted' && <span className="text-slate-500">(expired, report closed)</span>}
        {acc.view_count > 0 && (
          <button className="text-brand-700 hover:underline" onClick={() => setShowLog(!showLog)}>
            Viewed {acc.view_count}× {showLog ? '▲' : '▼'}
          </button>
        )}
        <span className="ml-auto flex gap-2">
          {!closed && acc.status === 'granted' && (
            <button className="btn-secondary btn-sm" disabled={busy} onClick={() => act('revoke')}>Revoke access</button>
          )}
          {!closed && ['none', 'denied', 'revoked'].includes(acc.status) && (
            <button className="btn-secondary btn-sm" disabled={busy} onClick={() => act('grant')}>Allow officers</button>
          )}
        </span>
      </div>
      {acc.status === 'requested' && !closed && (
        <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-amber-900">
          <p>
            <span className="font-medium">{acc.requested_by}</span> requested to view this file
            {acc.requested_at ? ` (${formatDate(acc.requested_at)})` : ''}.
          </p>
          <p className="mt-1">Reason: “{acc.request_reason}”</p>
          <p className="mt-1 text-amber-800/80">If approved, all officers can view this file until the report is closed.</p>
          <div className="mt-2 flex gap-2">
            <button className="btn-primary btn-sm" disabled={busy} onClick={() => act('grant')}>Approve</button>
            <button className="btn-secondary btn-sm" disabled={busy} onClick={() => act('deny')}>Deny</button>
          </div>
        </div>
      )}
      {showLog && (
        <ul className="mt-2 space-y-0.5 text-slate-600">
          {acc.views.map((v, i) => (
            <li key={i}>
              {formatDate(v.at)} · {v.officer}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
