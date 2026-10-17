<template>
  <div>
    <header class="ed-head reveal">
      <div class="head-row">
        <div>
          <div class="ed-kicker">System · 印务检查</div>
          <h1 class="ed-title">运行监控</h1>
          <p class="ed-lede">基础设施健康、流水线状态。采集在此选择爬虫与节奏后启动，并查看每个爬虫的日志。</p>
        </div>
        <button class="secondary" :disabled="loading" @click="load">刷新</button>
      </div>
    </header>

    <div v-if="error" class="card empty">
      <div class="empty-title">监控服务不可达</div>
      <p>{{ error }}</p>
      <button class="secondary" @click="load">重试</button>
    </div>

    <template v-else>
      <!-- 健康检查 -->
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
          <div v-for="(h, i) in healthRows" :key="h.name"
               class="card health-card card-hover reveal" :style="{ '--reveal-delay': i * 70 + 'ms' }">
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
        <div class="sec-mark"><span class="no">02</span><h3>采集调度</h3><span class="rule"></span></div>
        <div class="crawl-status">
          <span class="pill" :class="phaseClass">{{ phaseLabel }}</span>
          <span class="meta">最近一轮 {{ fmt(crawl?.last_run?.started_at) }}</span>
          <span class="meta">下次预计 {{ formatNext(crawl?.next_run_at) }}</span>
        </div>
        <p v-if="crawl?.last_run?.error" class="form-error">{{ crawl.last_run.error }}</p>

        <div class="field">
          <label>爬虫</label>
          <div class="seg">
            <button
              type="button"
              v-for="src in sources"
              :key="src.key"
              class="seg-btn"
              :class="{ on: selected.includes(src.key) }"
              :disabled="locked"
              @click="toggleSource(src.key)"
            >{{ src.label }}</button>
          </div>
        </div>

        <div class="field">
          <label>节奏</label>
          <div class="seg">
            <button type="button" class="seg-btn" :class="{ on: scheduleMode === 'hourly' }" :disabled="locked" @click="scheduleMode = 'hourly'">每小时</button>
            <button type="button" class="seg-btn" :class="{ on: scheduleMode === 'daily' }" :disabled="locked" @click="scheduleMode = 'daily'">每天</button>
          </div>
        </div>

        <div class="field" v-if="scheduleMode === 'daily'">
          <label for="daily-time">每天时刻</label>
          <input id="daily-time" type="time" v-model="dailyTime" :disabled="locked" />
        </div>

        <p class="meta hint">
          {{ scheduleMode === 'hourly'
            ? '点启动后立刻采集一次，之后每小时持续执行。'
            : '点启动后立刻采集一次；当天到达所选时刻还会再采集，之后每天该时刻执行。' }}
        </p>

        <div class="row">
          <button type="button" :disabled="!canStart" @click="startCrawl">{{ actionLoading && !locked ? '启动中…' : '启动' }}</button>
          <button type="button" class="secondary" :disabled="!locked || actionLoading" @click="stopCrawl">停止</button>
        </div>
        <p v-if="actionError" class="form-error">{{ actionError }}</p>

        <div class="log-list">
          <article v-for="c in crawlerLogs" :key="c.key" class="log-card">
            <div class="log-head">
              <strong>{{ c.name || sourceLabel(c.key) }}</strong>
              <span class="pill" :class="statusClass(c.status)">{{ c.status ? statusLabel(c.status) : '尚无记录' }}</span>
              <span class="meta mono">{{ c.success_count }} / {{ c.total_count }}</span>
            </div>
            <p v-if="c.error_message" class="form-error">{{ c.error_message }}</p>
            <pre class="log-box">{{ c.log_text || '暂无日志' }}</pre>
          </article>
        </div>
      </section>

      <!-- 流水线状态 -->
      <section class="card reveal" style="margin-top:32px;--reveal-delay:160ms">
        <div class="sec-mark"><span class="no">03</span><h3>处理流水线</h3><span class="rule"></span></div>
        <div class="pipe-grid" v-if="processing">
          <div class="pipe-item">
            <span class="meta">最近处理</span>
            <strong>{{ fmt(processing.last_pipeline_at) }}</strong>
            <span class="meta mono" v-if="processing.last_pipeline_stats">
              入库 {{ processing.last_pipeline_stats.inserted ?? 0 }} 条
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

      <!-- 爬虫任务 -->
      <section class="card reveal" style="margin-top:16px;--reveal-delay:220ms">
        <div class="sec-mark"><span class="no">04</span><h3>爬虫任务</h3><span class="rule"></span></div>
        <div class="table-wrap" v-if="tasks.length">
          <table class="task-table">
            <thead>
              <tr>
                <th>爬虫</th><th>状态</th><th>成功 / 总数</th><th>结束时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tasks" :key="t.id">
                <td class="mono">{{ t.crawler_name }}</td>
                <td>
                  <span class="pill" :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span>
                </td>
                <td class="mono">{{ t.success_count }} / {{ t.total_count }}</td>
                <td class="meta mono">{{ fmt(t.end_time) }}</td>
              </tr>
            </tbody>
          </table>
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import { crawlerLabel, crawlerSources, formatTime } from '../format'

const health = ref(null)
const processing = ref(null)
const tasks = ref([])
const { loading, error, run } = useAsync()

const crawl = ref(null)
const scheduleMode = ref('hourly')
const dailyTime = ref('08:00')
const selected = ref(['bioon', 'globenewswire', 'prnewswire', 'pharmcube'])
const formSynced = ref(false)
const actionError = ref('')
const actionLoading = ref(false)
let pollTimer = 0

const checked = computed(() => health.value !== null)
const locked = computed(() => Boolean(crawl.value?.running))
const canStart = computed(() => {
  if (locked.value || actionLoading.value) return false
  if (!selected.value.length) return false
  if (scheduleMode.value === 'daily' && !dailyTime.value) return false
  return true
})
const phaseLabel = computed(() => {
  if (crawl.value?.active) return '本轮进行中'
  if (crawl.value?.running) return '运行中'
  return '未启动'
})
const phaseClass = computed(() => {
  if (crawl.value?.active) return 'warn'
  if (crawl.value?.running) return 'ok'
  return ''
})
const sources = computed(() => {
  const rows = crawl.value?.available
  if (rows?.length) return rows.map((row) => ({ key: row.key, label: row.name }))
  return crawlerSources.value
})
const crawlerLogs = computed(() => crawl.value?.crawlers || [])

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
      value: embTotal ? `${Math.round((embDone / embTotal) * 100)}%` : '—',
      detail: `${embDone} / ${embTotal} 条新闻已向量化`,
    },
  ]
})

const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败' }[s] || s)
const statusClass = (s) => ({ success: 'ok', running: 'warn', failed: 'danger' }[s] || '')
const fmt = (v) => (v ? formatTime(v) : '尚未执行')
const sourceLabel = (key) => crawlerLabel(key)

function formatNext(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  if (d.getTime() <= Date.now() + 5000) return '即将执行'
  return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function applyConfig(cfg) {
  if (!cfg) return
  scheduleMode.value = cfg.schedule_mode || 'hourly'
  dailyTime.value = cfg.daily_time || '08:00'
  if (cfg.crawler_keys?.length) selected.value = [...cfg.crawler_keys]
  else if (!cfg.running) selected.value = sources.value.map((item) => item.key)
}

function toggleSource(key) {
  if (locked.value) return
  if (selected.value.includes(key)) selected.value = selected.value.filter((item) => item !== key)
  else selected.value = [...selected.value, key]
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
    if (!formSynced.value || status?.running) {
      applyConfig(status)
      formSynced.value = true
    }
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
    const status = await api.crawlStatus()
    crawl.value = status
    if (!formSynced.value || status?.running) {
      applyConfig(status)
      formSynced.value = true
    }
  } catch (e) {
    actionError.value = e.message || '采集状态不可用'
  }
}

async function startCrawl() {
  actionError.value = ''
  actionLoading.value = true
  try {
    const status = await api.crawlStart({
      schedule_mode: scheduleMode.value,
      daily_time: scheduleMode.value === 'daily' ? dailyTime.value : null,
      crawler_keys: selected.value,
    })
    crawl.value = status
    applyConfig(status)
    formSynced.value = true
    await refreshQuiet()
  } catch (e) {
    actionError.value = e.message || '启动失败'
  } finally {
    actionLoading.value = false
  }
}

async function stopCrawl() {
  actionError.value = ''
  actionLoading.value = true
  try {
    const status = await api.crawlStop()
    crawl.value = status
    applyConfig(status)
    formSynced.value = true
  } catch (e) {
    actionError.value = e.message || '停止失败'
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  load()
  pollTimer = setInterval(refreshQuiet, 5000)
})
onBeforeUnmount(() => clearInterval(pollTimer))
</script>

<style scoped>
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--sp-4);
}

.health-grid { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.health-card { padding: var(--sp-4) var(--sp-5); }
.health-head { display: flex; align-items: center; gap: var(--sp-2); }
.health-name { font-size: var(--fs-xs); color: var(--ink-mute); letter-spacing: 0.16em; text-transform: uppercase; font-weight: 700; }
.health-value { font-family: var(--font-serif); font-size: clamp(22px, 2.6vw, 30px); font-weight: 700; color: var(--pine); margin: 8px 0 2px; }
.dot {
  width: 9px; height: 9px; border-radius: 50%; flex: none;
}
.dot.ok   { background: var(--moss);  animation: blink 2.4s ease-in-out infinite; }
.dot.warn { background: var(--brass); }
.dot.bad  { background: var(--clay); }
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
}
.task-table tbody tr { transition: background var(--dur-fast); }
.task-table tbody tr:hover { background: var(--wash); }
.task-table tbody tr:last-child td { border-bottom: none; }

.crawl-status { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; margin-bottom: 16px; }
.field { margin-bottom: 16px; }
.field label { display: block; font-size: var(--fs-xs); letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-mute); font-weight: 700; margin-bottom: 8px; }
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: transparent;
  color: var(--pine);
  padding: 8px 14px;
}
.seg-btn.on { background: var(--pine); color: var(--paper); }
.hint { margin: 0 0 16px; }
.form-error { color: var(--clay); margin: 8px 0; }
.log-list { display: grid; gap: 12px; margin-top: 20px; }
.log-card { border-top: 1px solid var(--line); padding-top: 12px; }
.log-head { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; }
.log-box {
  margin: 8px 0 0;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  background: var(--wash);
  padding: 10px 12px;
  border-radius: var(--r-md);
}
</style>
