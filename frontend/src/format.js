/** 时间与来源展示工具。来源名称来自 /api/crawlers。 */

import { ref } from 'vue'

export const crawlerSources = ref([])

const crawlerLabels = new Map()

export function setCrawlerSources(rows) {
  const next = []
  crawlerLabels.clear()
  for (const row of rows || []) {
    const key = String(row.key || '').trim()
    if (!key) continue
    const label = String(row.name || key)
    next.push({ key, label })
    crawlerLabels.set(key.toLowerCase(), label)
  }
  crawlerSources.value = next
}

export function crawlerLabel(crawler) {
  if (!crawler) return '未知来源'
  return crawlerLabels.get(String(crawler).toLowerCase()) || crawler
}

export function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const diff = Date.now() - d.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days <= 7) return `${days} 天前`
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
