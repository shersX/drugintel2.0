<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Crawl · 采集监控</div>
      <p class="ed-lede">
        只读查看基础设施、本轮按源进度与任务历史。启动与调度请到
        <router-link to="/settings?tab=crawlers">爬虫注册表</router-link>。
      </p>
    </header>

    <div v-if="error" class="card empty">
      <div class="empty-title">监控服务不可达</div>
      <p>{{ error }}</p>
      <button class="secondary" @click="load">重试</button>
    </div>

    <template v-else>
      <section class="reveal">
        <div class="sec-mark"><span class="no">01</span><h3>基础设施</h3><span class="rule"></span></div>
        <div class="grid health-grid">
          <template v-if="loading && !checked">
            <div v-for="i in 3" :key="i" class="card">
              <div class="skeleton" style="width:80px;height:14px"></div>
              <div class="skeleton" style="width:120px;height:26px;margin-top:12px"></div>
            </div>
          </template>
          <template v-else>
            <div
              v-for="(h, i) in healthRows"
              :key="h.name"
              class="card health-card card-hover reveal"
              :style="{ '--reveal-delay': i * 70 + 'ms' }"
            >
              <div class="health-head">
                <span :class="['dot', h.level]"></span>
                <span class="health-name">{{ h.name }}</span>
              </div>
              <div class="health-value">{{ h.value }}</div>
              <div class="meta">{{ h.detail }}</div>
            </div>
          </template>
        </div>
      </section>

      <section class="card reveal" style="margin-top:32px;--reveal-delay:120ms">
        <div class="sec-mark"><span class="no">02</span><h3>本轮采集</h3><span class="rule"></span></div>
        <div class="crawl-status">
          <span class="pill" :class="phaseClass">{{ phaseLabel }}</span>
          <span class="meta">最近一轮 {{ fmt(crawl?.last_run?.started_at) }}</span>
          <span class="meta">下次预计 {{ formatNext(crawl?.next_run_at) }}</span>
          <span class="meta" v-if="roundDetail">{{ roundDetail }}</span>
        </div>
        <div v-if="crawl?.last_run?.error" class="run-error">
          <p class="form-error">最近一轮：{{ shortError(crawl.last_run.error) }}</p>
        </div>
        <div class="row" v-if="crawl?.active" style="margin-bottom:12px">
          <button type="button" class="ghost" :disabled="actionLoading" @click="abandonStuck">
            清除卡死状态
          </button>
        </div>

        <div class="table-wrap" v-if="crawlerProgressRows.length">
          <table class="task-table">
            <thead>
              <tr>
                <th>数据源</th><th>阶段</th><th>说明</th><th>落库</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in crawlerProgressRows" :key="row.key">
                <td>
                  <strong>{{ row.label }}</strong>
                  <div class="meta mono">{{ row.key }}</div>
                </td>
                <td>
                  <span class="pill" :class="stagePillClass(row.stage)">{{ row.stageLabel }}</span>
                </td>
                <td class="meta">{{ row.detail || '—' }}</td>
                <td class="mono">{{ row.rawInserted != null ? row.rawInserted : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">本轮尚无按源进度（未开采集或进度尚未上报）</p>
      </section>

      <section class="card reveal" style="margin-top:32px;--reveal-delay:160ms">
        <div class="sec-mark"><span class="no">03</span><h3>处理流水线</h3><span class="rule"></span></div>
        <div class="pipe-grid" v-if="processing">
          <div class="pipe-item">
            <span class="meta">最近处理</span>
            <strong>{{ fmt(processing.last_pipeline_at) }}</strong>
            <span class="meta mono" v-if="processing.last_pipeline_stats">
              入库 {{ processing.last_pipeline_stats.inserted ?? processing.last_pipeline_stats.raw_inserted ?? 0 }} 条
            </span>
          </div>
          <div class="pipe-item">
            <span class="meta">最近聚类</span>
            <strong>{{ fmt(processing.last_cluster_at) }}</strong>
            <span class="meta mono" v-if="processing.last_cluster_stats">
              新建事件 {{ processing.last_cluster_stats.new_events ?? 0 }} 个
            </span>
          </div>
        </div>
        <div v-else class="empty"><div class="empty-title">尚无流水线记录</div></div>
      </section>

      <section class="card reveal" style="margin-top:16px;--reveal-delay:220ms">
        <div class="sec-mark"><span class="no">04</span><h3>爬虫任务</h3><span class="rule"></span></div>
        <div class="seg" style="margin-bottom:12px">
          <button type="button" class="seg-btn" :class="{ on: taskTab === 'news' }" @click="setTaskTab('news')">新闻任务</button>
          <button type="button" class="seg-btn" :class="{ on: taskTab === 'pipeline' }" @click="setTaskTab('pipeline')">管线任务</button>
        </div>
        <div class="table-wrap" v-if="pagedTasks.length">
          <table class="task-table">
            <thead>
              <tr>
                <th>爬虫</th><th>状态</th><th>成功 / 总数</th><th>结束时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in pagedTasks" :key="t.id">
                <td class="mono">{{ t.crawler_name }}</td>
                <td>
                  <span class="pill" :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span>
                </td>
                <td class="mono">{{ t.success_count }} / {{ t.total_count }}</td>
                <td class="meta mono">{{ fmt(t.end_time) }}</td>
              </tr>
            </tbody>
          </table>
          <div class="row task-pager" v-if="taskTotal > taskPageSize">
            <button type="button" class="secondary" :disabled="taskPage <= 1" @click="taskPage -= 1">上一页</button>
            <span class="meta">第 {{ taskPage }} 页 · 共 {{ taskTotal }} 条</span>
            <button type="button" class="secondary" :disabled="taskPage >= taskTotalPages" @click="taskPage += 1">下一页</button>
          </div>
        </div>
        <div v-else-if="!loading" class="empty">
          <div class="empty-title">暂无任务记录</div>
          <p>爬虫运行后此处展示执行历史</p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import { crawlerLabel, formatTime } from '../format'

const health = ref(null)
const processing = ref(null)
const tasks = ref([])
const crawl = ref(null)
const { loading, error, run } = useAsync()
const actionLoading = ref(false)
const actionError = ref('')
const taskTab = ref('news')
const taskPage = ref(1)
const taskPageSize = 10
let pollTimer = 0

const STAGE_LABELS = {
  crawling: '爬取中',
  filtering: '过滤',
  persist: '落库',
  reprocess: '补跑',
  relevance: '相关性',
  summary: '摘要',
  embedding: '向量',
  clustering: '聚类',
  done: '完成',
  failed: '失败',
  running: '进行中',
}

function setTaskTab(tab) {
  taskTab.value = tab
  taskPage.value = 1
}

const checked = computed(() => health.value !== null)

const progressRaw = computed(() => crawl.value?.progress || crawl.value?.last_run?.progress || null)

const phaseLabel = computed(() => {
  if (crawl.value?.active) {
    const stage = progressRaw.value?.round?.stage || progressRaw.value?.stage
    if (stage === 'clustering') return '聚类中'
    return '本轮进行中'
  }
  if (crawl.value?.running) return '调度已启动'
  return '调度未启动'
})
const phaseClass = computed(() => {
  if (crawl.value?.active) return 'warn'
  if (crawl.value?.running) return 'ok'
  return ''
})
const roundDetail = computed(() => {
  const p = progressRaw.value
  if (!p) return ''
  const r = p.round || {}
  const done = r.crawlers_done ?? p.crawlers_done
  const total = r.crawlers_total ?? p.crawlers_total
  if (total != null) return `进度 ${done ?? 0}/${total}`
  return r.detail || p.detail || ''
})

const crawlerProgressRows = computed(() => {
  const p = progressRaw.value
  const by = p?.by_crawler
  if (!by || typeof by !== 'object') return []
  return Object.keys(by).sort().map((key) => {
    const row = by[key] || {}
    const stage = row.stage || ''
    return {
      key,
      label: crawlerLabel(key) || key,
      stage,
      stageLabel: STAGE_LABELS[stage] || row.label || stage || '—',
      detail: row.detail || row.label || '',
      rawInserted: row.raw_inserted,
    }
  })
})

const filteredTasks = computed(() => {
  const rows = tasks.value || []
  if (taskTab.value === 'pipeline') {
    return rows.filter((t) => String(t.crawler_name || '').includes('pipeline') || t.crawler_name === 'simcere_pipeline')
  }
  return rows.filter((t) => !String(t.crawler_name || '').includes('pipeline'))
})
const taskTotal = computed(() => filteredTasks.value.length)
const taskTotalPages = computed(() => Math.max(1, Math.ceil(taskTotal.value / taskPageSize)))
const pagedTasks = computed(() => {
  const start = (taskPage.value - 1) * taskPageSize
  return filteredTasks.value.slice(start, start + taskPageSize)
})
watch(taskTotalPages, (pages) => {
  if (taskPage.value > pages) taskPage.value = pages
})

const healthRows = computed(() => {
  const c = health.value?.checks || {}
  const db = c.database || {}
  const rd = c.redis || {}
  const vi = c.vector_index || {}
  const embTotal = vi.news_total ?? 0
  const embDone = vi.news_with_embedding ?? 0
  return [
    {
      name: '数据库',
      level: db.status === 'ok' ? 'ok' : 'bad',
      value: db.status === 'ok' ? '连接正常' : '异常',
      detail: db.latency_ms != null ? `响应 ${db.latency_ms}ms · pgvector ${db.pgvector ? '已启用' : '未启用'}` : (db.error || ''),
    },
    {
      name: 'Redis',
      level: rd.status === 'ok' ? 'ok' : rd.status === 'degraded' ? 'warn' : 'bad',
      value: rd.status === 'ok' ? '连接正常' : rd.status === 'degraded' ? '降级' : '异常',
      detail: rd.error || '缓存与任务队列',
    },
    {
      name: '向量覆盖',
      level: vi.status === 'ok' ? (embTotal && embDone < embTotal ? 'warn' : 'ok') : 'bad',
      value: embTotal ? `${Math.round((embDone / embTotal) * 100)}%` : (vi.status === 'ok' ? '100%' : '—'),
      detail: embTotal
        ? `${embDone} / ${embTotal} 条应向量化新闻已处理${vi.news_rejected ? ` · 已排除 ${vi.news_rejected} 条拒绝稿` : ''}`
        : (vi.news_rejected ? `暂无待向量化稿件 · 已排除 ${vi.news_rejected} 条拒绝稿` : '暂无新闻'),
    },
  ]
})

const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败', aborted: '已中断' }[s] || s)
const statusClass = (s) => ({ success: 'ok', running: 'warn', failed: 'danger', aborted: 'danger' }[s] || '')
const stagePillClass = (stage) => {
  if (stage === 'done') return 'ok'
  if (stage === 'failed') return 'danger'
  if (stage) return 'warn'
  return ''
}
const fmt = (v) => (v ? formatTime(v) : '尚未执行')

function shortError(text) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const first = raw.split('\n').map((line) => line.trim()).find(Boolean) || raw
  if (first.length <= 240) return first
  return `${first.slice(0, 240)}…`
}

function formatNext(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  if (d.getTime() <= Date.now() + 5000) return '即将执行'
  return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function refreshQuiet() {
  try {
    const [data, status] = await Promise.all([api.monitor(), api.crawlStatus()])
    if (data) {
      health.value = data.health || null
      processing.value = data.processing || null
      tasks.value = data.crawler_tasks || []
    }
    crawl.value = status
  } catch {
    /* 轮询失败时保留当前页面 */
  }
}

async function load() {
  const data = await run(() => api.monitor())
  if (data) {
    health.value = data.health || null
    processing.value = data.processing || null
    tasks.value = data.crawler_tasks || []
  }
  try {
    crawl.value = await api.crawlStatus()
  } catch (e) {
    actionError.value = e.message || '采集状态不可用'
  }
}

async function abandonStuck() {
  actionLoading.value = true
  try {
    crawl.value = await api.crawlAbandon()
    await refreshQuiet()
  } catch (e) {
    actionError.value = e.message || '清除失败'
  } finally {
    actionLoading.value = false
  }
}

function armPoll(ms) {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    const wasActive = Boolean(crawl.value?.active)
    await refreshQuiet()
    const nowActive = Boolean(crawl.value?.active)
    if (wasActive !== nowActive) armPoll(nowActive ? 2000 : 5000)
  }, ms)
}

onMounted(async () => {
  await load()
  armPoll(crawl.value?.active ? 2000 : 5000)
})
onBeforeUnmount(() => clearInterval(pollTimer))
</script>

<style scoped>
.health-grid { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.health-card { padding: var(--sp-4) var(--sp-5); }
.health-head { display: flex; align-items: center; gap: var(--sp-2); }
.health-name { font-size: var(--fs-xs); color: var(--ink-mute); letter-spacing: 0.16em; text-transform: uppercase; font-weight: 700; }
.health-value { font-family: var(--font-serif); font-size: clamp(22px, 2.6vw, 30px); font-weight: 700; color: var(--pine); margin: 8px 0 2px; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
.dot.ok { background: var(--moss); animation: blink 2.4s ease-in-out infinite; }
.dot.warn { background: var(--brass); }
.dot.bad { background: var(--clay); }
@keyframes blink { 50% { opacity: 0.35; } }

.pipe-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--sp-4); }
.pipe-item { display: flex; flex-direction: column; gap: 4px; }
.pipe-item strong { font-family: var(--font-serif); font-size: var(--fs-h2); }
.mono { font-family: var(--font-mono); font-size: var(--fs-sm); }

.table-wrap { overflow-x: auto; }
.task-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-sm);
}
.task-table th {
  text-align: left;
  color: var(--ink-mute);
  font-weight: 700;
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--ink);
}
.task-table td {
  padding: var(--sp-3);
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.task-table tbody tr:hover { background: var(--wash); }
.task-table tbody tr:last-child td { border-bottom: none; }

.crawl-status { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; margin-bottom: 16px; }
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: transparent;
  color: var(--pine);
  padding: 8px 14px;
}
.seg-btn.on { background: var(--pine); color: var(--paper); }
.task-pager {
  margin-top: 12px;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}
.form-error { color: var(--clay); margin: 8px 0; }
.run-error { margin: 0 0 12px; }
.ed-lede a { color: var(--pine); font-weight: 650; }
</style>
