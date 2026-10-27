const TOKEN_KEY = 'lapor_siber_token'

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

function formatDetail(detail) {
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = d.loc?.slice(-1)[0]
        const msg = (d.msg || '').replace(/^Value error, /, '')
        return field && field !== 'body' ? `${field}: ${msg}` : msg
      })
      .join(' · ')
  }
  return JSON.stringify(detail)
}

function authHeaders() {
  const t = tokenStore.get()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function handleError(res) {
  if (res.status === 401 && tokenStore.get()) {
    tokenStore.clear()
    window.dispatchEvent(new Event('auth:expired'))
  }
  let message = `${res.status} ${res.statusText}`
  try {
    message = formatDetail((await res.json()).detail) || message
  } catch {
  }
  throw new ApiError(res.status, message)
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = authHeaders()
  let payload
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload })
  if (!res.ok) await handleError(res)
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (p) => request(p),
  post: (p, b) => request(p, { method: 'POST', body: b ?? {} }),
  patch: (p, b) => request(p, { method: 'PATCH', body: b }),
  put: (p, b) => request(p, { method: 'PUT', body: b }),
  del: (p, b) => request(p, { method: 'DELETE', body: b }),
}

export function uploadFile(path, fields, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    Object.entries(fields).forEach(([k, v]) => form.append(k, v))
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api${path}`)
    const t = tokenStore.get()
    if (t) xhr.setRequestHeader('Authorization', `Bearer ${t}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let data = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new ApiError(xhr.status, formatDetail(data?.detail) || `Upload failed (${xhr.status})`))
    }
    xhr.onerror = () => reject(new ApiError(0, 'Connection to server lost'))
    xhr.send(form)
  })
}

function filenameFrom(disposition, fallback) {
  if (!disposition) return fallback
  const star = disposition.match(/filename\*=(?:UTF-8|utf-8)''([^;]+)/)
  if (star) return decodeURIComponent(star[1])
  const plain = disposition.match(/filename="?([^";]+)"?/)
  return plain ? plain[1] : fallback
}

export async function fetchBlob(path) {
  const res = await fetch(`/api${path}`, { headers: authHeaders() })
  if (!res.ok) await handleError(res)
  return { blob: await res.blob(), headers: res.headers }
}

export async function downloadFile(path, fallbackName = 'download') {
  const res = await fetch(`/api${path}`, { headers: authHeaders() })
  if (!res.ok) await handleError(res)
  const blob = await res.blob()
  const name = filenameFrom(res.headers.get('Content-Disposition'), fallbackName)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
  return {
    name,
    size: blob.size,
    cipher: res.headers.get('X-Cipher'),
    integrity: res.headers.get('X-Integrity'),
    decryptMs: Number(res.headers.get('X-Decrypt-Ms')),
  }
}
