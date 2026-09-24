<template>
  <div v-if="news">
    <h2>{{ news.title }}</h2>
    <div class="meta" style="margin:8px 0 16px">
      {{ news.source || news.crawler }} · {{ news.publish_time || '-' }}
      <a v-if="news.detail_url" :href="news.detail_url" target="_blank">原文</a>
    </div>
    <div class="card">
      <h3>摘要</h3>
      <p>{{ news.abstract }}</p>
    </div>
    <div class="card">
      <h3>正文</h3>
      <p style="white-space:pre-wrap">{{ news.content }}</p>
    </div>
    <div class="card" v-if="news.related_news?.length">
      <h3>同事件簇</h3>
      <div v-for="r in news.related_news" :key="r.id" class="list-item">
        <router-link :to="`/news/${r.id}`">{{ r.title }}</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({ id: { type: [String, Number], required: true } })
const news = ref(null)

async function load() {
  news.value = await api.newsDetail(props.id)
}
onMounted(load)
watch(() => props.id, load)
</script>
