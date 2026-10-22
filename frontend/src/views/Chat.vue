<template>
  <div class="chat-layout">
    <div class="chat-main-inner">
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
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { openLoginPrompt } from '../authPrompt'
import ChatComposer from '../components/chat/ChatComposer.vue'
import ChatThread from '../components/chat/ChatThread.vue'
import { useChatAsk } from '../composables/useChatAsk'
import { useChatSessions } from '../composables/useChatSessions'
import { session } from '../session'

const route = useRoute()
const router = useRouter()

const query = ref('')
const messages = ref([])
const loading = ref(false)
const loadingStage = ref('')
const activeSearchQuery = ref('')
const threadRef = ref(null)

const {
  conversationId,
  asking,
  selectTick,
  clearTick,
  loadList,
  syncQuery,
  requireLogin,
} = useChatSessions()

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

async function loadConversationDetail(id) {
  if (!id) {
    messages.value = []
    return
  }
  try {
    const detail = await api.conversationDetail(id)
    conversationId.value = detail.id
    messages.value = (detail.messages || []).map((m) => ({
      role: m.role,
      content: m.content,
      sources: m.sources || [],
    }))
  } catch (e) {
    if (e.status === 401) openLoginPrompt('/chat')
    else if (e.status === 404) {
      conversationId.value = ''
      messages.value = []
      syncQuery(router, route, '')
      await loadList()
    }
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
  asking.value = true
  loadingStage.value = 'intent'
  activeSearchQuery.value = ''
  threadRef.value?.scrollDown?.()
  try {
    let data
    try {
      data = await askViaWs(q)
    } catch (wsErr) {
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
      syncQuery(router, route, cid)
      await loadList()
      return
    }
    const cid = data.conversation_id || conversationId.value
    if (cid) {
      conversationId.value = cid
      syncQuery(router, route, cid)
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
    asking.value = false
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

watch(selectTick, async () => {
  const id = conversationId.value
  if (id) await loadConversationDetail(id)
})

watch(clearTick, () => {
  messages.value = []
  query.value = ''
})

watch(
  () => route.query.c,
  async (c) => {
    const id = typeof c === 'string' ? c : ''
    if (!id) {
      conversationId.value = ''
      messages.value = []
      query.value = ''
      return
    }
    if (id !== conversationId.value && session.user) {
      conversationId.value = id
      await loadConversationDetail(id)
    }
  },
)

onMounted(async () => {
  await loadList()
  const fromQuery = typeof route.query.c === 'string' ? route.query.c : ''
  if (fromQuery && session.user) {
    conversationId.value = fromQuery
    await loadConversationDetail(fromQuery)
  } else if (!fromQuery) {
    messages.value = []
  }
})

watch(
  () => session.user?.id,
  async (id) => {
    if (!id) {
      messages.value = []
      conversationId.value = ''
      await loadList()
      return
    }
    await loadList()
  },
)
</script>

<style scoped>
.chat-layout {
  height: calc(100dvh - 148px);
  max-height: calc(100dvh - 148px);
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.chat-main-inner {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}
</style>
