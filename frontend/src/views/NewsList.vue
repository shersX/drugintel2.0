<template>
  <div>
    <div class="row" style="justify-content:space-between">
      <h2>新闻列表</h2>
      <button class="secondary" @click="load">刷新</button>
    </div>
    <div class="card" v-for="n in items" :key="n.id">
      <router-link :to="`/news/${n.id}`"><strong>{{ n.title }}</strong></router-link>
      <div class="meta">{{ n.source || n.crawler }} · {{ n.publish_time || '-' }}</div>
      <p>{{ n.abstract }}</p>
    </div>
    <div class="row">
      <button class="secondary" :disabled="page<=1" @click="page--; load()">上一页</button>
      <span class="meta">第 {{ page }} 页 / 共 {{ total }} 条</span>
      <button class="secondary" @click="page++; load()">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const items = ref([])
const page = ref(1)
const total = ref(0)

async function load() {
  const data = await api.news(page.value)
  items.value = data.items || []
  total.value = data.total || 0
}
onMounted(load)
</script>
