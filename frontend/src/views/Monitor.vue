<template>
  <div>
    <header class="ed-head reveal">
      <div class="head-row">
        <div>
          <div class="ed-kicker">Crawl · 采集监控</div>
          <h1 class="ed-title">爬虫监控</h1>
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
        <div v-if="progressView" class="progress-panel">
          <div class="progress-head">
            <strong>{{ progressView.label }}</strong>
            <span class="meta">{{ progressView.detail }}</span>
          </div>
          <div class="progress-track" aria-hidden="true">
            <div class="progress-fill" :style="{ width: progressView.pct + '%' }"></div>
          </div>
          <div class="progress-meta meta">
            <span v-if="progressView.crawlerText">{{ progressView.crawlerText }}</span>
            <span v-if="progressView.counts">{{ progressView.counts }}</span>
          </div>
          <ol class="progress-stages">
            <li
              v-for="s in progressStages"
              :key="s.key"
              :class="{ on: s.on, done: s.done }"
            >{{ s.label }}</li>
          </ol>
        </div>
        <div v-if="crawl && crawl.llm_ready === false" class="llm-gate">
          <p class="form-error">{{ crawl.llm_message || '尚未配置 LLM，无法启动采集。' }}</p>
          <router-link class="llm-gate-link" to="/settings">前往系统设置</router-link>
        </div>
        <div v-if="crawl?.last_run?.error" class="run-error">
          <p class="form-error">最近一轮失败：{{ shortError(crawl.last_run.error) }}</p>
          <details v-if="crawl.last_run.error.length > 240" class="run-error-detail">
            <summary>查看完整错误</summary>
            <pre>{{ crawl.last_run.error }}</pre>
          </details>
        </div>

        <div class="source-picker">
          <div class="source-picker-head">
            <div>
              <div class="source-picker-title">本轮采集来源</div>
              <p class="meta source-picker-hint">
                {{ locked ? '采集运行中，来源不可改。' : '点击切换；启动后将只跑勾选的来源。' }}
              </p>
            </div>
            <span class="source-count" :class="{ warn: !selectedCount }">已选 {{ selectedCount }} / {{ sourceTotal }}</span>
          </div>
          <div v-if="!locked" class="source-actions">
            <button type="button" class="ghost" :disabled="!sourceTotal || selectedCount === sourceTotal" @click="selectAllSources">全选</button>
            <button type="button" class="ghost" :disabled="!selectedCount" @click="clearSources">清空</button>
          </div>
          <div class="source-grid" role="group" aria-label="本轮采集来源">
            <button
              type="button"
              v-for="src in sources"
              :key="src.key"
              class="source-card"
              :class="{ on: selected.includes(src.key) }"
              :disabled="locked"
              :aria-pressed="selected.includes(src.key)"
              @click="toggleSource(src.key)"
            >
              <span class="source-check" aria-hidden="true">{{ selected.includes(src.key) ? '✓' : '' }}</span>
              <span class="source-text">
                <strong>{{ src.label }}</strong>
                <span class="meta mono">{{ src.key }}</span>
              </span>
            </button>
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
          <button type="button" class="ghost" :disabled="actionLoading || locked" @click="reprocessPending">补跑积压</button>
        </div>
        <p v-if="actionError" class="form-error">{{ actionError }}</p>
        <p v-if="reprocessMsg" class="meta">{{ reprocessMsg }}</p>

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
const reprocessMsg = ref('')
let pollTimer = 0

const STAGE_ORDER = [
  { key: 'crawling', label: '爬取' },
  { key: 'filtering', label: '过滤' },
  { key: 'persist', label: '落库' },
  { key: 'reprocess', label: '补跑' },
  { key: 'relevance', label: '相关性' },
  { key: 'summary', label: '摘要' },
  { key: 'embedding', label: '向量' },
  { key: 'clustering', label: '聚类' },
  { key: 'done', label: '完成' },
]

const checked = computed(() => health.value !== null)
const locked = computed(() => Boolean(crawl.value?.running))
const llmReady = computed(() => crawl.value?.llm_ready !== false)
const canStart = computed(() => {
  if (locked.value || actionLoading.value) return false
  if (!llmReady.value) return false
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
const progressRaw = computed(() => crawl.value?.progress || crawl.value?.last_run?.progress || null)
const progressView = computed(() => {
  const p = progressRaw.value
  if (!p || !crawl.value?.active) return null
  const done = Number(p.crawlers_done || 0)
  const total = Number(p.crawlers_total || 0)
  const stage = p.stage || 'crawling'
  const idx = STAGE_ORDER.findIndex((s) => s.key === stage)
  let pct = idx >= 0 ? Math.round(((idx + 1) / STAGE_ORDER.length) * 100) : 8
  if (stage === 'crawling' && total > 0) {
    pct = Math.max(8, Math.round((done / Math.max(total, 1)) * 40))
  }
  if (stage === 'done') pct = 100
  return {
    label: p.label || stage,
    detail: p.detail || '',
    pct: Math.min(100, Math.max(5, pct)),
    crawlerText: total ? `爬虫 ${done}/${total}` : '',
    counts: [
      p.items_in != null ? `输入 ${p.items_in}` : '',
      p.items_out != null ? `输出 ${p.items_out}` : '',
      p.raw_inserted != null ? `落库 ${p.raw_inserted}` : '',
    ].filter(Boolean).join(' · '),
  }
})
const progressStages = computed(() => {
  const p = progressRaw.value
  const stage = p?.stage || ''
  const idx = STAGE_ORDER.findIndex((s) => s.key === stage)
  return STAGE_ORDER
    .filter((s) => s.key !== 'reprocess' || stage === 'reprocess')
    .map((s) => {
      const orderIdx = STAGE_ORDER.findIndex((x) => x.key === s.key)
      return {
        key: s.key,
        label: s.label,
        on: s.key === stage,
        done: idx >= 0 && orderIdx >= 0 && orderIdx < idx,
      }
    })
})
const sources = computed(() => {
  const rows = crawl.value?.available
  if (rows?.length) return rows.map((row) => ({ key: row.key, label: row.name }))
  return crawlerSources.value
})
const sourceTotal = computed(() => sources.value.length)
const selectedCount = computed(() => selected.value.filter((key) => sources.value.some((s) => s.key === key)).length)
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
      value: embTotal ? `${Math.round((embDone / embTotal) * 100)}%` : (vi.status === 'ok' ? '100%' : '—'),
      detail: embTotal
        ? `${embDone} / ${embTotal} 条应向量化新闻已处理${vi.news_rejected ? ` · 已排除 ${vi.news_rejected} 条拒绝稿` : ''}`
        : (vi.news_rejected ? `暂无待向量化稿件 · 已排除 ${vi.news_rejected} 条拒绝稿` : '暂无新闻'),
    },
  ]
})

const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败' }[s] || s)
const statusClass = (s) => ({ success: 'ok', running: 'warn', failed: 'danger' }[s] || '')
const fmt = (v) => (v ? formatTime(v) : '尚未执行')
const sourceLabel = (key) => crawlerLabel(key)

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

function applyConfig(cfg) {
  if (!cfg) return
  scheduleMode.value = cfg.schedule_mode || 'hourly'
  dailyTime.value = cfg.daily_time || '08:00'
  const availableKeys = new Set(sources.value.map((item) => item.key))
  if (cfg.crawler_keys?.length) {
    // 只保留当前可选（已启用）源，避免进度分母含已禁用但仍写在配置里的 key
    selected.value = cfg.crawler_keys.filter((key) => availableKeys.has(key))
  } else if (!cfg.running) {
    selected.value = sources.value.map((item) => item.key)
  }
}

function toggleSource(key) {
  if (locked.value) return
  if (selected.value.includes(key)) selected.value = selected.value.filter((item) => item !== key)
  else selected.value = [...selected.value, key]
}

function selectAllSources() {
  if (locked.value) return
  selected.value = sources.value.map((item) => item.key)
}

function clearSources() {
  if (locked.value) return
  selected.value = []
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
  if (!llmReady.value) {
    actionError.value = crawl.value?.llm_message || '尚未配置 LLM，请先到「系统设置」配置大模型'
    return
  }
  actionLoading.value = true
  try {
    const availableKeys = new Set(sources.value.map((item) => item.key))
    const status = await api.crawlStart({
      schedule_mode: scheduleMode.value,
      daily_time: scheduleMode.value === 'daily' ? dailyTime.value : null,
      crawler_keys: selected.value.filter((key) => availableKeys.has(key)),
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

async function reprocessPending() {
  actionError.value = ''
  reprocessMsg.value = ''
  actionLoading.value = true
  try {
    const stats = await api.crawlReprocess(50)
    reprocessMsg.value = `补跑完成：捞取 ${stats.pending ?? 0} 条，ready ${stats.ready_updated ?? stats.after_embedding ?? 0}`
    await refreshQuiet()
  } catch (e) {
    actionError.value = e.message || '补跑失败'
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
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--sp-4);
}
.head-row .ed-lede {
  max-width: none;
  white-space: nowrap;
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
.progress-panel {
  margin: 0 0 18px;
  padding: 12px 14px;
  background: var(--wash);
  border-radius: var(--r-md);
}
.progress-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: baseline;
  margin-bottom: 10px;
}
.progress-head strong { font-family: var(--font-serif); font-size: var(--fs-h2); color: var(--pine); }
.progress-track {
  height: 8px;
  background: color-mix(in srgb, var(--pine) 12%, var(--paper));
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--pine);
  border-radius: 999px;
  transition: width 0.35s ease;
}
.progress-meta { display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 8px; }
.progress-stages {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
}
.progress-stages li {
  font-size: var(--fs-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink-mute);
  padding: 4px 8px;
  border-radius: var(--r-sm);
}
.progress-stages li.done { color: var(--moss); background: color-mix(in srgb, var(--moss) 12%, transparent); }
.progress-stages li.on { color: var(--paper); background: var(--pine); }
.field { margin-bottom: 16px; }
.field label { display: block; font-size: var(--fs-xs); letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-mute); font-weight: 700; margin-bottom: 8px; }
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: transparent;
  color: var(--pine);
  padding: 8px 14px;
}
.seg-btn.on { background: var(--pine); color: var(--paper); }
.source-picker {
  margin: 0 0 20px;
  padding: 14px 16px;
  background: var(--wash);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}
.source-picker-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
}
.source-picker-title {
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  color: var(--pine);
  font-weight: 700;
}
.source-picker-hint { margin: 4px 0 0; }
.source-count {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--pine);
  white-space: nowrap;
  padding: 4px 10px;
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--pine) 10%, transparent);
}
.source-count.warn {
  color: var(--clay);
  background: color-mix(in srgb, var(--clay) 10%, transparent);
}
.source-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.source-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  text-align: left;
  padding: 12px 12px;
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--line);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: border-color var(--dur-fast), background var(--dur-fast), box-shadow var(--dur-fast);
}
.source-card:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--pine) 45%, var(--line));
  box-shadow: none;
}
.source-card.on {
  border-color: var(--pine);
  background: color-mix(in srgb, var(--pine) 8%, var(--paper));
}
.source-card:disabled {
  cursor: not-allowed;
  opacity: 0.85;
}
.source-check {
  flex: none;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  border: 1.5px solid var(--line);
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  color: var(--paper);
  background: transparent;
}
.source-card.on .source-check {
  border-color: var(--pine);
  background: var(--pine);
}
.source-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.source-text strong {
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--ink);
}
.source-card.on .source-text strong { color: var(--pine); }
.hint { margin: 0 0 16px; }
.form-error { color: var(--clay); margin: 8px 0; }
.run-error { margin: 0 0 16px; }
.run-error .form-error { margin: 0; }
.run-error-detail {
  margin-top: 8px;
  font-size: var(--fs-sm);
  color: var(--ink-soft);
}
.run-error-detail summary { cursor: pointer; color: var(--pine); font-weight: 650; }
.run-error-detail pre {
  margin: 8px 0 0;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.45;
  background: var(--wash);
  color: var(--ink);
  padding: 10px 12px;
  border-radius: var(--r-md);
}
.llm-gate {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin: 0 0 16px;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--clay) 8%, var(--paper));
  border-radius: var(--r-md);
}
.llm-gate .form-error { margin: 0; }
.llm-gate-link {
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--pine);
  text-decoration: underline;
  text-underline-offset: 3px;
}
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
