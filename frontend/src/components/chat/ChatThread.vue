<template>
  <div class="thread" ref="root">
    <div v-if="!messages.length" class="welcome">
      <div class="welcome-mark">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" />
          <path d="M9 11h6M9 15h4" />
        </svg>
      </div>
      <h3>你好，我是医药情报助手</h3>
      <p>试试这些问题，或者提出你自己的：</p>
      <div class="row suggestions">
        <button
          v-for="s in suggestions"
          :key="s"
          type="button"
          class="pill suggestion"
          :disabled="loading"
          @click="$emit('suggest', s)"
        >{{ s }}</button>
      </div>
    </div>

    <template v-for="(m, i) in messages" :key="i">
      <div
        v-if="m.role === 'user' || m.content || m.sources?.length || m.error || m.clarify"
        class="msg"
        :class="m.role"
      >
        <div class="bubble" :class="{ clarify: m.clarify }">
          <div v-if="m.clarify && m.role === 'assistant'" class="clarify-tag">需要补充</div>
          <div v-if="m.role === 'user'" class="answer plain">{{ m.content }}</div>
          <div
            v-else-if="m.content"
            class="answer md"
            v-html="renderMarkdown(m.content, m.sources)"
          />

          <div v-if="m.sources?.length" class="sources">
            <div class="sources-head">检索来源</div>
            <div
              v-for="(s, si) in m.sources"
              :id="`cite-${i}-${si + 1}`"
              :key="`${s.id || 's'}-${si}`"
              class="source-card"
            >
              <router-link
                v-if="s.id != null"
                :to="`/news/${s.id}`"
                class="source-main"
              >
                <div class="source-top">
                  <span class="source-id">[{{ si + 1 }}]</span>
                  <span v-if="s.page_context" class="page-badge">本页</span>
                  <span class="source-title">{{ s.title }}</span>
                  <span class="score">{{ (s.score ?? 0).toFixed?.(2) ?? s.score }}</span>
                </div>
                <div class="score-track">
                  <span class="score-fill" :style="{ width: Math.round((s.score || 0) * 100) + '%' }"></span>
                </div>
              </router-link>
              <div v-else class="source-main">
                <div class="source-top">
                  <span class="source-id">[{{ si + 1 }}]</span>
                  <span v-if="s.page_context" class="page-badge">本页</span>
                  <span class="source-title">{{ s.title }}</span>
                  <span class="score">{{ (s.score ?? 0).toFixed?.(2) ?? s.score }}</span>
                </div>
              </div>
              <a
                v-if="s.detail_url"
                class="source-origin"
                :href="s.detail_url"
                target="_blank"
                rel="noopener"
              >原文</a>
            </div>
          </div>

          <div v-if="m.error" class="msg-error">{{ m.error }}</div>

          <div v-if="m.role === 'assistant' && m.content && !loading" class="msg-actions">
            <button type="button" class="ghost" @click="$emit('export', m)">导出报告</button>
          </div>
        </div>
      </div>
    </template>

    <!-- 流式正文已出现后不再叠一层阶段条，避免双框 -->
    <div v-if="showStageBubble" class="msg assistant">
      <div class="bubble thinking">
        <span></span><span></span><span></span>
        <div class="thinking-copy">
          <em>{{ stageLabel }}</em>
          <small v-if="searchQuery">检索：{{ searchQuery }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { marked } from 'marked'
import { computed, nextTick, ref, watch } from 'vue'

marked.setOptions({ breaks: true, gfm: true })

const STAGE_LABELS = {
  intent: '正在识别意图…',
  rewrite: '正在优化问法…',
  clarify: '需要您补充信息…',
  retrieve: '正在检索…',
  rerank: '正在重排与筛选…',
  retry: '原句结果不足，准备优化问法…',
  generate: '正在生成回答…',
}

const props = defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  loadingStage: { type: String, default: '' },
  searchQuery: { type: String, default: '' },
  suggestions: { type: Array, default: () => [] },
})

const stageLabel = computed(() => {
  // 有改写检索词时，retrieve 表示补充检索而非原句
  if (props.loadingStage === 'retrieve' && props.searchQuery) {
    return '正在优化问法并补充检索…'
  }
  if (props.loadingStage === 'rerank' && props.searchQuery) {
    return '正在按优化问法重排筛选…'
  }
  return STAGE_LABELS[props.loadingStage] || '正在处理…'
})

const showStageBubble = computed(() => {
  if (!props.loading) return false
  const last = props.messages[props.messages.length - 1]
  // 已有流式正文时只保留回答气泡，阶段条让位
  if (last?.role === 'assistant' && last.content) return false
  return true
})

defineEmits(['suggest', 'export'])

const root = ref(null)

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

async function scrollDown() {
  await nextTick()
  root.value?.scrollTo({ top: root.value.scrollHeight, behavior: 'smooth' })
}

watch(
  () => [
    props.messages.length,
    props.loading,
    props.messages.map((m) => m.content?.length || 0).join(','),
  ],
  () => { scrollDown() },
)

defineExpose({ scrollDown })
</script>

<style scoped>
.thread {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-2) var(--sp-1) var(--sp-5);
  overflow-y: auto;
  min-height: 0;
  overscroll-behavior: contain;
}
.welcome {
  text-align: center;
  padding: var(--sp-6) var(--sp-4);
  color: var(--ink-soft);
}
.welcome-mark {
  width: 58px; height: 58px;
  margin: 0 auto var(--sp-4);
  border-radius: 50% 50% 50% 8px;
  display: grid; place-items: center;
  color: var(--paper);
  background: var(--pine);
  box-shadow: 0 14px 30px -12px rgba(28, 75, 51, 0.55);
}
.welcome h3 {
  font-family: var(--font-serif);
  font-size: var(--fs-h1);
  color: var(--ink);
  margin-bottom: var(--sp-2);
}
.welcome p { margin: 0 0 var(--sp-4); }
.suggestions { justify-content: center; }
.suggestion { cursor: pointer; }
.suggestion:hover { transform: translateY(-2px); }

.msg { display: flex; animation: msg-in var(--dur-base) var(--ease-spring); }
.msg.user { justify-content: flex-end; }
@keyframes msg-in { from { opacity: 0; transform: translateY(10px); } }

.bubble {
  max-width: min(72ch, 92%);
  border-radius: var(--r-lg);
  padding: var(--sp-4) var(--sp-5);
  line-height: 1.8;
}
.msg.user .bubble {
  background: var(--pine);
  color: var(--paper);
  font-weight: 500;
  border-bottom-right-radius: var(--sp-1);
}
.msg.assistant .bubble {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-bottom-left-radius: var(--sp-1);
  color: var(--ink);
  box-shadow: var(--shadow-sm);
}
.msg.assistant .bubble.clarify {
  border-color: color-mix(in srgb, var(--brass) 45%, var(--rule));
  background: color-mix(in srgb, var(--brass) 8%, var(--surface));
}
.clarify-tag {
  display: inline-block;
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brass, #9a6b2f);
  margin-bottom: 8px;
}
.answer.plain { white-space: pre-wrap; }
.answer.md :deep(p) { margin: 0 0 0.7em; }
.answer.md :deep(p:last-child) { margin-bottom: 0; }
.answer.md :deep(h1),
.answer.md :deep(h2),
.answer.md :deep(h3),
.answer.md :deep(h4) {
  font-family: var(--font-serif);
  font-weight: 700;
  line-height: 1.35;
  margin: 0.9em 0 0.4em;
}
.answer.md :deep(h1:first-child),
.answer.md :deep(h2:first-child),
.answer.md :deep(h3:first-child),
.answer.md :deep(h4:first-child) { margin-top: 0; }
.answer.md :deep(h1) { font-size: 1.2em; }
.answer.md :deep(h2) { font-size: 1.12em; }
.answer.md :deep(h3),
.answer.md :deep(h4) { font-size: 1.05em; }
.answer.md :deep(ul),
.answer.md :deep(ol) {
  margin: 0.35em 0 0.75em;
  padding-left: 1.35em;
}
.answer.md :deep(li) { margin: 0.25em 0; }
.answer.md :deep(ul ul),
.answer.md :deep(ol ol),
.answer.md :deep(ul ol),
.answer.md :deep(ol ul) { margin: 0.2em 0 0.35em; }
.answer.md :deep(strong),
.answer.md :deep(b) { font-weight: 700; }
.answer.md :deep(em),
.answer.md :deep(i) { font-style: italic; }
.answer.md :deep(a) {
  color: var(--pine);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.answer.md :deep(a:hover) { color: var(--moss); }
.answer.md :deep(a.cite-ref) {
  display: inline;
  font-family: var(--font-mono);
  font-size: 0.86em;
  font-weight: 700;
  color: var(--pine);
  background: color-mix(in srgb, var(--lime) 22%, transparent);
  border-radius: 4px;
  padding: 0 0.28em;
  margin: 0 0.08em;
  text-decoration: none;
  white-space: nowrap;
}
.answer.md :deep(a.cite-ref:hover) {
  color: var(--paper);
  background: var(--pine);
}
.answer.md :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.9em;
  background: var(--wash);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.answer.md :deep(pre) {
  margin: 0.6em 0;
  padding: var(--sp-3);
  overflow-x: auto;
  background: var(--wash);
  border-radius: var(--r-sm);
  font-size: 0.88em;
}
.answer.md :deep(pre code) {
  background: none;
  padding: 0;
}
.answer.md :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.2em 0 0.2em 0.9em;
  border-left: 3px solid var(--moss);
  color: var(--ink-soft);
}
.answer.md :deep(hr) {
  border: 0;
  border-top: 1px solid var(--rule);
  margin: 0.9em 0;
}
.answer.md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.7em 0;
  font-size: 0.92em;
}
.answer.md :deep(th),
.answer.md :deep(td) {
  border: 1px solid var(--rule);
  padding: 6px 8px;
  vertical-align: top;
}
.answer.md :deep(th) {
  background: var(--wash);
  font-weight: 700;
}

.sources { margin-top: var(--sp-4); border-top: 1px dashed var(--rule-strong); padding-top: var(--sp-3); }
.sources-head {
  font-size: var(--fs-xs);
  letter-spacing: 0.16em;
  color: var(--ink-mute);
  text-transform: uppercase;
  margin-bottom: var(--sp-2);
}
.source-card {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--r-sm);
}
.source-main {
  flex: 1;
  min-width: 0;
  color: inherit;
  border-radius: var(--r-sm);
  transition: background var(--dur-fast);
}
.source-main:hover { background: var(--wash); }
.source-origin {
  flex: none;
  font-size: var(--fs-xs);
  color: var(--pine);
  font-weight: 700;
  padding-top: 2px;
}
.source-top { display: flex; align-items: baseline; gap: var(--sp-2); font-size: var(--fs-sm); }
.source-id { font-family: var(--font-mono); color: var(--moss); font-size: var(--fs-xs); }
.page-badge {
  flex: none;
  font-size: 10px;
  font-weight: 700;
  padding: 0 5px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--lime) 35%, transparent);
  color: var(--pine);
}
.source-title { flex: 1; min-width: 0; }
.score { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--ink-mute); }
.score-track {
  height: 3px;
  border-radius: 2px;
  background: var(--paper-deep);
  margin-top: 6px;
  overflow: hidden;
}
.score-fill {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--pine), var(--lime));
}

.msg-error { color: var(--clay); font-size: var(--fs-sm); margin-top: var(--sp-2); }
.msg-actions { margin-top: var(--sp-3); display: flex; gap: var(--sp-2); }

.thinking { display: flex; align-items: center; gap: var(--sp-2); color: var(--ink-mute); }
.thinking-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.thinking em { font-style: normal; font-size: var(--fs-sm); }
.thinking small {
  font-size: var(--fs-xs);
  font-family: var(--font-mono);
  color: var(--ink-mute);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 48ch;
}
.thinking span {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--moss);
  animation: bounce 1.2s ease-in-out infinite;
  flex: none;
}
.thinking span:nth-child(2) { animation-delay: 150ms; }
.thinking span:nth-child(3) { animation-delay: 300ms; }
@keyframes bounce { 40% { transform: translateY(-6px); opacity: 0.5; } }

@media (max-width: 900px) {
  .bubble { max-width: 96%; }
}
</style>
