<template>
  <div class="page-chat" :class="{ open }">
    <Transition name="panel">
      <div v-if="open" class="panel" role="dialog" aria-label="页面问答">
        <header class="panel-head">
          <div class="panel-titles">
            <strong>AI 问答</strong>
            <small v-if="pageNewsId">结合本页新闻提问</small>
            <small v-else>全库情报问答</small>
          </div>
          <div class="panel-actions">
            <button type="button" class="ghost icon-btn" title="新对话" :disabled="loading" @click="resetChat">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <button type="button" class="ghost icon-btn" title="关闭" @click="open = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
        </header>

        <div class="panel-body" ref="bodyRef">
          <div v-if="!messages.length" class="empty-hint">
            <p v-if="pageNewsId">可以问：这篇文章讲了什么？有哪些关键结论？</p>
            <p v-else>试试：最近有哪些 GLP-1 相关进展？</p>
          </div>

          <div
            v-for="(m, i) in messages"
            :key="i"
            class="msg"
            :class="m.role"
          >
            <div class="bubble" :class="{ clarify: m.clarify, error: m.error }">
              <div v-if="m.clarify" class="tag">需要补充</div>
              <div v-if="m.error" class="err">{{ m.error }}</div>
              <div v-else-if="m.role === 'user'" class="text">{{ m.content }}</div>
              <div
                v-else
                class="text md"
                v-html="renderMarkdown(m.content, m.sources)"
              />
              <div v-if="m.sources?.length" class="src-list">
                <span class="src-label">来源</span>
                <a
                  v-for="(s, si) in m.sources"
                  :key="`${s.id}-${si}`"
                  class="src"
                  :class="{ page: s.page_context }"
                  :href="s.id != null ? `/news/${s.id}` : (s.detail_url || '#')"
                  :target="s.id != null ? '_self' : '_blank'"
                  rel="noopener"
                  :title="s.title"
                >
                  <span v-if="s.page_context" class="badge">本页</span>
                  <span v-else class="src-num">{{ si + 1 }}</span>
                  <span class="src-title">{{ shortTitle(s.title) }}</span>
                </a>
              </div>
            </div>
          </div>

          <div v-if="showStage" class="msg assistant">
            <div class="bubble thinking">
              <span></span><span></span><span></span>
              <em>{{ stageLabel }}</em>
            </div>
          </div>
        </div>

        <form class="panel-foot" @submit.prevent="send">
          <input
            v-model="query"
            :disabled="loading"
            :placeholder="pageNewsId ? '基于本页提问…' : '输入问题…'"
            aria-label="输入问题"
          />
          <button type="submit" :disabled="loading || !query.trim()">发送</button>
        </form>
      </div>
    </Transition>

    <button
      type="button"
      class="fab"
      :aria-expanded="open"
      :title="open ? '收起问答' : '打开问答'"
      @click="toggle"
    >
      <svg v-if="!open" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" />
        <path d="M9 11h6M9 15h4" />
      </svg>
      <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { marked } from 'marked'
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { openLoginPrompt } from '../../authPrompt'
import { useChatAsk } from '../../composables/useChatAsk'
import { session } from '../../session'

marked.setOptions({ breaks: true, gfm: true })

const CID_KEY = 'drugintel.pageChat.cid'
const MSGS_KEY = 'drugintel.pageChat.msgs'

const STAGE_LABELS = {
  intent: '正在识别意图…',
  rewrite: '正在优化问法…',
  clarify: '需要您补充信息…',
  retrieve: '正在检索…',
  rerank: '正在重排与筛选…',
  retry: '正在补充检索…',
  generate: '正在生成回答…',
}

const route = useRoute()
const open = ref(false)
const query = ref('')
const messages = ref(loadMsgs())
const conversationId = ref(sessionStorage.getItem(CID_KEY) || '')
const loading = ref(false)
const loadingStage = ref('')
const activeSearchQuery = ref('')
const bodyRef = ref(null)

const pageNewsId = computed(() => {
  const m = route.path.match(/^\/news\/(\d+)/)
  return m ? Number(m[1]) : null
})

const { askViaWs, askViaRest } = useChatAsk({
  messages,
  conversationId,
  loadingStage,
  activeSearchQuery,
  getNewsId: () => pageNewsId.value,
})

const showStage = computed(() => {
  if (!loading.value) return false
  const last = messages.value[messages.value.length - 1]
  if (last?.role === 'assistant' && last.content) return false
  return true
})

const stageLabel = computed(() => STAGE_LABELS[loadingStage.value] || '正在处理…')

function escapeAttr(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function linkCitations(html, sources) {
  if (!sources?.length) return html
  return html.replace(/\[(\d+)\]/g, (match, num) => {
    const idx = Number(num) - 1
    const source = sources[idx]
    if (!source) return match
    const title = escapeAttr(source.title || `来源 ${num}`)
    if (source.id != null && source.id !== '') {
      return `<a class="cite-ref" href="/news/${source.id}" title="${title}" target="_blank" rel="noopener noreferrer">[${num}]</a>`
    }
    if (source.detail_url) {
      return `<a class="cite-ref" href="${escapeAttr(source.detail_url)}" title="${title}" target="_blank" rel="noopener noreferrer">[${num}]</a>`
    }
    return match
  })
}

function renderMarkdown(text, sources = []) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const html = marked.parse(raw, { async: false })
  return linkCitations(html, sources)
}

function shortTitle(title, max = 22) {
  const t = String(title || '').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max)}…`
}

function loadMsgs() {
  try {
    const raw = sessionStorage.getItem(MSGS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function persist() {
  try {
    if (conversationId.value) sessionStorage.setItem(CID_KEY, conversationId.value)
    else sessionStorage.removeItem(CID_KEY)
    sessionStorage.setItem(MSGS_KEY, JSON.stringify(messages.value.slice(-40)))
  } catch {
    /* ignore quota */
  }
}

watch([messages, conversationId], () => persist(), { deep: true })

async function scrollDown() {
  await nextTick()
  if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
}

watch(
  () => [messages.value.length, loading.value, messages.value.map((m) => m.content?.length || 0).join(',')],
  () => { if (open.value) scrollDown() },
)

function toggle() {
  open.value = !open.value
  if (open.value) scrollDown()
}

function resetChat() {
  if (loading.value) return
  conversationId.value = ''
  messages.value = []
  query.value = ''
  sessionStorage.removeItem(CID_KEY)
  sessionStorage.removeItem(MSGS_KEY)
}

function requireLogin() {
  if (session.user) return true
  openLoginPrompt(route.fullPath || '/')
  return false
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
  scrollDown()
  try {
    let data
    try {
      data = await askViaWs(q)
    } catch {
      loadingStage.value = 'retrieve'
      data = await askViaRest(q)
      const cid = data.conversation_id || data.session_id || conversationId.value
      if (cid) conversationId.value = cid
      messages.value.push({
        role: 'assistant',
        content: data.answer || '（未获取到回答）',
        sources: data.sources || [],
        clarify: Boolean(data.clarify),
      })
      return
    }
    const cid = data.conversation_id || conversationId.value
    if (cid) conversationId.value = cid
  } catch (e) {
    if (e.status === 401) {
      messages.value.pop()
      query.value = q
      openLoginPrompt(route.fullPath || '/')
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
    scrollDown()
  }
}
</script>

<style scoped>
.page-chat {
  position: fixed;
  right: 1.25rem;
  bottom: 1.25rem;
  z-index: 45;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  pointer-events: none;
}
.page-chat > * { pointer-events: auto; }

.fab {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: var(--paper);
  background: var(--pine);
  box-shadow: 0 12px 28px -10px rgba(28, 75, 51, 0.55);
  transition: transform var(--dur-fast), background var(--dur-fast);
}
.fab:hover {
  transform: translateY(-2px) scale(1.04);
  background: var(--moss);
}

.panel {
  width: min(360px, calc(100vw - 2rem));
  height: min(480px, calc(100dvh - 7rem));
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r-lg);
  box-shadow: 0 20px 48px -18px rgba(28, 36, 32, 0.45);
  overflow: hidden;
}

.panel-head {
  flex: none;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--rule);
  background: color-mix(in srgb, var(--wash) 70%, var(--surface));
}
.panel-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.panel-titles strong {
  font-family: var(--font-serif);
  font-size: var(--fs-md);
  color: var(--ink);
}
.panel-titles small {
  font-size: var(--fs-xs);
  color: var(--ink-mute);
}
.panel-actions { display: flex; gap: 2px; }
.icon-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  display: grid;
  place-items: center;
  border-radius: 8px;
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.empty-hint {
  margin: auto;
  text-align: center;
  color: var(--ink-mute);
  font-size: var(--fs-sm);
  padding: 1rem;
}
.empty-hint p { margin: 0; }

.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.bubble {
  max-width: 92%;
  padding: 8px 12px;
  border-radius: 14px;
  font-size: var(--fs-sm);
  line-height: 1.55;
}
.msg.user .bubble {
  background: var(--pine);
  color: var(--paper);
  border-bottom-right-radius: 4px;
}
.msg.assistant .bubble {
  background: var(--wash);
  border: 1px solid var(--rule);
  color: var(--ink);
  border-bottom-left-radius: 4px;
}
.bubble.clarify {
  border-color: color-mix(in srgb, var(--brass) 45%, var(--rule));
  background: color-mix(in srgb, var(--brass) 8%, var(--surface));
}
.tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--brass, #9a6b2f);
  margin-bottom: 4px;
}
.text { white-space: pre-wrap; word-break: break-word; }
.text.md { white-space: normal; }
.text.md :deep(p) { margin: 0 0 0.45em; }
.text.md :deep(p:last-child),
.text.md :deep(*:last-child) { margin-bottom: 0; }
.text.md :deep(ul),
.text.md :deep(ol) {
  margin: 0.25em 0 0.55em;
  padding-left: 1.2em;
}
.text.md :deep(li) { margin: 0.15em 0; }
.text.md :deep(strong),
.text.md :deep(b) { font-weight: 700; }
.text.md :deep(a) {
  color: var(--pine);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.text.md :deep(a.cite-ref) {
  display: inline;
  font-family: var(--font-mono);
  font-size: 0.86em;
  font-weight: 700;
  color: var(--pine);
  background: color-mix(in srgb, var(--lime) 22%, transparent);
  border-radius: 4px;
  padding: 0 0.22em;
  margin: 0 0.06em;
  text-decoration: none;
  white-space: nowrap;
}
.text.md :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.9em;
  background: var(--surface);
  padding: 0.08em 0.28em;
  border-radius: 3px;
}
.text.md :deep(pre) {
  margin: 0.45em 0;
  padding: 8px;
  overflow-x: auto;
  background: var(--surface);
  border-radius: 6px;
  font-size: 0.86em;
}
.text.md :deep(pre code) { background: none; padding: 0; }
.err { color: var(--clay); }
.src-list {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
  border-top: 1px dashed var(--rule);
  padding-top: 5px;
  line-height: 1.2;
}
.src-label {
  flex: none;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--ink-mute);
  text-transform: uppercase;
}
.src {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 100%;
  font-size: 11px;
  color: var(--pine);
  text-decoration: none;
  padding: 1px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--lime) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--pine) 12%, var(--rule));
}
.src:hover { background: color-mix(in srgb, var(--lime) 28%, transparent); }
.src.page { font-weight: 650; }
.src-num {
  font-family: var(--font-mono);
  font-size: 10px;
  opacity: 0.85;
}
.src-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 14ch;
}
.badge {
  flex: none;
  font-size: 10px;
  padding: 0 4px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--lime) 40%, transparent);
  color: var(--pine);
}

.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-mute);
}
.thinking em { font-style: normal; font-size: var(--fs-xs); }
.thinking span {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--moss);
  animation: bounce 1.2s ease-in-out infinite;
}
.thinking span:nth-child(2) { animation-delay: 150ms; }
.thinking span:nth-child(3) { animation-delay: 300ms; }
@keyframes bounce { 40% { transform: translateY(-5px); opacity: 0.5; } }

.panel-foot {
  flex: none;
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--rule);
}
.panel-foot input {
  flex: 1;
  min-width: 0;
  font-size: var(--fs-sm);
  padding: 8px 10px;
}
.panel-foot button {
  flex: none;
  padding: 8px 12px;
  font-size: var(--fs-sm);
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}

@media (max-width: 480px) {
  .page-chat {
    right: 0.85rem;
    bottom: 0.85rem;
  }
  .panel {
    width: min(100vw - 1.5rem, 360px);
    height: min(70dvh, 480px);
  }
}
</style>
