const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await res.json()
  if (!res.ok || data.code !== 0) {
    throw new Error(data.message || `HTTP ${res.status}`)
  }
  return data.data
}

export const api = {
  overview: () => request('/api/stats/overview'),
  trend: () => request('/api/stats/trend'),
  keywords: () => request('/api/stats/keywords'),
  news: (page = 1) => request(`/api/news?page=${page}&page_size=20`),
  newsDetail: (id) => request(`/api/news/${id}`),
  events: () => request('/api/events'),
  ask: (body) => request('/api/chat/ask', { method: 'POST', body: JSON.stringify(body) }),
  watchlist: () => request('/api/watchlist'),
  createWatchlist: (body) => request('/api/watchlist', { method: 'POST', body: JSON.stringify(body) }),
  deleteWatchlist: (id) => request(`/api/watchlist/${id}`, { method: 'DELETE' }),
  monitor: () => request('/api/monitor/status'),
  exportReport: (body) => request('/api/reports/export', { method: 'POST', body: JSON.stringify(body) }),
}
