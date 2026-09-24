<template>
  <div>
    <h2>系统监控</h2>
    <div class="card">
      <h3>健康检查</h3>
      <pre>{{ JSON.stringify(health, null, 2) }}</pre>
    </div>
    <div class="card">
      <h3>处理状态</h3>
      <pre>{{ JSON.stringify(processing, null, 2) }}</pre>
    </div>
    <div class="card">
      <h3>爬虫任务</h3>
      <div v-for="t in tasks" :key="t.id" class="list-item">
        <div>{{ t.crawler_name }} · {{ t.status }}</div>
        <div class="meta">success={{ t.success_count }}/{{ t.total_count }} · {{ t.end_time }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const health = ref({})
const processing = ref({})
const tasks = ref([])

onMounted(async () => {
  const data = await api.monitor()
  health.value = data.health || {}
  processing.value = data.processing || {}
  tasks.value = data.crawler_tasks || []
})
</script>
