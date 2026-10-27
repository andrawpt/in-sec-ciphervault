import { CIPHERS } from '../lib/constants'
import { formatBytes, formatMs } from '../lib/format'

export default function VerifyResult({ result }) {
  if (!result) return null
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50">
      <table className="w-full text-xs">
        <thead className="text-left text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">Copy</th>
            <th className="px-3 py-2 font-medium">Intact?</th>
            <th className="px-3 py-2 text-right font-medium">Encryption</th>
            <th className="px-3 py-2 text-right font-medium">Decryption</th>
            <th className="px-3 py-2 text-right font-medium">Ciphertext</th>
            <th className="px-3 py-2 text-right font-medium">Overhead</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((r) => (
            <tr key={r.cipher} className="border-t border-slate-200">
              <td className="px-3 py-2">{CIPHERS.find((c) => c.value === r.cipher)?.desc ?? r.cipher}</td>
              <td className={`px-3 py-2 font-medium ${r.ok ? 'text-emerald-700' : 'text-red-700'}`}>
                {r.ok ? '✓ identical' : `✗ ${r.error}`}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{formatMs(r.enc_ms)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatMs(r.decrypt_ms)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatBytes(r.cipher_size)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.overhead_bytes} B</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
