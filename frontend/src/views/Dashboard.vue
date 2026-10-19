<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Overview · 情报全景</div>
      <h1 class="ed-title">今日，医药世界正在发生什么</h1>
      <p class="ed-lede">像翻阅一本每日刊行的医药情报简报。</p>
    </header>

    <!-- 错误提示 -->
    <div v-if="error" class="card empty reveal" style="--reveal-delay:80ms">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.01" />
      </svg>
      <div class="empty-title">暂时无法加载</div>
      <p>请稍后重试。</p>
      <button class="secondary" @click="load">重试</button>
    </div>

    <template v-else>
      <p v-if="!loading && !overview.news_count && session.user?.role === 'admin'" class="card note">
        库里还没有新闻。到 <router-link to="/monitor">系统监控</router-link> 选择爬虫并启动采集。
      </p>
      <!-- 01 数字全景 -->
      <section class="reveal" style="--reveal-delay:100ms">
        <div class="sec-mark"><span class="no">01</span><h3>数字全景</h3><span class="rule"></span></div>
        <div class="grid">
          <template v-if="loading">
            <div v-for="i in 4" :key="i" class="card stat">
              <div class="skeleton" style="width:64px;height:12px"></div>
              <div class="skeleton" style="width:110px;height:44px;margin-top:12px"></div>
            </div>
          </template>
          <template v-else>
            <StatCard v-for="(s, i) in stats" :key="s.label"
              :label="s.label" :value="s.value" :delay="120 + i * 70" />
          </template>
        </div>
      </section>

      <!-- 02 趋势与热词 -->
      <div class="bento">
        <section class="card reveal" style="--reveal-delay:240ms">
          <div class="sec-mark"><span class="no">02</span><h3>新闻趋势 · 近 14 天</h3><span class="rule"></span></div>
          <TrendChart v-if="trend.length" :items="trend" />
          <div v-else-if="loading" class="skeleton" style="height:220px"></div>
          <div v-else class="empty">
            <div class="empty-title">暂无趋势数据</div>
          </div>
        </section>

        <section class="card reveal" style="--reveal-delay:320ms">
          <div class="sec-mark"><span class="no">03</span><h3>热门关键词</h3><span class="rule"></span></div>
          <div class="row" v-if="keywords.length">
            <span
              v-for="k in keywords"
              :key="k.keyword"
              class="pill"
              :style="{ fontSize: keywordSize(k) }"
              :title="`命中 ${k.count} 次`"
            >{{ k.keyword }}<em class="kw-count">{{ k.count }}</em></span>
          </div>
          <div v-else-if="loading" class="skeleton" style="height:40px"></div>
          <div v-else class="empty"><div class="empty-title">暂无关键词命中</div></div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { session } from '../session'
import { useAsync } from '../composables'
import StatCard from '../components/StatCard.vue'
import TrendChart from '../components/TrendChart.vue'

const overview = ref({})
const trend = ref([])
const keywords = ref([])
const { loading, error, run } = useAsync()

const stats = computed(() => {
  const o = overview.value || {}
  return [
    { label: '在库新闻', value: o.news_count ?? 0 },
    { label: '聚合事件', value: o.event_count ?? 0 },
    { label: '已向量化', value: o.news_with_embedding ?? 0 },
    { label: '待聚类', value: o.unassigned_news ?? 0 },
  ]
})

/** 词频映射到 12–18px 字号，形成视觉权重 */
function keywordSize(k) {
  const max = Math.max(...keywords.value.map((x) => x.count || 0), 1)
  const ratio = (k.count || 0) / max
  return `${12 + ratio * 6}px`
}

async function load() {
  const data = await run(() =>
    Promise.all([api.overview(), api.trend(), api.keywords()])
  )
  if (!data) return
  const [o, t, k] = data
  overview.value = o || {}
  trend.value = t || []
  keywords.value = (k || []).slice(0, 18)
}

onMounted(load)
</script>

<style scoped>
.note { margin-bottom: 20px; color: var(--ink-soft); }
.note a { color: var(--pine); font-weight: 700; }
.bento {
  display: grid;
  grid-template-columns: 7fr 5fr;
  gap: 16px;
  margin-top: 16px;
}
.bento > section { align-self: start; }
.kw-count {
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 0.8em;
  color: var(--ink-mute);
  margin-left: 6px;
}
@media (max-width: 900px) {
  .bento { grid-template-columns: 1fr; }
}
</style>
