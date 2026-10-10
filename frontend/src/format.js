/** 时间与来源展示工具 */

const CRAWLER_LABELS = {
  bioon: '生物谷',
  globenewswire: 'GlobeNewswire',
  prnewswire: 'PR Newswire',
}

export function crawlerLabel(crawler) {
  if (!crawler) return '未知来源'
  return CRAWLER_LABELS[String(crawler).toLowerCase()] || crawler
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
