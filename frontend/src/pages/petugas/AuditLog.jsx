import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Alert, PageHeader, Spinner } from '../../components/ui'
import { formatDate } from '../../lib/format'

const ACTION_LABELS = {
  'auth.login': 'Sign in',
  'auth.login_failed': 'Failed sign in',
  'auth.register': 'Registration',
  'report.create': 'Report created',
  'attachment.upload': 'Attachment uploaded',
  'attachment.download': 'Attachment downloaded',
  'attachment.verify': 'Integrity check',
  'attachment.access_denied': 'Attachment access denied',
  'officer.view_report': 'Officer opened case',
  'officer.change_status': 'Status changed',
  'officer.add_note': 'Officer note',
  'officer.request_access': 'Officer requested file access',
  'officer.view_attachment': 'Officer viewed file',
  'officer.view_denied': 'Officer denied file view',
  'attachment.access_grant': 'Reporter granted access',
  'attachment.access_deny': 'Reporter denied access',
  'attachment.access_revoke': 'Reporter revoked access',
  'officer.open_verification': 'Officer opened ID verification',
  'officer.view_ktp': 'Officer viewed ID card',
  'officer.view_ktp_denied': 'ID card access denied',
  'officer.ktp_terverifikasi': 'ID verified',
  'officer.ktp_ditolak': 'ID rejected',
  'officer.ktp_flag': 'Re-verification requested',
  'me.view_profile': 'Reporter viewed profile',
  'me.upload_ktp': 'ID uploaded',
  'me.export': 'Data exported',
  'me.delete_account': 'Account deleted',
}

export default function AuditLog() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.get('/officer/audit?limit=200').then(setRows).catch((e) => setError(e.message))
  }, [])

  return (
    <>
      <PageHeader title="Audit Log" subtitle="Every data access is logged. Logs contain no personal data." />
      <Alert>{error}</Alert>
      {!rows ? (
        <Spinner />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Object</th>
                <th className="px-4 py-3 font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={`border-t border-slate-100 ${r.action.includes('denied') || r.action.includes('failed') ? 'bg-red-50/50' : ''}`}>
                  <td className="px-4 py-2 whitespace-nowrap text-slate-500">{formatDate(r.created_at)}</td>
                  <td className="px-4 py-2">{r.actor_role ?? '–'}</td>
                  <td className="px-4 py-2">{ACTION_LABELS[r.action] ?? r.action}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-500">
                    {r.target_type ? `${r.target_type}:${r.target_id?.slice(0, 8)}` : '–'}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-500">{r.detail ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
