import { Component, useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { fetchBlob } from '../api/client'
import { Spinner } from './ui'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

class PdfErrorBoundary extends Component {
  state = { hasError: false }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  render() {
    if (this.state.hasError) {
      return <p className="p-4 text-sm text-red-700">Failed to render PDF preview.</p>
    }
    return this.props.children
  }
}

const inflight = new Map()
function loadOnce(source) {
  const key = `${source.path}:${source.openedAt}`
  if (!inflight.has(key)) {
    inflight.set(key, fetchBlob(source.path))
    setTimeout(() => inflight.delete(key), 60_000)
  }
  return inflight.get(key)
}

function PdfCanvasViewer({ buffer }) {
  const containerRef = useRef(null)
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let cancelled = false
    let doc = null
    let task = null
    const container = containerRef.current
    if (!container || !buffer) return
    container.innerHTML = ''
    setStatus('loading')

    try {
      task = pdfjsLib.getDocument({ data: buffer.slice(0) })
      task.promise.then(async (pdf) => {
        if (cancelled) {
          pdf.destroy().catch(() => {})
          return
        }
        doc = pdf
        const dpr = Math.min(window.devicePixelRatio || 1, 2)
        for (let num = 1; num <= pdf.numPages; num++) {
          if (cancelled) break
          const page = await pdf.getPage(num)
          const base = page.getViewport({ scale: 1.5 })
          const viewport = page.getViewport({ scale: 1.5 * dpr })
          const canvas = document.createElement('canvas')
          canvas.width = viewport.width
          canvas.height = viewport.height
          canvas.style.width = `${base.width}px`
          canvas.style.maxWidth = '100%'
          canvas.style.height = 'auto'
          canvas.className = 'pointer-events-none mx-auto mb-4 block rounded bg-white shadow-sm select-none'
          container.appendChild(canvas)
          const ctx = canvas.getContext('2d')
          await page.render({ canvasContext: ctx, viewport }).promise
        }
        if (!cancelled) setStatus('ready')
      }).catch(() => {
        if (!cancelled) setStatus('error')
      })
    } catch {
      setStatus('error')
    }

    return () => {
      cancelled = true
      try { doc?.destroy?.()?.catch?.(() => {}) } catch {}
      try { task?.destroy?.()?.catch?.(() => {}) } catch {}
      if (container) container.innerHTML = ''
    }
  }, [buffer])

  return (
    <div className="p-4">
      {status === 'loading' && <Spinner label="Rendering PDF securely…" />}
      {status === 'error' && <p className="p-4 text-sm text-red-700">Failed to render PDF preview.</p>}
      <div ref={containerRef} />
    </div>
  )
}

export default function SecureViewer({ source, officerName, onClose }) {
  const [state, setState] = useState({ loading: true })
  const [lockReason, setLockReason] = useState(null)

  useEffect(() => {
    let url
    let cancelled = false
    loadOnce(source)
      .then(async ({ blob, headers }) => {
        if (cancelled) return
        if (headers.get('X-Preview') === 'text-extract' || blob.type.startsWith('text/') || blob.type === 'message/rfc822') {
          setState({ text: await blob.text(), extracted: headers.get('X-Preview') === 'text-extract' })
        } else if (blob.type === 'application/pdf') {
          const buffer = await blob.arrayBuffer()
          if (!cancelled) setState({ pdfBuffer: buffer, type: blob.type })
        } else {
          url = URL.createObjectURL(blob)
          setState({ url, type: blob.type })
        }
      })
      .catch((e) => !cancelled && setState({ error: e.message }))

    const onKeyDown = (e) => {
      if (e.key === 'Escape') return onClose()
      const mod = e.metaKey || e.ctrlKey
      if (e.key === 'PrintScreen') {
        e.preventDefault()
        setLockReason('shortcut')
        navigator.clipboard?.writeText?.('').catch(() => {})
        return
      }
      if (mod && ['s', 'p', 'c', 'u'].includes(e.key.toLowerCase())) {
        e.preventDefault()
        return
      }
      if (mod && e.shiftKey) {
        setLockReason('shortcut')
      }
    }

    const onBlur = () => setLockReason((prev) => prev || 'blur')
    const onFocus = () => {
      if (!document.hidden) setLockReason((prev) => (prev === 'blur' ? null : prev))
    }
    const onVis = () => {
      if (document.hidden) setLockReason((prev) => prev || 'blur')
      else setLockReason((prev) => (prev === 'blur' ? null : prev))
    }

    window.addEventListener('keydown', onKeyDown, true)
    window.addEventListener('blur', onBlur)
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVis)
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
      window.removeEventListener('keydown', onKeyDown, true)
      window.removeEventListener('blur', onBlur)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [source, onClose])

  const obscured = lockReason !== null
  const stamp = `${officerName} · ${new Date().toLocaleString('en-US')} · CONFIDENTIAL`
  const block = (e) => e.preventDefault()

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/70 p-3 sm:p-6 print:bg-white" onClick={onClose}>
      <div className="hidden print:flex h-full w-full items-center justify-center text-center text-sm font-medium text-slate-700">
        Printing and Save as PDF are disabled for confidential previews.
      </div>
      <div
        className="mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-surface select-none print:hidden"
        onClick={(e) => e.stopPropagation()}
        onContextMenu={block}
        onCopy={block}
        onCut={block}
        onDragStart={block}
      >
        <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{source.title}</div>
            <div className="text-xs text-slate-500">
              Preview only. Saving, printing, and copying are disabled; this access is logged and visible to the reporter.
              {state.extracted && ' Document displayed as text; original formatting is not preserved.'}
            </div>
          </div>
          <button className="btn-secondary btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="relative min-h-0 flex-1 overflow-auto bg-slate-100" onContextMenu={block}>
          <div className={`min-h-full transition duration-150 ${obscured ? 'blur-xl opacity-15' : ''}`}>
            {state.loading && <div className="px-4"><Spinner label="Decrypting and verifying…" /></div>}
            {state.error && <div className="p-6 text-sm text-red-700">{state.error}</div>}
            {state.text != null && (
              <pre className="min-h-full p-6 font-mono text-sm whitespace-pre-wrap text-slate-800 select-none">{state.text}</pre>
            )}
            {state.url && state.type.startsWith('image/') && (
              <img src={state.url} alt="" draggable={false} className="pointer-events-none mx-auto max-h-full object-contain p-4 select-none" />
            )}
            {state.url && state.type.startsWith('video/') && (
              <video
                src={state.url}
                controls
                controlsList="nodownload noplaybackrate noremoteplayback"
                disablePictureInPicture
                onContextMenu={block}
                className="mx-auto max-h-full p-4"
              />
            )}
            {state.pdfBuffer && (
              <PdfErrorBoundary>
                <PdfCanvasViewer buffer={state.pdfBuffer} />
              </PdfErrorBoundary>
            )}
          </div>
          {obscured && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-900/40 p-6 text-center backdrop-blur-sm">
              <div className="space-y-3 rounded-xl bg-surface px-5 py-4 text-xs text-slate-700 shadow-lg">
                <p className="font-medium">
                  {lockReason === 'shortcut'
                    ? 'Preview locked because a screenshot shortcut was detected.'
                    : 'Preview hidden while window is unfocused.'}
                </p>
                {lockReason === 'shortcut' && (
                  <button type="button" className="btn-primary btn-sm" onClick={() => setLockReason(null)}>
                    Resume preview
                  </button>
                )}
              </div>
            </div>
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
