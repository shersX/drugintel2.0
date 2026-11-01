<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Events · 事件簇</div>
      <p class="meta">按情报风险分排序；点击查看成员时间线。</p>
    </header>

    <div v-if="error" class="card empty">
      <div class="empty-title">加载失败</div>
      <p>{{ error }}</p>
      <button class="secondary" @click="load">重试</button>
    </div>

    <div v-else-if="loading && !items.length" class="card">加载中…</div>

    <div v-else class="event-list">
      <article v-for="e in items" :key="e.id" class="event-card reveal" @click="open(e.id)">
        <div class="event-top">
          <strong>{{ e.title }}</strong>
          <span v-if="e.ci_risk_score != null" class="risk" :title="'情报风险分（非临床 LoA）'">
            {{ Number(e.ci_risk_score).toFixed(2) }}
          </span>
        </div>
        <p class="meta">{{ e.summary || '暂无摘要' }}</p>
        <div class="chips">
          <span v-for="p in (e.products || []).slice(0, 4)" :key="'p'+p" class="pill">{{ p }}</span>
          <span v-for="o in (e.orgs || []).slice(0, 3)" :key="'o'+o" class="pill muted">{{ o }}</span>
          <span v-for="t in (e.story_types || [])" :key="'t'+t" class="pill story">{{ t }}</span>
          <span class="meta">{{ e.news_count }} 篇</span>
        </div>
      </article>
    </div>

    <div v-if="detail" class="drawer card">
      <header>
        <h3>{{ detail.title }}</h3>
        <button class="secondary" @click="detail = null">关闭</button>
      </header>
      <p class="meta">
        风险分 {{ detail.ci_risk_score ?? '—' }}
        · {{ detail.disclaimer }}
      </p>
      <ol class="timeline">
        <li v-for="m in detail.timeline || []" :key="m.id">
          <router-link :to="`/news/${m.id}`">{{ m.title }}</router-link>
          <span class="meta">{{ m.publish_time || '时间未知' }} · {{ m.story_type || 'other' }}</span>
        </li>
      </ol>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'

const items = ref([])
const detail = ref(null)
const { loading, error, run } = useAsync()

async function load() {
  await run(async () => {
    const data = await api.events(1)
    items.value = data.items || []
  })
}

async function open(id) {
  detail.value = await api.eventDetail(id)
}

onMounted(load)
</script>

<style scoped>
.event-list { display: grid; gap: 12px; }
.event-card {
  padding: 16px 18px; border: 1px solid var(--border, #e5e7eb); border-radius: 10px; cursor: pointer;
}
.event-top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.risk {
  font-variant-numeric: tabular-nums; font-weight: 700; background: #111; color: #fff;
  border-radius: 999px; padding: 2px 10px; font-size: 12px;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; align-items: center; }
.pill { background: #eef2ff; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.pill.muted { background: #f3f4f6; }
.pill.story { background: #ecfeff; }
.drawer { margin-top: 20px; }
.timeline { padding-left: 18px; }
.timeline li { margin: 8px 0; }
</style>
