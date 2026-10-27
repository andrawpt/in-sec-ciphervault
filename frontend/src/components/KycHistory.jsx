import { formatDate } from '../lib/format'

const DOT = {
  diajukan: 'bg-slate-400',
  terverifikasi: 'bg-emerald-600',
  ditolak: 'bg-red-600',
  verifikasi_ulang: 'bg-amber-500',
}

export default function KycHistory({ history }) {
  if (!history?.length) return <p className="text-sm text-slate-500">No history yet.</p>
  return (
    <ol className="relative space-y-3 border-l border-slate-200 pl-5">
      {[...history].reverse().map((h, i) => (
        <li key={i} className="relative">
          <span className={`absolute top-1.5 -left-[25px] h-2.5 w-2.5 rounded-full ring-4 ring-surface ${DOT[h.action]}`} />
          <div className="text-xs text-slate-500">
            {formatDate(h.created_at)} · {h.actor}
          </div>
          <div className="text-sm font-medium text-slate-800">{h.label}</div>
          {h.note && <p className="mt-1 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{h.note}</p>}
        </li>
      ))}
    </ol>
  )
}
