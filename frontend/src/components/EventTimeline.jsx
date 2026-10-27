import { OFFICER_UNIT, STATUS } from '../lib/constants'
import { formatDate } from '../lib/format'

export default function EventTimeline({ events }) {
  if (!events?.length) return <p className="text-sm text-slate-500">No activity yet.</p>
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {events.map((e) => (
        <li key={e.id} className="relative">
          <span
            className={`absolute top-1.5 -left-[25px] h-2.5 w-2.5 rounded-full ring-4 ring-surface ${
              e.type === 'status' ? 'bg-brand-600' : 'bg-slate-400'
            }`}
          />
          <div className="text-xs text-slate-500">
            {formatDate(e.created_at)} · {e.actor_role === 'petugas' ? `${OFFICER_UNIT} Officer` : 'Reporter'}
          </div>
          {e.type === 'status' && (
            <div className="text-sm font-medium text-slate-800">
              {e.from_status ? `${STATUS[e.from_status]?.label} → ` : ''}
              {STATUS[e.to_status]?.label ?? e.to_status}
            </div>
          )}
          {e.note && (
            <p className="mt-1 rounded-lg bg-slate-50 px-3 py-2 text-sm whitespace-pre-wrap text-slate-700">{e.note}</p>
          )}
        </li>
      ))}
    </ol>
  )
}
