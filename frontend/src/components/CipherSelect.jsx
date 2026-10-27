import { CIPHERS } from '../lib/constants'

export default function CipherSelect({ value, onChange, className = '' }) {
  return (
    <select className={`input w-auto py-1.5 text-xs ${className}`} value={value} onChange={(e) => onChange(e.target.value)}>
      {CIPHERS.map((c) => (
        <option key={c.value} value={c.value}>
          {c.desc}
        </option>
      ))}
    </select>
  )
}
