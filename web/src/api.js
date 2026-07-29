// Schlanker Fetch-Wrapper. Sessions laufen über httpOnly-Cookies (credentials: include).
const BASE = '/api'

async function req(path, opts = {}) {
  const isForm = opts.body instanceof FormData
  const res = await fetch(BASE + path, {
    credentials: 'include',
    ...opts,
    headers: {
      Accept: 'application/json',
      ...(opts.body != null && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...(opts.headers || {})
    }
  })
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('json') ? await res.json() : await res.text()
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText
    throw Object.assign(new Error(detail), { status: res.status, data })
  }
  return data
}

export const api = {
  get: (p) => req(p),
  post: (p, body) => req(p, { method: 'POST', body: body != null ? JSON.stringify(body) : undefined }),
  put: (p, body) => req(p, { method: 'PUT', body: JSON.stringify(body) }),
  patch: (p, body) => req(p, { method: 'PATCH', body: JSON.stringify(body) }),
  del: (p) => req(p, { method: 'DELETE' }),
  upload: (p, formData) => req(p, { method: 'POST', body: formData })
}
