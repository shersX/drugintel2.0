import { computed, ref } from 'vue'
import { api } from '../api'
import { openLoginPrompt } from '../authPrompt'
import { session } from '../session'

const conversations = ref([])
const conversationId = ref('')
/** Chat 页提问中：侧栏禁用切换 */
const asking = ref(false)
/** 选会话后递增，Chat 页拉取详情 */
const selectTick = ref(0)
/** 新对话清空信号 */
const clearTick = ref(0)

function startOfDay(d) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

function groupByTime(items) {
  const now = startOfDay(new Date())
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const week = new Date(now)
  week.setDate(week.getDate() - 7)

  const buckets = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '近 7 天', items: [] },
    { label: '更早', items: [] },
  ]
  for (const item of items) {
    const t = startOfDay(new Date(item.updated_at || item.created_at || Date.now()))
    if (t.getTime() === now.getTime()) buckets[0].items.push(item)
    else if (t.getTime() === yesterday.getTime()) buckets[1].items.push(item)
    else if (t >= week) buckets[2].items.push(item)
    else buckets[3].items.push(item)
  }
  return buckets.filter((b) => b.items.length)
}

const groupedConversations = computed(() => groupByTime(conversations.value))

export function useChatSessions() {
  async function loadList() {
    if (!session.user) {
      conversations.value = []
      return
    }
    try {
      conversations.value = await api.conversations()
    } catch (e) {
      if (e.status === 401) conversations.value = []
      else console.warn(e)
    }
  }

  function syncQuery(router, route, id) {
    const next = { ...route.query }
    if (id) next.c = id
    else delete next.c
    router.replace({ path: '/chat', query: next })
  }

  function startNew(router, route) {
    if (asking.value) return
    conversationId.value = ''
    clearTick.value += 1
    syncQuery(router, route, '')
  }

  async function selectConversation(router, route, id) {
    if (asking.value || !id) return
    if (conversationId.value === id) {
      selectTick.value += 1
      return
    }
    conversationId.value = id
    selectTick.value += 1
    syncQuery(router, route, id)
  }

  async function renameConversation(item) {
    const title = window.prompt('重命名会话', item.title || '')
    if (title == null) return
    const cleaned = title.trim()
    if (!cleaned) return
    try {
      const row = await api.renameConversation(item.id, cleaned)
      const idx = conversations.value.findIndex((c) => c.id === item.id)
      if (idx >= 0) conversations.value[idx] = { ...conversations.value[idx], ...row }
    } catch (e) {
      window.alert(e.message || '重命名失败')
    }
  }

  async function removeConversation(router, route, item) {
    if (!window.confirm(`删除会话「${item.title || '新对话'}」？`)) return
    try {
      await api.deleteConversation(item.id)
      conversations.value = conversations.value.filter((c) => c.id !== item.id)
      if (conversationId.value === item.id) startNew(router, route)
    } catch (e) {
      window.alert(e.message || '删除失败')
    }
  }

  function requireLogin() {
    if (session.user) return true
    openLoginPrompt('/chat')
    return false
  }

  return {
    conversations,
    conversationId,
    asking,
    selectTick,
    clearTick,
    groupedConversations,
    loadList,
    syncQuery,
    startNew,
    selectConversation,
    renameConversation,
    removeConversation,
    requireLogin,
  }
}
