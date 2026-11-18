import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Alert, PageHeader, Spinner } from '../../components/ui'
import { CIPHERS, STATUS } from '../../lib/constants'

const CIPHER_ORDER = ['AES-256-GCM', 'RC4-HMAC', 'DES-CBC-HMAC']

const CIPHER_STYLE = {
  'AES-256-GCM': { bar: 'bg-emerald-600', fill: '#059669', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  'RC4-HMAC': { bar: 'bg-sky-500', fill: '#0ea5e9', badge: 'bg-sky-50 text-sky-700 border-sky-200' },
  'DES-CBC-HMAC': { bar: 'bg-rose-500', fill: '#f43f5e', badge: 'bg-rose-50 text-rose-700 border-rose-200' },
}

const BAR_TRANSITION = 'y 450ms cubic-bezier(0.22, 1, 0.36, 1), height 450ms cubic-bezier(0.22, 1, 0.36, 1), opacity 200ms ease'
const LABEL_TRANSITION = 'transform 450ms cubic-bezier(0.22, 1, 0.36, 1)'

const METRICS = [
  { key: 'mb_per_s', label: 'Throughput (MB/s)', unit: 'MB/s', hint: 'Higher bar = faster encryption throughput (MB/s)' },
  { key: 'avg_enc_ms', label: 'Avg time (ms)', unit: 'ms', hint: 'Lower bar = faster encryption time (ms)' },
  { key: 'avg_overhead_bytes', label: 'Overhead (B)', unit: 'B', hint: 'Lower bar = smaller metadata & key-wrap overhead (Bytes)' },
]

function metricValue(row, metric) {
  if (!row) return 0
  return Number(row[metric] || 0)
}

function GroupedBarChart({ byType, metric }) {
  const [hovered, setHovered] = useState(null)
  const extensions = [...new Set(byType.map((r) => r.file_type).filter(Boolean))]
  const activeMetric = METRICS.find((m) => m.key === metric) ?? METRICS[0]
  const unit = activeMetric.unit

  if (extensions.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No encrypted file uploads recorded yet.</p>
  }

  const values = byType.map((r) => metricValue(r, metric))
  const rawMax = Math.max(1, ...values)
  const magnitude = 10 ** Math.floor(Math.log10(rawMax))
  const yMax = Math.ceil(rawMax / magnitude) * magnitude
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => Math.round(yMax * t * 10) / 10)

  const pad = { top: 24, right: 20, bottom: 52, left: 56 }
  const W = Math.max(720, pad.left + pad.right + extensions.length * 140)
  const H = 280
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom
  const groupW = plotW / extensions.length
  const barW = Math.min(36, Math.max(16, Math.floor((groupW * 0.65) / CIPHER_ORDER.length)))
  const gap = Math.min(10, Math.max(4, Math.floor(barW * 0.25)))
  const groupBarsW = CIPHER_ORDER.length * barW + (CIPHER_ORDER.length - 1) * gap

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-medium text-slate-600">{activeMetric.hint}</span>
        <div className="flex flex-wrap items-center gap-4">
          {CIPHER_ORDER.map((c) => {
            const active = hovered?.cipher === c
            return (
              <span
                key={c}
                onMouseEnter={() => setHovered({ cipher: c, fileType: null })}
                onMouseLeave={() => setHovered(null)}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-0.5 transition ${
                  active ? 'bg-slate-200/80 font-semibold text-slate-900' : 'text-slate-700 hover:text-slate-900'
                }`}
              >
                <span className="inline-block h-2.5 w-2.5 rounded-xs" style={{ backgroundColor: CIPHER_STYLE[c].fill }} />
                {CIPHERS.find((x) => x.value === c)?.label ?? c}
              </span>
            )
          })}
        </div>
      </div>

      <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible" style={extensions.length > 4 ? { minWidth: W } : undefined} role="img" aria-label="Grouped bar chart of cipher performance by file extension">
        {ticks.map((t) => {
          const y = pad.top + plotH - (t / yMax) * plotH
          return (
            <g key={t}>
              <line x1={pad.left} y1={y} x2={W - pad.right} y2={y} className="stroke-slate-200" strokeDasharray={t === 0 ? undefined : '4 4'} />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize="11" className="fill-slate-500">
                {t}
              </text>
            </g>
          )
        })}

        <text x={14} y={pad.top + plotH / 2} textAnchor="middle" fontSize="11" className="fill-slate-500" transform={`rotate(-90 14 ${pad.top + plotH / 2})`}>
          {unit}
        </text>

        {extensions.map((ext, gi) => {
          const gx = pad.left + gi * groupW + (groupW - groupBarsW) / 2
          const groupRows = byType.filter((r) => r.file_type === ext)
          const fileCount = groupRows.reduce((s, r) => s + (r.files ?? 0), 0)
          const totalMb = Math.round(groupRows.reduce((s, r) => s + (r.total_mb ?? 0), 0) * 100) / 100
          const extLabel = `.${ext}`
          return (
            <g key={ext}>
              {CIPHER_ORDER.map((c, ci) => {
                const row = groupRows.find((r) => r.cipher === c)
                const val = metricValue(row, metric)
                const h = row ? Math.max(3, (val / yMax) * plotH) : 0
                const x = gx + ci * (barW + gap)
                const y = pad.top + plotH - h
                const isMatch = hovered
                  ? hovered.fileType
                    ? hovered.fileType === ext && hovered.cipher === c
                    : hovered.cipher === c
                  : false
                const isDimmed = hovered !== null && !isMatch
                const cipherLabel = CIPHERS.find((x) => x.value === c)?.label ?? c
                return (
                  <g key={c}>
                    {row ? (
                      <>
                        <rect
                          x={x}
                          y={y}
                          width={barW}
                          height={h}
                          rx="4"
                          fill={CIPHER_STYLE[c].fill}
                          opacity={isDimmed ? 0.3 : 1}
                          className="cursor-pointer"
                          style={{ transition: BAR_TRANSITION }}
                          onMouseEnter={() =>
                            setHovered({ fileType: ext, fileLabel: extLabel, cipher: c, cipherLabel, val, x: x + barW / 2, y })
                          }
                          onMouseLeave={() => setHovered(null)}
                        />
                        <text
                          x={x + barW / 2}
                          y={0}
                          textAnchor="middle"
                          fontSize="10"
                          fontWeight="600"
                          opacity={isDimmed ? 0.35 : 1}
                          className="pointer-events-none fill-slate-700"
                          style={{ transform: `translateY(${y - 6}px)`, transition: LABEL_TRANSITION }}
                        >
                          {val}
                        </text>
                      </>
                    ) : (
                      <rect x={x} y={pad.top + plotH - 2} width={barW} height={2} className="fill-slate-300" opacity={isDimmed ? 0.35 : 1} />
                    )}
                  </g>
                )
              })}
              <text x={pad.left + gi * groupW + groupW / 2} y={H - 24} textAnchor="middle" fontSize="12" fontWeight="600" className="fill-slate-700">
                {extLabel}
              </text>
              <text x={pad.left + gi * groupW + groupW / 2} y={H - 9} textAnchor="middle" fontSize="10" className="fill-slate-500">
                {`${fileCount} file${fileCount === 1 ? '' : 's'} · ${totalMb} MB`}
              </text>
            </g>
          )
        })}

        {hovered?.fileType && (() => {
          const tipW = 160
          const tipH = 44
          const tx = Math.min(Math.max(hovered.x - tipW / 2, 8), W - tipW - 8)
          const ty = Math.max(4, hovered.y - tipH - 20)
          return (
            <g className="pointer-events-none">
              <rect x={tx} y={ty} width={tipW} height={tipH} rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1" opacity="0.96" />
              <circle cx={tx + 12} cy={ty + 15} r="4" fill={CIPHER_STYLE[hovered.cipher].fill} />
              <text x={tx + 22} y={ty + 18} fontSize="11" fontWeight="600" fill="#f8fafc">
                {hovered.cipherLabel}
              </text>
              <text x={tx + 12} y={ty + 34} fontSize="10" fill="#cbd5e1">
                {`${hovered.fileLabel}: ${hovered.val} ${unit}`}
              </text>
            </g>
          )
        })()}
      </svg>
      </div>
    </div>
  )
}

export default function Stats() {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  const [metric, setMetric] = useState('mb_per_s')
  useEffect(() => {
    api.get('/officer/stats').then(setS).catch((e) => setError(e.message))
  }, [])
  if (!s) return error ? <Alert>{error}</Alert> : <Spinner />
  const maxCat = Math.max(1, ...s.by_category.map((c) => c.count))
  const byType = s.encryption_by_type ?? []

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

      <section className="card mt-6 p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Cipher suitability by file extension</h2>
            <p className="text-xs text-slate-500">
              Visual comparison of AES, DES, and RC4 across uploaded file extensions to evaluate which algorithm fits each format best.
            </p>
          </div>
          <div className="flex flex-wrap rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
            {METRICS.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setMetric(m.key)}
                className={`rounded-md px-2.5 py-1 font-medium transition ${
                  metric === m.key ? 'bg-surface text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <GroupedBarChart byType={byType} metric={metric} />
      </section>
    </>
  )
}
