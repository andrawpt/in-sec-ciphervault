import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Alert, PageHeader, Spinner } from '../../components/ui'
import { CIPHERS, STATUS } from '../../lib/constants'

export default function Stats() {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.get('/officer/stats').then(setS).catch((e) => setError(e.message))
  }, [])
  if (!s) return error ? <Alert>{error}</Alert> : <Spinner />
  const maxCat = Math.max(1, ...s.by_category.map((c) => c.count))

  return (
    <>
      <PageHeader title="Statistics" subtitle="Aggregates without personal data." />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <div className="card p-4">
          <div className="text-xs text-slate-500">Total</div>
          <div className="text-2xl font-semibold">{s.total}</div>
        </div>
        {Object.entries(s.by_status).map(([k, v]) => (
          <div key={k} className="card p-4">
            <div className="text-xs text-slate-500">{STATUS[k]?.label}</div>
            <div className="text-2xl font-semibold">{v}</div>
          </div>
        ))}
      </div>

      <section className="card mt-6 p-5">
        <h2 className="mb-4 font-semibold">Reports by category</h2>
        <ul className="space-y-2">
          {s.by_category.map((c) => (
            <li key={c.category} className="grid grid-cols-[minmax(0,12rem)_1fr_2.5rem] items-center gap-3 text-sm">
              <span className="truncate text-slate-600">{c.label}</span>
              <div className="h-2.5 rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-brand-600" style={{ width: `${(c.count / maxCat) * 100}%` }} />
              </div>
              <span className="text-right tabular-nums">{c.count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card mt-6 p-5">
        <h2 className="font-semibold">Encryption performance from actual uploads</h2>
        <p className="mb-4 text-xs text-slate-500">
          Calculated from encryption times recorded when each file was uploaded. For controlled measurements, see benchmark results.
        </p>
        {s.encryption.length === 0 ? (
          <p className="text-sm text-slate-500">No files uploaded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500">
                <tr>
                  <th className="py-2 font-medium">Cipher</th>
                  <th className="py-2 text-right font-medium">Files</th>
                  <th className="py-2 text-right font-medium">Total data</th>
                  <th className="py-2 text-right font-medium">Total time</th>
                  <th className="py-2 text-right font-medium">Throughput</th>
                </tr>
              </thead>
              <tbody>
                {s.encryption.map((e) => (
                  <tr key={e.cipher} className="border-t border-slate-100">
                    <td className="py-2">{CIPHERS.find((c) => c.value === e.cipher)?.desc ?? e.cipher}</td>
                    <td className="py-2 text-right tabular-nums">{e.files}</td>
                    <td className="py-2 text-right tabular-nums">{e.total_mb} MB</td>
                    <td className="py-2 text-right tabular-nums">{e.total_enc_ms} ms</td>
                    <td className="py-2 text-right font-medium tabular-nums">{e.mb_per_s} MB/s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
