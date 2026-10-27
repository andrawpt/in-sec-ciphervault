import { useEffect, useState } from 'react'
import { fetchBlob } from '../api/client'
import { Spinner } from './ui'

const inflight = new Map()
function loadOnce(source) {
  const key = `${source.path}:${source.openedAt}`
  if (!inflight.has(key)) {
    inflight.set(key, fetchBlob(source.path))
    setTimeout(() => inflight.delete(key), 60_000)
  }
  return inflight.get(key)
}

export default function SecureViewer({ source, officerName, onClose }) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let url
    let cancelled = false
    loadOnce(source)
      .then(async ({ blob, headers }) => {
        if (cancelled) return
        if (headers.get('X-Preview') === 'text-extract' || blob.type.startsWith('text/') || blob.type === 'message/rfc822') {
          setState({ text: await blob.text(), extracted: headers.get('X-Preview') === 'text-extract' })
        } else {
          url = URL.createObjectURL(blob)
          setState({ url, type: blob.type })
        }
      })
      .catch((e) => !cancelled && setState({ error: e.message }))
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
      window.removeEventListener('keydown', onKey)
    }
  }, [source, onClose])

  const stamp = `${officerName} · ${new Date().toLocaleString('en-US')} · CONFIDENTIAL`
  const block = (e) => e.preventDefault()

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/70 p-3 sm:p-6" onClick={onClose}>
      <div className="mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-surface" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{source.title}</div>
            <div className="text-xs text-slate-500">
              Preview only. This access is logged and visible to the reporter.
              {state.extracted && ' Document displayed as text; original formatting is not preserved.'}
            </div>
          </div>
          <button className="btn-secondary btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="relative min-h-0 flex-1 overflow-auto bg-slate-100" onContextMenu={block}>
          {state.loading && <div className="px-4"><Spinner label="Decrypting and verifying…" /></div>}
          {state.error && <div className="p-6 text-sm text-red-700">{state.error}</div>}
          {state.text != null && (
            <pre className="min-h-full p-6 font-mono text-sm whitespace-pre-wrap text-slate-800 select-text">{state.text}</pre>
          )}
          {state.url && state.type.startsWith('image/') && (
            <img src={state.url} alt="" draggable={false} className="mx-auto max-h-full object-contain p-4" />
          )}
          {state.url && state.type.startsWith('video/') && (
            <video src={state.url} controls controlsList="nodownload noremoteplayback" disablePictureInPicture className="mx-auto max-h-full p-4" />
          )}
          {state.url && state.type === 'application/pdf' && (
            <iframe src={`${state.url}#toolbar=0`} title="preview" className="h-full min-h-[70vh] w-full" />
          )}
          <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
            <div className="absolute -inset-1/2 flex rotate-[-24deg] flex-wrap content-start gap-x-16 gap-y-20 opacity-[0.13]">
              {Array.from({ length: 80 }).map((_, i) => (
                <span key={i} className="text-sm font-semibold whitespace-nowrap text-slate-900">{stamp}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
