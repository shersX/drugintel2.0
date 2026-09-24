<template>
  <div>
    <h2>智慧问答</h2>
    <div class="card chat-box">{{ answer || '在下方输入问题，支持多轮会话。' }}</div>
    <div class="card" v-if="sources.length">
      <h3>来源</h3>
      <div v-for="s in sources" :key="s.id" class="list-item">
        <div>[{{ s.id }}] {{ s.title }}</div>
        <div class="meta">score={{ s.score?.toFixed?.(3) ?? s.score }}</div>
      </div>
    </div>
    <div class="row">
      <input v-model="query" style="flex:1" placeholder="例如：最近有哪些医药新闻？" @keyup.enter="send" />
      <button @click="send" :disabled="loading">发送</button>
      <button class="secondary" @click="exportPdf" :disabled="!answer">导出 PDF</button>
    </div>
    <div class="meta" style="margin-top:8px">session: {{ sessionId || '-' }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'

const query = ref('')
const answer = ref('')
const sources = ref([])
const sessionId = ref('')
const loading = ref(false)
let lastQuestion = ''

async function send() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  lastQuestion = query.value.trim()
  try {
    const data = await api.ask({
      query: lastQuestion,
      session_id: sessionId.value || null,
      top_k: 5,
    })
    answer.value = data.answer
    sources.value = data.sources || []
    sessionId.value = data.session_id
    query.value = ''
  } catch (e) {
    answer.value = `错误：${e.message}`
  } finally {
    loading.value = false
  }
}

async function exportPdf() {
  const data = await api.exportReport({
    question: lastQuestion || '问答导出',
    answer: answer.value,
    sources: sources.value,
    fmt: 'pdf',
  })
  window.open(`/api/reports/download/${data.filename}`, '_blank')
}
</script>
