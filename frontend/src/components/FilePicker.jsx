import { useRef } from 'react'
import { FILE_RULES } from '../lib/constants'
import { formatBytes } from '../lib/format'

export default function FilePicker({ kind, files, onChange, multiple = true, onError, extra }) {
  const ref = useRef(null)
  const rule = FILE_RULES[kind]
  const exts = rule.accept.split(',')

  const add = (list) => {
    const next = multiple ? [...files] : []
    for (const f of list) {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      if (!exts.includes(ext)) {
        onError?.(`${f.name}: unsupported format (${rule.label})`)
        continue
      }
      if (f.size > rule.maxMb * 1024 * 1024) {
        onError?.(`${f.name}: exceeds ${rule.maxMb} MB`)
        continue
      }
      next.push(f)
    }
    onChange(next)
  }

  return (
    <div>
      <div
        className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center hover:border-brand-600"
        onClick={() => ref.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          add(e.dataTransfer.files)
        }}
      >
        <p className="text-sm font-medium text-slate-700">Click or drag files here</p>
        <p className="mt-1 text-xs text-slate-500">{rule.label}</p>
        <input
          ref={ref}
          type="file"
          hidden
          accept={rule.accept}
          multiple={multiple}
          onChange={(e) => {
            add(e.target.files)
            e.target.value = ''
          }}
        />
      </div>
      {files.length > 0 && (
        <ul className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-surface text-sm">
          {files.map((f, i) => (
            <li key={i} className="px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{f.name}</span>
                <span className="flex shrink-0 items-center gap-3 text-xs text-slate-500">
                  {formatBytes(f.size)}
                  <button type="button" className="text-red-600 hover:underline" onClick={() => onChange(files.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                </span>
              </div>
              {extra?.(f)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
