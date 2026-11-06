<template>
  <div class="events-page">
    <header class="ed-head reveal">
      <div class="ed-kicker">Events · 事件簇</div>
      <p class="meta">按情报风险分排序；点击打开右侧研报抽屉。</p>
    </header>

    <div v-if="error" class="card empty">
      <div class="empty-title">加载失败</div>
      <p>{{ error }}</p>
      <button class="secondary" @click="load">重试</button>
    </div>

    <div v-else-if="loading && !items.length" class="card">加载中…</div>

    <div v-else class="event-list">
      <article
        v-for="e in items"
        :key="e.id"
        class="event-card reveal"
        :class="{ active: selectedId === e.id }"
        @click="open(e.id)"
      >
        <div class="event-top">
          <strong>{{ e.title }}</strong>
          <span v-if="e.ci_risk_score != null" class="risk" title="情报风险分（非临床 LoA）">
            {{ Number(e.ci_risk_score).toFixed(2) }}
          </span>
        </div>
        <p class="meta clamp">{{ e.summary || '暂无摘要' }}</p>
        <div class="chips">
          <span v-for="p in (e.products || []).slice(0, 4)" :key="'p'+p" class="pill">{{ p }}</span>
          <span v-for="o in (e.orgs || []).slice(0, 3)" :key="'o'+o" class="pill muted">{{ o }}</span>
          <span v-for="t in (e.story_types || [])" :key="'t'+t" class="pill story">{{ t }}</span>
          <span class="meta">{{ e.news_count }} 篇</span>
        </div>
      </article>
    </div>

    <Teleport to="body">
      <div
        v-if="drawerOpen"
        class="drawer-mask"
        @click.self="closeDrawer"
      >
        <aside
          class="drawer"
          role="dialog"
          aria-modal="true"
          aria-labelledby="event-drawer-title"
        >
          <header class="drawer-head">
            <div class="head-copy">
              <h3 id="event-drawer-title">{{ detail?.title || '事件详情' }}</h3>
              <p class="meta">
                风险分 {{ detail?.ci_risk_score ?? '—' }}
                · {{ detail?.disclaimer || '情报关注/风险评分，非药物临床成功概率' }}
              </p>
            </div>
            <button type="button" class="ghost drawer-close" @click="closeDrawer">关闭</button>
          </header>

          <div class="drawer-body">
            <div v-if="detailLoading && !detail" class="skel">加载详情…</div>
            <template v-else-if="detail">
              <section class="block forecast">
                <div class="block-head">
                  <h4>预判推演</h4>
                  <button
                    type="button"
                    class="secondary tiny"
                    :disabled="forecastBusy"
                    @click="regenForecast"
                  >
                    {{ forecastBusy ? '生成中…' : '重新生成' }}
                  </button>
                </div>
                <p class="meta tip">
                  <span v-if="reportModeLabel" class="mode-tag">{{ reportModeLabel }}</span>
                  Analyst Agent 异步深度分析（thinking）；非临床 LoA。
                </p>
                <div
                  v-if="forecastBusy || ['queued','running'].includes(detail.forecast_status)"
                  class="skel"
                >
                  深度分析生成中，可能需要数分钟…
                </div>
                <div
                  v-else-if="detail.forecast_report"
                  class="report md"
                  v-html="reportHtml"
                />
                <p v-else-if="detail.forecast_error || detail.forecast_status === 'failed'" class="err">
                  {{ detail.forecast_error || '研报生成失败' }}
                </p>
                <p v-else class="meta">尚未生成研报，将自动排队或点击「重新生成」。</p>
              </section>

              <section class="block">
                <h4>事件摘要</h4>
                <div
                  v-if="detail.summary"
                  class="summary md"
                  v-html="summaryHtml"
                />
                <p v-else class="meta">暂无综合摘要</p>
              </section>

              <section v-if="scoreRows.length" class="block">
                <h4>风险拆解</h4>
                <ul class="score-list">
                  <li v-for="row in scoreRows" :key="row.label">
                    <span>{{ row.label }}</span>
                    <strong>{{ row.value }}</strong>
                  </li>
                </ul>
              </section>

              <section class="block">
                <h4>证据时间线</h4>
                <ol class="timeline">
                  <li v-for="m in detail.timeline || []" :key="m.id">
                    <router-link :to="`/news/${m.id}`" @click.stop>{{ m.title }}</router-link>
                    <span class="meta">
                      {{ m.publish_time || '时间未知' }} · {{ m.story_type || 'other' }}
                      <template v-if="m.is_representative"> · 代表篇</template>
                    </span>
                    <p v-if="m.abstract_snippet" class="snip">{{ m.abstract_snippet }}</p>
                    <div class="chips tight">
                      <span v-for="p in (m.products || []).slice(0, 3)" :key="m.id+'p'+p" class="pill">{{ p }}</span>
                      <span v-for="o in (m.orgs || []).slice(0, 2)" :key="m.id+'o'+o" class="pill muted">{{ o }}</span>
                    </div>
                  </li>
                </ol>
              </section>

              <section v-if="(detail.entity_event_chain || []).length" class="block">
                <h4>同实体事件链</h4>
                <ul class="chain">
                  <li
                    v-for="c in detail.entity_event_chain"
                    :key="c.id"
                    @click="open(c.id)"
                  >
                    <strong>{{ c.title }}</strong>
                    <span class="meta">
                      风险 {{ c.ci_risk_score ?? '—' }} · {{ c.news_count }} 篇
                      · {{ (c.story_types || []).join('/') || 'other' }}
                    </span>
                    <p class="snip">{{ c.summary }}</p>
                  </li>
                </ul>
              </section>
            </template>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { marked } from 'marked'
import { api } from '../api'
import { useAsync } from '../composables'

marked.setOptions({ breaks: true, gfm: true })

const MODE_LABEL = {
  clinical_asset: '临床资产',
  deal_capital: '交易资本',
  general_intel: '一般情报',
}

const items = ref([])
const detail = ref(null)
const selectedId = ref(null)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const forecastBusy = ref(false)
const { loading, error, run } = useAsync()
let pollTimer = 0

const reportHtml = computed(() => {
  const raw = detail.value?.forecast_report || ''
  if (!raw) return ''
  return marked.parse(raw, { async: false })
})

const summaryHtml = computed(() => {
  const raw = detail.value?.summary || ''
  if (!raw) return ''
  return marked.parse(raw, { async: false })
})

const reportModeLabel = computed(() => {
  const m = detail.value?.report_mode || detail.value?.forecast_evidence_meta?.report_mode
  return MODE_LABEL[m] || ''
})

const scoreRows = computed(() => {
  const sc = detail.value?.score_components
  if (!sc || typeof sc !== 'object') return []
  const rows = []
  if (sc.story_type_weight != null) rows.push({ label: '故事类型权重', value: Number(sc.story_type_weight).toFixed(3) })
  if (sc.volume_score != null) rows.push({ label: '报道量/增速', value: Number(sc.volume_score).toFixed(3) })
  if (sc.entity_score != null) rows.push({ label: '实体完整度', value: Number(sc.entity_score).toFixed(3) })
  if (sc.burst_prob != null) rows.push({ label: '爆发分量', value: Number(sc.burst_prob).toFixed(3) })
  return rows
})

async function load() {
  await run(async () => {
    const data = await api.events(1)
    items.value = data.items || []
  })
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = 0
  }
  forecastBusy.value = false
}

async function refreshDetail(id) {
  const d = await api.eventDetail(id)
  if (selectedId.value !== id) return null
  detail.value = d
  return d
}

function startPoll(id) {
  stopPoll()
  forecastBusy.value = true
  pollTimer = setInterval(async () => {
    if (!drawerOpen.value || selectedId.value !== id) {
      stopPoll()
      return
    }
    try {
      const d = await refreshDetail(id)
      const st = d?.forecast_status
      if (st === 'ready' || st === 'failed' || (d?.forecast_report && st !== 'queued' && st !== 'running')) {
        stopPoll()
      }
    } catch {
      /* keep polling briefly */
    }
  }, 2500)
}

async function open(id) {
  stopPoll()
  selectedId.value = id
  drawerOpen.value = true
  detailLoading.value = true
  try {
    detail.value = await api.eventDetail(id)
    const st = detail.value?.forecast_status
    if (detail.value?.forecast_report && st === 'ready') {
      return
    }
    if (st === 'queued' || st === 'running') {
      startPoll(id)
      return
    }
    forecastBusy.value = true
    try {
      const fc = await api.eventForecast(id, { force: false })
      detail.value = {
        ...detail.value,
        forecast_status: fc.status || 'queued',
        forecast_error: null,
      }
      if (fc.status === 'ready' && fc.cached) {
        await refreshDetail(id)
        forecastBusy.value = false
      } else {
        startPoll(id)
      }
    } catch (e) {
      detail.value = {
        ...detail.value,
        forecast_status: 'failed',
        forecast_error: e.message || '研报入队失败',
      }
      forecastBusy.value = false
    }
  } finally {
    detailLoading.value = false
  }
}

async function regenForecast() {
  if (!selectedId.value || forecastBusy.value) return
  const id = selectedId.value
  forecastBusy.value = true
  try {
    await api.eventForecast(id, { force: true })
    detail.value = {
      ...detail.value,
      forecast_status: 'queued',
      forecast_error: null,
    }
    startPoll(id)
  } catch (e) {
    detail.value = {
      ...detail.value,
      forecast_status: 'failed',
      forecast_error: e.message || '研报入队失败',
    }
    forecastBusy.value = false
  }
}

function closeDrawer() {
  stopPoll()
  drawerOpen.value = false
  selectedId.value = null
}

function onKey(e) {
  if (e.key === 'Escape' && drawerOpen.value) closeDrawer()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  stopPoll()
  window.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.events-page { min-width: 0; }
.event-list { display: grid; gap: 12px; }
.event-card {
  padding: 16px 18px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 10px;
  cursor: pointer;
  background: var(--surface, #fff);
  transition: border-color .15s ease, box-shadow .15s ease;
}
.event-card:hover { border-color: var(--pine, #1f4d3a); }
.event-card.active {
  border-color: var(--pine, #1f4d3a);
  box-shadow: 0 0 0 1px var(--pine, #1f4d3a);
}
.event-top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.risk {
  font-variant-numeric: tabular-nums; font-weight: 700; background: #111; color: #fff;
  border-radius: 999px; padding: 2px 10px; font-size: 12px; flex-shrink: 0;
}
.clamp {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; align-items: center; }
.chips.tight { margin-top: 4px; }
.pill { background: #eef2ff; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.pill.muted { background: #f3f4f6; }
.pill.story { background: #ecfeff; }

.drawer-mask {
  position: fixed; inset: 0; z-index: 80;
  background: rgba(15, 23, 20, 0.35);
  display: flex; justify-content: flex-end;
}
.drawer {
  width: min(520px, 92vw);
  height: 100%;
  background: var(--surface, #fff);
  border-left: 1px solid var(--rule, #e5e7eb);
  display: flex; flex-direction: column;
  box-shadow: -8px 0 28px rgba(0,0,0,.08);
}
.drawer-head {
  display: flex; justify-content: space-between; gap: 12px; align-items: flex-start;
  padding: 18px 20px 12px; border-bottom: 1px solid var(--rule, #e5e7eb);
}
.drawer-head h3 { margin: 0 0 6px; font-size: 1.05rem; line-height: 1.35; }
.drawer-close { flex-shrink: 0; }
.drawer-body {
  flex: 1; overflow: auto; padding: 16px 20px 28px;
  display: flex; flex-direction: column; gap: 0;
}
.block {
  padding: 16px 0;
  border-bottom: 1px dashed var(--rule, #d1d5db);
}
.block:first-child { padding-top: 4px; }
.block:last-child {
  border-bottom: none;
  padding-bottom: 4px;
}
.block h4 { margin: 0 0 8px; font-size: 0.95rem; }
.block-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.block-head h4 { margin: 0; }
.tip { margin: 4px 0 10px; }
.mode-tag {
  display: inline-block; margin-right: 8px; padding: 1px 8px;
  border: 1px dashed var(--rule, #d1d5db); border-radius: 999px; font-size: 12px;
}
.tiny { font-size: 12px; padding: 4px 10px; }
.skel { padding: 12px; color: var(--ink-mute, #6b7280); }
.err { color: var(--clay, #b45309); }
.report.md :deep(h2),
.summary.md :deep(h2) { font-size: 1rem; margin: 1em 0 0.4em; }
.report.md :deep(h3),
.summary.md :deep(h3) { font-size: 0.95rem; margin: 0.85em 0 0.35em; }
.report.md :deep(p),
.summary.md :deep(p) { margin: 0.45em 0; line-height: 1.65; }
.report.md :deep(ul),
.summary.md :deep(ul),
.report.md :deep(ol),
.summary.md :deep(ol) { margin: 0.4em 0; padding-left: 1.25em; }
.report.md :deep(li),
.summary.md :deep(li) { margin: 0.2em 0; line-height: 1.55; }
.report.md :deep(strong),
.summary.md :deep(strong) { font-weight: 600; }
.score-list { list-style: none; padding: 0; margin: 0; }
.score-list li {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 6px 0; border-bottom: 1px solid var(--rule, #eee); font-size: 13px;
}
.timeline { padding-left: 18px; margin: 0; }
.timeline li { margin: 10px 0; }
.snip { margin: 4px 0 0; font-size: 13px; color: var(--ink-mute, #6b7280); line-height: 1.5; }
.chain { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.chain li {
  border: 1px solid var(--rule, #e5e7eb); border-radius: 8px; padding: 10px 12px; cursor: pointer;
}
.chain li:hover { border-color: var(--pine, #1f4d3a); }
.chain strong { display: block; font-size: 14px; margin-bottom: 4px; }

@media (min-width: 1100px) {
  .drawer { width: min(40vw, 560px); }
}
</style>
