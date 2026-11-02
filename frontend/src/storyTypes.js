/** 新闻事件类型：接口仍用英文 value，界面展示中文 label。 */

export const STORY_TYPE_OPTIONS = [
  { value: 'clinical', label: '临床' },
  { value: 'regulatory', label: '监管' },
  { value: 'deal', label: '交易' },
  { value: 'financing', label: '融资' },
  { value: 'pipeline', label: '管线' },
  { value: 'conference', label: '会议' },
  { value: 'safety', label: '安全' },
  { value: 'other', label: '其他' },
]

export function storyTypeLabel(code) {
  if (!code) return ''
  const hit = STORY_TYPE_OPTIONS.find((t) => t.value === String(code).toLowerCase())
  return hit?.label || String(code)
}
