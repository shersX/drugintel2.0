<template>
  <div class="chat-layout">
    <div v-if="drawerOpen" class="drawer-mask" @click="drawerOpen = false" />

    <ChatSidebar
      :groups="groupedConversations"
      :active-id="conversationId"
      :drawer-open="drawerOpen"
      :logged-in="Boolean(session.user)"
      :busy="loading"
      @new="startNew"
      @select="selectConversation"
      @rename="renameConversation"
      @remove="removeConversation"
      @close-drawer="drawerOpen = false"
      @login="openLoginPrompt('/chat')"
    />

    <div class="chat-main">
      <header class="ed-head mobile-only">
        <button type="button" class="ghost mobile-history" @click="drawerOpen = !drawerOpen">
          历史会话
        </button>
      </header>

      <ChatThread
        ref="threadRef"
        :messages="messages"
        :loading="loading"
        :loading-stage="loadingStage"
        :search-query="activeSearchQuery"
        :suggestions="suggestions"
        @suggest="onSuggest"
        @export="exportReport"
      />

      <ChatComposer v-model="query" :disabled="loading" @submit="send" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { openLoginPrompt } from '../authPrompt'
import ChatComposer from '../components/chat/ChatComposer.vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import ChatThread from '../components/chat/ChatThread.vue'
import { useChatAsk } from '../composables/useChatAsk'
import { session } from '../session'

const route = useRoute()
const router = useRouter()

const query = ref('')
const messages = ref([])
const conversationId = ref('')
const conversations = ref([])
const loading = ref(false)
const loadingStage = ref('')
const activeSearchQuery = ref('')
const drawerOpen = ref(false)
const threadRef = ref(null)

const { askViaWs, askViaRest } = useChatAsk({
  messages,
  conversationId,
  loadingStage,
  activeSearchQuery,
})

const suggestions = [
  '最近有哪些医药新闻？',
  'GLP-1 领域有什么动态？',
  '诺和诺德最近有什么事件？',
]

const groupedConversations = computed(() => groupByTime(conversations.value))

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

function requireLogin() {
  if (session.user) return true
  openLoginPrompt('/chat')
  return false
}

function syncQuery(id) {
  const next = { ...route.query }
  if (id) next.c = id
  else delete next.c
  router.replace({ query: next })
}

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

async function selectConversation(id) {
  if (loading.value || !id) return
  drawerOpen.value = false
  try {
    const detail = await api.conversationDetail(id)
    conversationId.value = detail.id
    messages.value = (detail.messages || []).map((m) => ({
      role: m.role,
      content: m.content,
      sources: m.sources || [],
    }))
    syncQuery(detail.id)
  } catch (e) {
    if (e.status === 401) openLoginPrompt('/chat')
    else if (e.status === 404) {
      conversationId.value = ''
      messages.value = []
      syncQuery('')
      await loadList()
    }
  }
}

function startNew() {
  if (loading.value) return
  conversationId.value = ''
  messages.value = []
  query.value = ''
  drawerOpen.value = false
  syncQuery('')
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

async function removeConversation(item) {
  if (!window.confirm(`删除会话「${item.title || '新对话'}」？`)) return
  try {
    await api.deleteConversation(item.id)
    conversations.value = conversations.value.filter((c) => c.id !== item.id)
    if (conversationId.value === item.id) startNew()
  } catch (e) {
    window.alert(e.message || '删除失败')
  }
}

function onSuggest(text) {
  query.value = text
  send()
}

async function send() {
  const q = query.value.trim()
  if (!q || loading.value) return
  if (!requireLogin()) return
  messages.value.push({ role: 'user', content: q })
  query.value = ''
  loading.value = true
  loadingStage.value = 'intent'
  activeSearchQuery.value = ''
  threadRef.value?.scrollDown?.()
  try {
    let data
    try {
      data = await askViaWs(q)
    } catch (wsErr) {
      // WebSocket 不可用时回退 REST（无阶段动画）
      loadingStage.value = 'retrieve'
      data = await askViaRest(q)
      const cid = data.conversation_id || data.session_id || conversationId.value
      conversationId.value = cid
      messages.value.push({
        role: 'assistant',
        content: data.answer || '（未获取到回答）',
        sources: data.sources || [],
        clarify: Boolean(data.clarify),
      })
      if (data.search_query) activeSearchQuery.value = data.search_query
      syncQuery(cid)
      await loadList()
      return
    }
    const cid = data.conversation_id || conversationId.value
    if (cid) {
      conversationId.value = cid
      syncQuery(cid)
    }
    await loadList()
  } catch (e) {
    if (e.status === 401) {
      messages.value.pop()
      query.value = q
      openLoginPrompt('/chat')
      return
    }
    messages.value.push({
      role: 'assistant',
      content: '',
      error: `回答失败：${e.message}`,
    })
  } finally {
    loading.value = false
    loadingStage.value = ''
    activeSearchQuery.value = ''
    threadRef.value?.scrollDown?.()
  }
}

async function exportReport(m) {
  if (!requireLogin()) return
  const idx = messages.value.indexOf(m)
  const question = idx > 0 ? messages.value[idx - 1]?.content : '报告导出'
  try {
    const data = await api.exportReport({
      question,
      answer: m.content,
      sources: m.sources || [],
      fmt: 'pdf',
    })
    window.open(`/api/reports/download/${data.filename}`, '_blank')
  } catch (e) {
    m.error = `导出失败：${e.message}`
  }
}

onMounted(async () => {
  await loadList()
  const fromQuery = typeof route.query.c === 'string' ? route.query.c : ''
  if (fromQuery && session.user) await selectConversation(fromQuery)
})

watch(
  () => session.user?.id,
  async (id) => {
    if (!id) {
      conversations.value = []
      startNew()
      return
    }
    await loadList()
  },
)
</script>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 0 20px;
  height: calc(100dvh - 148px);
  max-height: calc(100dvh - 148px);
  min-height: 0;
}
.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
}
.ed-head {
  flex: none;
  margin-bottom: 12px;
}
.mobile-only { display: none; }
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(28, 36, 32, 0.35);
}

@media (max-width: 900px) {
  .chat-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .mobile-only { display: block; }
  .mobile-history { display: inline-flex; }
}
</style>
