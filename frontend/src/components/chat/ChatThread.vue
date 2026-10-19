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
      <div class="msg" :class="m.role">
        <div class="bubble">
          <div v-if="m.role === 'user'" class="answer">{{ m.content }}</div>
          <div v-else-if="m.content" class="answer">{{ m.content }}</div>

          <div v-if="m.sources?.length" class="sources">
            <div class="sources-head">检索来源</div>
            <div v-for="s in m.sources" :key="s.id" class="source-card">
              <router-link :to="`/news/${s.id}`" class="source-main">
                <div class="source-top">
                  <span class="source-id">[#{{ s.id }}]</span>
                  <span class="source-title">{{ s.title }}</span>
                  <span class="score">{{ (s.score ?? 0).toFixed?.(2) ?? s.score }}</span>
                </div>
                <div class="score-track">
                  <span class="score-fill" :style="{ width: Math.round((s.score || 0) * 100) + '%' }"></span>
                </div>
              </router-link>
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

          <div v-if="m.role === 'assistant' && m.content" class="msg-actions">
            <button type="button" class="ghost" @click="$emit('export', m)">导出报告</button>
          </div>
        </div>
      </div>
    </template>

    <div v-if="loading" class="msg assistant">
      <div class="bubble thinking">
        <span></span><span></span><span></span>
        <em>正在检索情报库…</em>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  suggestions: { type: Array, default: () => [] },
})

defineEmits(['suggest', 'export'])

const root = ref(null)

async function scrollDown() {
  await nextTick()
  root.value?.scrollTo({ top: root.value.scrollHeight, behavior: 'smooth' })
}

watch(() => [props.messages.length, props.loading], () => { scrollDown() })

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

@media (max-width: 900px) {
  .bubble { max-width: 96%; }
}
</style>
