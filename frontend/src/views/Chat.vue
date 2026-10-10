<template>
  <div class="chat">
    <header class="ed-head reveal">
      <div class="ed-kicker">RAG Assistant · 编辑部问答</div>
      <h1 class="ed-title">智慧问答</h1>
      <p class="ed-lede">基于在库情报的检索增强问答，支持多轮追问与来源追溯。</p>
    </header>

    <!-- 对话区 -->
    <div class="thread" ref="threadEl">
      <!-- 欢迎态 -->
      <div v-if="!messages.length" class="welcome reveal">
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
          <button v-for="s in suggestions" :key="s" class="pill suggestion" @click="query = s; send()">
            {{ s }}
          </button>
        </div>
      </div>

      <!-- 消息 -->
      <template v-for="(m, i) in messages" :key="i">
        <div class="msg" :class="m.role">
          <div class="bubble">
            <div v-if="m.role === 'assistant'" class="answer">{{ m.content }}</div>

            <!-- 来源卡片 -->
            <div v-if="m.sources?.length" class="sources">
              <div class="sources-head">检索来源</div>
              <a
                v-for="s in m.sources"
                :key="s.id"
                :href="s.detail_url || `/news/${s.id}`"
                target="_blank"
                rel="noopener"
                class="source-card"
              >
                <div class="source-top">
                  <span class="source-id">[#{{ s.id }}]</span>
                  <span class="source-title">{{ s.title }}</span>
                  <span class="score">{{ (s.score ?? 0).toFixed?.(2) ?? s.score }}</span>
                </div>
                <div class="score-track">
                  <span class="score-fill" :style="{ width: Math.round((s.score || 0) * 100) + '%' }"></span>
                </div>
              </a>
            </div>

            <div v-if="m.error" class="msg-error">{{ m.error }}</div>

            <div v-if="m.role === 'assistant' && m.content" class="msg-actions">
              <button class="ghost" @click="exportReport(m)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.8" stroke-linecap="round">
                  <path d="M12 3v12M7 10l5 5 5-5" /><path d="M4 21h16" />
                </svg>
                导出报告
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- 思考指示 -->
      <div v-if="loading" class="msg assistant">
        <div class="bubble thinking">
          <span></span><span></span><span></span>
          <em>正在检索情报库…</em>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <form class="composer reveal" @submit.prevent="send">
      <input
        v-model="query"
        :disabled="loading"
        placeholder="例如：最近有哪些 GLP-1 相关的临床进展？"
        aria-label="输入问题"
      />
      <button type="submit" :disabled="loading || !query.trim()">发送</button>
      <button type="button" class="secondary" v-if="messages.length" @click="reset" title="清空对话">
        新对话
      </button>
    </form>
    <div class="meta session-line" v-if="sessionId">会话 {{ sessionId }}</div>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { api } from '../api'

const query = ref('')
const messages = ref([])
const sessionId = ref('')
const loading = ref(false)
const threadEl = ref(null)

const suggestions = [
  '最近有哪些医药新闻？',
  'GLP-1 领域有什么动态？',
  '诺和诺德最近有什么事件？',
]

async function scrollDown() {
  await nextTick()
  threadEl.value?.scrollTo({ top: threadEl.value.scrollHeight, behavior: 'smooth' })
}

async function send() {
  const q = query.value.trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', content: q })
  query.value = ''
  loading.value = true
  await scrollDown()
  try {
    const data = await api.ask({ query: q, session_id: sessionId.value || null, top_k: 5 })
    sessionId.value = data.session_id || sessionId.value
    messages.value.push({
      role: 'assistant',
      content: data.answer || '（未获取到回答）',
      sources: data.sources || [],
    })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '',
      error: `回答失败：${e.message}`,
    })
  } finally {
    loading.value = false
    await scrollDown()
  }
}

function reset() {
  messages.value = []
  sessionId.value = ''
  query.value = ''
}

async function exportReport(m) {
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
</script>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 300px);
  min-height: 440px;
}

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
  padding: var(--sp-8) var(--sp-4);
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
.answer { white-space: pre-wrap; }

.sources { margin-top: var(--sp-4); border-top: 1px dashed var(--rule-strong); padding-top: var(--sp-3); }
.sources-head {
  font-size: var(--fs-xs);
  letter-spacing: 0.16em;
  color: var(--ink-mute);
  text-transform: uppercase;
  margin-bottom: var(--sp-2);
}
.source-card {
  display: block;
  color: inherit;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--r-sm);
  transition: background var(--dur-fast);
}
.source-card:hover { background: var(--wash); }
.source-top { display: flex; align-items: baseline; gap: var(--sp-2); font-size: var(--fs-sm); }
.source-id { font-family: var(--font-mono); color: var(--moss); font-size: var(--fs-xs); }
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
  transition: width var(--dur-slow) var(--ease-out);
}

.msg-error { color: var(--clay); font-size: var(--fs-sm); margin-top: var(--sp-2); }
.msg-actions { margin-top: var(--sp-3); display: flex; gap: var(--sp-2); }

.thinking { display: flex; align-items: center; gap: var(--sp-2); color: var(--ink-mute); }
.thinking em { font-style: normal; font-size: var(--fs-sm); }
.thinking span {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--moss);
  animation: bounce 1.2s ease-in-out infinite;
}
.thinking span:nth-child(2) { animation-delay: 150ms; }
.thinking span:nth-child(3) { animation-delay: 300ms; }
@keyframes bounce { 40% { transform: translateY(-6px); opacity: 0.5; } }

.composer {
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-4) 0 var(--sp-2);
  flex: none;
}
.composer input { flex: 1; }
.session-line { margin-top: var(--sp-2); font-family: var(--font-mono); }

@media (max-width: 900px) {
  .bubble { max-width: 96%; }
}
</style>
