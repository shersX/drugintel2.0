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

const BEIJING_WALL = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?(?:\.\d+)?$/

function parseDate(value) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const raw = String(value).trim()
  // 后端已输出北京墙钟 "YYYY-MM-DD HH:mm" 时，勿再按浏览器本地时区偏移
  const wall = BEIJING_WALL.exec(raw)
  if (wall && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(raw)) {
    const d = new Date(`${wall[1]}T${wall[2]}:00+08:00`)
    return Number.isNaN(d.getTime()) ? null : d
  }
  // Python datetime str: "2026-10-19 06:10:00+00:00"
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const d = new Date(normalized)
  if (!Number.isNaN(d.getTime())) return d
  const fallback = new Date(raw)
  return Number.isNaN(fallback.getTime()) ? null : fallback
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

/** 发布时间展示：统一按北京时间到分钟 */
export function formatDateTimeMinute(value) {
  if (value == null || value === '') return '—'
  const raw = String(value).trim()
  const wall = BEIJING_WALL.exec(raw)
  if (wall && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(raw)) {
    return `${wall[1]} ${wall[2]}`
  }
  const d = parseDate(value)
  if (!d) return raw || '—'
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const get = (type) => parts.find((p) => p.type === type)?.value || '00'
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`
}

/** 列表预览：去掉 Markdown 标记，压成一行纯文本 */
export function plainAbstract(value, maxLen = 160) {
  let text = String(value || '')
  if (!text) return ''
  text = text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
  if (text.length <= maxLen) return text
  return `${text.slice(0, maxLen - 1)}…`
}

/** 相对时间（监控等场景） */
export function formatTime(value) {
  const d = parseDate(value)
  if (!d) return value ? String(value) : '—'
  const diff = Date.now() - d.getTime()
  if (diff < 0) return formatDateTimeMinute(d)
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days <= 7) return `${days} 天前`
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
