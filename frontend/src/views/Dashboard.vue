<template>
  <div>
    <h2>仪表盘</h2>
    <div class="grid" style="margin-top:16px">
      <div class="card stat" v-for="s in stats" :key="s.label">
        <div class="label">{{ s.label }}</div>
        <div class="value">{{ s.value }}</div>
      </div>
    </div>
    <div class="card">
      <h3>热门关键词</h3>
      <div class="row" style="margin-top:8px">
        <span v-for="k in keywords" :key="k.keyword" class="meta">
          {{ k.keyword }} ({{ k.count }})
        </span>
      </div>
    </div>
    <div class="card">
      <h3>新闻趋势（近14天）</h3>
      <div v-for="t in trend" :key="t.date" class="list-item">
        <div>{{ t.date }}</div>
        <div class="meta">{{ t.count }} 条</div>
      </div>
      <div v-if="!trend.length" class="meta">暂无趋势数据</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const stats = ref([])
const keywords = ref([])
const trend = ref([])

onMounted(async () => {
  const o = await api.overview()
  stats.value = [
    { label: '新闻数', value: o.news_count },
    { label: '事件数', value: o.event_count },
    { label: '已向量化', value: o.news_with_embedding },
    { label: '未聚类', value: o.unassigned_news },
  ]
  keywords.value = await api.keywords()
  trend.value = await api.trend()
})
</script>
