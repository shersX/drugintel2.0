const BASE = ''

let on401 = () => {}

export function onUnauthorized(fn) {
  on401 = fn
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch {
    throw new Error('无法连接后端服务，请确认 API 已在 :8000 启动')
  }
  let data
  try {
    data = await res.json()
  } catch {
    throw new Error(res.status === 500 ? '后端响应异常（请检查服务与数据库连接）' : `服务异常（HTTP ${res.status}）`)
  }
  if (res.status === 401 && !path.startsWith('/api/auth/login')) on401()
  if (!res.ok || data.code !== 0) {
    const detail = data.detail
    const message = data.message
      || (typeof detail === 'string' ? detail : detail?.message)
      || `HTTP ${res.status}`
    const err = new Error(message)
    err.status = res.status
    err.detail = detail
    throw err
  }
  return data.data
}

export const api = {
  login: (body) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  updateProfile: (body) => request('/api/auth/profile', { method: 'PUT', body: JSON.stringify(body) }),
  users: () => request('/api/admin/users'),
  createUser: (body) => request('/api/admin/users', { method: 'POST', body: JSON.stringify(body) }),
  disableUser: (id) => request(`/api/admin/users/${id}/disable`, { method: 'POST' }),
  enableUser: (id) => request(`/api/admin/users/${id}/enable`, { method: 'POST' }),
  resetUserPassword: (id, password) => request(`/api/admin/users/${id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  }),
  kickUser: (id) => request(`/api/admin/users/${id}/kick`, { method: 'POST' }),
  setChatLimit: (id, daily_chat_limit) => request(`/api/admin/users/${id}/chat-limit`, {
    method: 'PUT',
    body: JSON.stringify({ daily_chat_limit }),
  }),
  overview: () => request('/api/stats/overview'),
  trend: () => request('/api/stats/trend'),
  keywords: () => request('/api/stats/keywords'),
  news: (page = 1, { q = '', crawler = '' } = {}) => {
    const params = new URLSearchParams({ page: String(page), page_size: '20' })
    if (q) params.set('q', q)
    if (crawler) params.set('crawler', crawler)
    return request(`/api/news?${params}`)
  },
  newsDetail: (id) => request(`/api/news/${id}`),
  events: () => request('/api/events'),
  ask: (body) => request('/api/chat/ask', { method: 'POST', body: JSON.stringify(body) }),
  watchlist: () => request('/api/watchlist'),
  createWatchlist: (body) => request('/api/watchlist', { method: 'POST', body: JSON.stringify(body) }),
  deleteWatchlist: (id) => request(`/api/watchlist/${id}`, { method: 'DELETE' }),
  monitor: () => request('/api/monitor/status'),
  crawlConfig: () => request('/api/crawl/config'),
  crawlStatus: () => request('/api/crawl/status'),
  crawlStart: (body) => request('/api/crawl/start', { method: 'POST', body: JSON.stringify(body) }),
  crawlStop: () => request('/api/crawl/stop', { method: 'POST' }),
  llmProfiles: () => request('/api/llm/profiles'),
  createLlmProfile: (body) => request('/api/llm/profiles', { method: 'POST', body: JSON.stringify(body) }),
  updateLlmProfile: (id, body) => request(`/api/llm/profiles/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteLlmProfile: (id) => request(`/api/llm/profiles/${id}`, { method: 'DELETE' }),
  activateLlmProfile: (id, rebuild = false) => request(
    `/api/llm/profiles/${id}/activate?rebuild=${rebuild ? 'true' : 'false'}`,
    { method: 'POST' },
  ),
  testLlmProfile: (body) => request('/api/llm/profiles/test', { method: 'POST', body: JSON.stringify(body) }),
  exportReport: (body) => request('/api/reports/export', { method: 'POST', body: JSON.stringify(body) }),
}
