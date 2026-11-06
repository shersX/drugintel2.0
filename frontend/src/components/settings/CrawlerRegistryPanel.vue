<template>
  <div class="reg-page reveal">
    <header class="reg-hero">
      <div class="reg-hero-copy">
        <h2 class="reg-title">爬虫注册表</h2>
        <p class="reg-desc">
          管理已注册来源的启停与采集参数。运行进度见
          <router-link to="/monitor">爬虫监控</router-link>。
        </p>
      </div>
      <div class="reg-hero-side">
        <p class="reg-count">
          <strong>{{ crawlerOnCount }}</strong>
          <span>/ {{ crawlerRows.length }} 已启用</span>
        </p>
        <p v-if="crawlerOffCount" class="meta">停用 {{ crawlerOffCount }} 个</p>
        <p v-if="drawerOpen && draftDirty" class="meta unsaved">1 项未保存</p>
        <router-link class="reg-monitor" to="/monitor">查看运行监控</router-link>
      </div>
    </header>

    <p v-if="crawlerMsg" class="meta" :class="{ 'form-error': crawlerErr }">{{ crawlerMsg }}</p>
    <p v-if="crawlerLoading" class="meta">加载中…</p>

    <template v-else>
      <section class="reg-card">
        <div class="table-wrap" v-if="catalogRows.length">
          <table class="reg-table">
            <thead>
              <tr>
                <th>数据源</th>
                <th>类型</th>
                <th>状态</th>
                <th>最近运行</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in catalogRows" :key="row.crawler_key">
                <td>
                  <div class="src">
                    <span class="mark" :class="markTone(row.crawler_key)" aria-hidden="true">{{ markLetter(row) }}</span>
                    <span class="src-copy">
                      <strong>{{ row.name }}</strong>
                      <span class="meta mono">{{ row.crawler_key }}</span>
                    </span>
                  </div>
                </td>
                <td>
                  <span class="pill">{{ kindLabel(row) }}</span>
                </td>
                <td>
                  <span class="status" :class="sourceStatus(row).key">
                    <i class="status-dot" aria-hidden="true"></i>
                    {{ sourceStatus(row).label }}
                  </span>
                </td>
                <td class="meta mono" :title="lastRunExact(row)">{{ lastRunLabel(row) }}</td>
                <td class="act">
                  <button type="button" class="ghost config-btn" @click="openDrawer(row)">配置</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta empty-line">暂无已注册爬虫</p>
      </section>

      <div class="sched-grid">
        <section class="reg-card sched-card">
          <header class="sched-head">
            <div>
              <h3>新闻采集</h3>
              <p class="meta">本组统一调度，不是每个来源单独定时。</p>
            </div>
            <div class="sched-status">
              <span class="pill" :class="crawlLocked ? 'ok' : ''">{{ crawlLocked ? '调度运行中' : '未启动' }}</span>
              <span v-if="crawlActive" class="meta">本轮进行中</span>
              <span class="meta">下次 {{ formatNext(crawlStatus?.next_run_at) }}</span>
            </div>
          </header>

          <div v-if="crawlStatus && crawlStatus.llm_ready === false" class="form-error">
            {{ crawlStatus.llm_message || '尚未配置 LLM，无法启动采集。' }}
            <router-link to="/settings?tab=system">前往系统设置</router-link>
          </div>

          <div class="field">
            <label>本轮来源（仅已启用）</label>
            <div class="source-chip-row">
              <button
                type="button"
                v-for="row in newsEnabledRows"
                :key="row.crawler_key"
                class="source-chip"
                :class="{ on: crawlSelected.includes(row.crawler_key) }"
                :disabled="crawlLocked"
                :aria-pressed="crawlSelected.includes(row.crawler_key)"
                @click="toggleCrawlSource(row.crawler_key)"
              >
                <span class="chip-check" aria-hidden="true"></span>
                <span>{{ row.name || row.crawler_key }}</span>
              </button>
            </div>
            <p class="meta" v-if="!newsEnabledRows.length">请先启用至少一个新闻爬虫</p>
          </div>

          <div class="field">
            <label>节奏</label>
            <div class="seg">
              <button type="button" class="seg-btn" :class="{ on: crawlMode === 'manual' }" :disabled="crawlLocked" @click="crawlMode = 'manual'">手动</button>
              <button type="button" class="seg-btn" :class="{ on: crawlMode === 'interval' }" :disabled="crawlLocked" @click="crawlMode = 'interval'">间隔</button>
              <button type="button" class="seg-btn" :class="{ on: crawlMode === 'hourly' }" :disabled="crawlLocked" @click="crawlMode = 'hourly'">每小时</button>
              <button type="button" class="seg-btn" :class="{ on: crawlMode === 'daily' }" :disabled="crawlLocked" @click="crawlMode = 'daily'">每天</button>
            </div>
          </div>
          <div class="field" v-if="crawlMode === 'interval'">
            <label>间隔分钟（≥15）</label>
            <input type="number" min="15" max="1440" v-model.number="crawlInterval" :disabled="crawlLocked" />
          </div>
          <div class="field" v-if="crawlMode === 'daily'">
            <label>每天时刻</label>
            <input type="time" v-model="crawlDailyTime" :disabled="crawlLocked" />
          </div>
          <div class="row">
            <button type="button" :disabled="!canStartCrawl" @click="startCrawlSchedule">
              {{ crawlActionBusy && !crawlLocked ? '启动中…' : '启动' }}
            </button>
            <button type="button" class="secondary" :disabled="!crawlLocked || crawlActionBusy" @click="stopCrawlSchedule">停止</button>
            <button type="button" class="ghost" :disabled="crawlActionBusy || crawlLocked" @click="reprocessCrawlPending">补跑积压</button>
          </div>
          <p v-if="crawlActionMsg" class="meta" :class="{ 'form-error': crawlActionErr }">{{ crawlActionMsg }}</p>
        </section>

        <section class="reg-card sched-card">
          <header class="sched-head">
            <div>
              <h3>管线同步</h3>
              <p class="meta">本组统一调度，不是每个来源单独定时。</p>
            </div>
            <div class="sched-status">
              <span class="pill" :class="pipeRunning ? 'ok' : ''">{{ pipeRunning ? '定时运行中' : '未启动' }}</span>
              <span class="meta">节奏 {{ pipeModeLabel }}</span>
            </div>
          </header>

          <p v-if="!visionReady" class="form-error">
            请先在
            <router-link to="/settings?tab=system">系统设置</router-link>
            中启用视觉模型后再同步管线。
          </p>
          <p v-else class="meta">视觉模型：{{ visionModel || '已就绪' }}</p>

          <div class="field">
            <label>节奏</label>
            <div class="seg">
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'manual' }" @click="pipeMode = 'manual'">手动</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'interval' }" @click="pipeMode = 'interval'">间隔</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'daily' }" @click="pipeMode = 'daily'">每天</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'weekly' }" @click="pipeMode = 'weekly'">每周</button>
            </div>
          </div>
          <div class="field" v-if="pipeMode === 'interval'">
            <label>间隔分钟（≥15）</label>
            <input type="number" min="15" v-model.number="pipeInterval" />
          </div>
          <div class="field" v-if="pipeMode === 'daily' || pipeMode === 'weekly'">
            <label>时刻</label>
            <input type="time" v-model="pipeDailyTime" />
          </div>
          <div class="field" v-if="pipeMode === 'weekly'">
            <label>星期（0=周一 … 6=周日）</label>
            <input type="number" min="0" max="6" v-model.number="pipeWeeklyDay" />
          </div>
          <div class="row">
            <button type="button" :disabled="!visionReady || pipeBusy" @click="syncPipeline(false)">
              {{ pipeBusy ? '同步中…' : '立即同步管线' }}
            </button>
            <button type="button" class="secondary" :disabled="!visionReady || pipeBusy" @click="syncPipeline(true)">强制重跑视觉</button>
            <button type="button" class="secondary" :disabled="pipeBusy" @click="savePipeSchedule">保存调度</button>
            <button type="button" class="ghost" :disabled="pipeBusy || !pipeRunning" @click="stopPipeSchedule">停止定时</button>
          </div>
          <p v-if="pipeMsg" class="meta" :class="{ 'form-error': pipeErr }">{{ pipeMsg }}</p>
        </section>
      </div>
    </template>

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
          aria-labelledby="crawler-drawer-title"
        >
          <header class="drawer-head">
            <div class="src">
              <span class="mark" :class="markTone(draft.crawler_key)" aria-hidden="true">{{ markLetter(draft) }}</span>
              <span class="src-copy">
                <h3 id="crawler-drawer-title">{{ draft.name || draft.crawler_key }}</h3>
                <span class="meta mono">{{ draft.crawler_key }}</span>
              </span>
            </div>
            <button type="button" class="ghost drawer-close" @click="closeDrawer" :disabled="Boolean(crawlerBusy)">关闭</button>
          </header>

          <div class="drawer-body">
            <p v-if="draft.kind === 'pipeline'" class="meta">下载管线图片，再由视觉模型抽取。参数保存后下一轮生效。</p>
            <p v-else class="meta">参数保存后下一轮采集生效。</p>

            <label class="switch">
              <input type="checkbox" v-model="draft.enabled" :disabled="Boolean(crawlerBusy)" />
              <span class="switch-ui" aria-hidden="true"></span>
              <span>{{ draft.enabled ? '启用中' : '已停用' }}</span>
            </label>

            <template v-if="draft.kind !== 'pipeline'">
              <div class="field">
                <label for="crawler-pages">页数</label>
                <input id="crawler-pages" type="number" min="1" max="50" v-model.number="draft.page_count" :disabled="Boolean(crawlerBusy)" />
              </div>
              <div class="field">
                <label for="crawler-conc">并发</label>
                <input id="crawler-conc" type="number" min="1" max="20" v-model.number="draft.concurrency" :disabled="Boolean(crawlerBusy)" />
              </div>
              <label class="check-line">
                <input type="checkbox" v-model="draft.fetch_details" :disabled="Boolean(crawlerBusy)" />
                <span>抓取详情</span>
              </label>
            </template>

            <div v-else class="field">
              <label for="crawler-source-url">来源 URL</label>
              <input
                id="crawler-source-url"
                v-model="draft.source_url"
                type="url"
                placeholder="https://www.simcere.com/kxcx/yggx.aspx"
                :disabled="Boolean(crawlerBusy)"
              />
            </div>
          </div>

          <footer class="drawer-foot">
            <button type="button" class="secondary" :disabled="Boolean(crawlerBusy)" @click="closeDrawer">取消</button>
            <button type="button" :disabled="Boolean(crawlerBusy) || !draftDirty" @click="saveDraft">
              {{ crawlerBusy ? '保存中…' : '保存' }}
            </button>
          </footer>
        </aside>
      </div>

      <div
        v-if="feedbackDialog.open"
        class="feedback-mask"
        @click.self="closeFeedbackDialog"
      >
        <div
          class="feedback-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="crawler-feedback-title"
        >
          <h3 id="crawler-feedback-title" :class="{ bad: feedbackDialog.error }">{{ feedbackDialog.title }}</h3>
          <p>{{ feedbackDialog.message }}</p>
          <div class="feedback-dialog-actions">
            <button type="button" @click="closeFeedbackDialog">知道了</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { api } from '../../api'
import { formatDateTimeMinute, formatTime } from '../../format'

const MARK_TONES = ['pine', 'moss', 'brass']
const PIPE_MODE_LABEL = { manual: '手动', interval: '间隔', daily: '每天', weekly: '每周' }
const LIVE_STAGES = new Set(['', 'done', 'failed'])

const crawlerRows = ref([])
const crawlerSnapshot = ref({})
const crawlerLoading = ref(false)
const crawlerBusy = ref('')
const crawlerMsg = ref('')
const crawlerErr = ref(false)
const feedbackDialog = reactive({
  open: false,
  error: false,
  title: '',
  message: '',
})
const drawerOpen = ref(false)
const draft = reactive({
  crawler_key: '',
  name: '',
  kind: 'news',
  enabled: true,
  page_count: 1,
  concurrency: 1,
  fetch_details: false,
  source_url: '',
})

const crawlStatus = ref(null)
const crawlMode = ref('hourly')
const crawlDailyTime = ref('08:00')
const crawlInterval = ref(60)
const crawlSelected = ref([])
const crawlActionBusy = ref(false)
const crawlActionMsg = ref('')
const crawlActionErr = ref(false)

const visionReady = ref(false)
const visionModel = ref('')
const pipeSourceUrl = ref('https://www.simcere.com/kxcx/yggx.aspx')
const pipeSourceUrlSnap = ref(pipeSourceUrl.value)
const pipeMode = ref('manual')
const pipeInterval = ref(60)
const pipeDailyTime = ref('08:00')
const pipeWeeklyDay = ref(0)
const pipeRunning = ref(false)
const pipeBusy = ref(false)
const pipeMsg = ref('')
const pipeErr = ref(false)

const crawlerOnCount = computed(() => crawlerRows.value.filter((r) => r.enabled).length)
const crawlerOffCount = computed(() => crawlerRows.value.length - crawlerOnCount.value)
const newsCrawlerRows = computed(() => crawlerRows.value.filter((r) => (r.kind || 'news') !== 'pipeline'))
const catalogRows = computed(() => {
  const pipeline = crawlerRows.value.filter((r) => r.kind === 'pipeline')
  return [...newsCrawlerRows.value, ...pipeline]
})
const newsEnabledRows = computed(() => newsCrawlerRows.value.filter((r) => r.enabled))
const crawlLocked = computed(() => Boolean(crawlStatus.value?.running))
const crawlActive = computed(() => Boolean(crawlStatus.value?.active))
const pipeModeLabel = computed(() => PIPE_MODE_LABEL[pipeMode.value] || pipeMode.value)
const taskByKey = computed(() => {
  const map = {}
  for (const item of crawlStatus.value?.crawlers || []) {
    if (item?.key) map[item.key] = item
  }
  return map
})
const canStartCrawl = computed(() => {
  if (crawlLocked.value || crawlActionBusy.value) return false
  if (crawlStatus.value?.llm_ready === false) return false
  if (!crawlSelected.value.length) return false
  if (crawlMode.value === 'daily' && !crawlDailyTime.value) return false
  if (crawlMode.value === 'interval' && Number(crawlInterval.value) < 15) return false
  return true
})
const draftDirty = computed(() => isDraftDirty())

function openFeedbackDialog({ error = false, title, message }) {
  feedbackDialog.open = true
  feedbackDialog.error = Boolean(error)
  feedbackDialog.title = title
  feedbackDialog.message = message
}

function closeFeedbackDialog() {
  feedbackDialog.open = false
}

function onEscape(e) {
  if (e.key !== 'Escape') return
  if (feedbackDialog.open) {
    closeFeedbackDialog()
    return
  }
  if (drawerOpen.value && !crawlerBusy.value) closeDrawer()
}

function crawlerSnapKey(row) {
  return JSON.stringify({
    enabled: Boolean(row.enabled),
    page_count: Number(row.page_count),
    concurrency: Number(row.concurrency),
    fetch_details: Boolean(row.fetch_details),
  })
}

function rememberCrawlerSnapshot(rows) {
  const map = {}
  for (const row of rows) map[row.crawler_key] = crawlerSnapKey(row)
  crawlerSnapshot.value = map
}

function isDraftDirty() {
  const prev = crawlerSnapshot.value[draft.crawler_key]
  if (!prev) return false
  if (prev !== crawlerSnapKey(draft)) return true
  if ((draft.kind || 'news') === 'pipeline') {
    return String(draft.source_url || '').trim() !== String(pipeSourceUrlSnap.value || '').trim()
  }
  return false
}

function markTone(key) {
  let hash = 0
  const text = String(key || '')
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  return MARK_TONES[hash % MARK_TONES.length]
}

function markLetter(row) {
  const raw = String(row?.name || row?.crawler_key || '?').trim()
  const ch = Array.from(raw)[0] || '?'
  return /[a-z]/i.test(ch) ? ch.toUpperCase() : ch
}

function kindLabel(row) {
  return row?.kind === 'pipeline' ? '管线' : '新闻资讯'
}

function progressByCrawler() {
  const progress = crawlStatus.value?.progress || crawlStatus.value?.last_run?.progress
  const by = progress?.by_crawler
  return by && typeof by === 'object' ? by : {}
}

function sourceIsLive(key) {
  if (taskByKey.value[key]?.status === 'running') return true
  if (!crawlStatus.value?.active) return false
  const stage = String(progressByCrawler()[key]?.stage || '')
  return Boolean(stage) && !LIVE_STAGES.has(stage)
}

function sourceStatus(row) {
  if (!row.enabled) return { key: 'off', label: '已停用' }
  if (sourceIsLive(row.crawler_key)) return { key: 'run', label: '采集中' }
  const status = taskByKey.value[row.crawler_key]?.status
  if (status === 'failed' || status === 'aborted') return { key: 'fail', label: '最近失败' }
  return { key: 'on', label: '启用中' }
}

function lastRunLabel(row) {
  const end = taskByKey.value[row.crawler_key]?.end_time
  return end ? formatTime(end) : '—'
}

function lastRunExact(row) {
  const end = taskByKey.value[row.crawler_key]?.end_time
  if (!end) return ''
  return formatDateTimeMinute(end)
}

function formatNext(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  if (d.getTime() <= Date.now() + 5000) return '即将执行'
  return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function applyCrawlStatus(status) {
  crawlStatus.value = status
  if (!status) return
  crawlMode.value = status.schedule_mode || 'hourly'
  crawlDailyTime.value = status.daily_time || '08:00'
  crawlInterval.value = status.interval_minutes || 60
  const enabledKeys = newsEnabledRows.value.map((r) => r.crawler_key)
  const enabled = new Set(enabledKeys)
  if (status.crawler_keys?.length) {
    crawlSelected.value = status.crawler_keys.filter((k) => enabled.has(k))
  } else {
    crawlSelected.value = [...enabledKeys]
  }
  if (!crawlSelected.value.length) crawlSelected.value = [...enabledKeys]
}

function applyPipeConfig(cfg) {
  if (!cfg) return
  pipeRunning.value = Boolean(cfg.running)
  pipeMode.value = cfg.schedule_mode || 'manual'
  pipeInterval.value = cfg.interval_minutes || 60
  pipeDailyTime.value = cfg.daily_time || '08:00'
  pipeWeeklyDay.value = cfg.weekly_day ?? 0
  if (cfg.source_url) pipeSourceUrl.value = cfg.source_url
  pipeSourceUrlSnap.value = pipeSourceUrl.value
}

function toggleCrawlSource(key) {
  if (crawlLocked.value) return
  if (crawlSelected.value.includes(key)) {
    crawlSelected.value = crawlSelected.value.filter((k) => k !== key)
  } else {
    crawlSelected.value = [...crawlSelected.value, key]
  }
}

function openDrawer(row) {
  draft.crawler_key = row.crawler_key
  draft.name = row.name
  draft.kind = row.kind === 'pipeline' ? 'pipeline' : 'news'
  draft.enabled = Boolean(row.enabled)
  draft.page_count = Number(row.page_count)
  draft.concurrency = Number(row.concurrency)
  draft.fetch_details = Boolean(row.fetch_details)
  draft.source_url = pipeSourceUrl.value
  drawerOpen.value = true
}

function closeDrawer() {
  if (crawlerBusy.value) return
  drawerOpen.value = false
}

async function loadCrawlers() {
  crawlerMsg.value = ''
  crawlerErr.value = false
  crawlerLoading.value = true
  try {
    const [data, status, vs, pipeCfg] = await Promise.all([
      api.adminCrawlers(),
      api.crawlStatus().catch(() => null),
      api.pipelineVisionStatus().catch(() => null),
      api.pipelineCrawlConfig().catch(() => null),
    ])
    crawlerRows.value = Array.isArray(data) ? data : []
    rememberCrawlerSnapshot(crawlerRows.value)
    applyCrawlStatus(status)
    visionReady.value = Boolean(vs?.ready)
    visionModel.value = vs?.model || ''
    if (!vs?.ready && vs?.message) {
      pipeMsg.value = vs.message
      pipeErr.value = true
    }
    applyPipeConfig(pipeCfg)
  } catch (e) {
    crawlerErr.value = true
    crawlerMsg.value = e.message || '加载失败'
    crawlerRows.value = []
    crawlerSnapshot.value = {}
  } finally {
    crawlerLoading.value = false
  }
}

async function startCrawlSchedule() {
  crawlActionMsg.value = ''
  crawlActionErr.value = false
  crawlActionBusy.value = true
  try {
    const enabled = new Set(newsEnabledRows.value.map((r) => r.crawler_key))
    const status = await api.crawlStart({
      schedule_mode: crawlMode.value,
      daily_time: crawlMode.value === 'daily' ? crawlDailyTime.value : null,
      interval_minutes: crawlMode.value === 'interval' ? crawlInterval.value : null,
      crawler_keys: crawlSelected.value.filter((k) => enabled.has(k)),
    })
    applyCrawlStatus(status)
    crawlActionMsg.value = '采集调度已启动'
  } catch (e) {
    crawlActionErr.value = true
    crawlActionMsg.value = e.message || '启动失败'
  } finally {
    crawlActionBusy.value = false
  }
}

async function stopCrawlSchedule() {
  crawlActionBusy.value = true
  crawlActionMsg.value = ''
  crawlActionErr.value = false
  try {
    const status = await api.crawlStop()
    applyCrawlStatus(status)
    crawlActionMsg.value = '已停止采集调度'
  } catch (e) {
    crawlActionErr.value = true
    crawlActionMsg.value = e.message || '停止失败'
  } finally {
    crawlActionBusy.value = false
  }
}

async function reprocessCrawlPending() {
  crawlActionBusy.value = true
  crawlActionMsg.value = ''
  crawlActionErr.value = false
  try {
    const stats = await api.crawlReprocess(50)
    crawlActionMsg.value = `补跑完成：捞取 ${stats.pending ?? 0} 条，ready ${stats.ready_updated ?? stats.after_embedding ?? 0}`
  } catch (e) {
    crawlActionErr.value = true
    crawlActionMsg.value = e.message || '补跑失败'
  } finally {
    crawlActionBusy.value = false
  }
}

async function syncPipeline(force) {
  pipeBusy.value = true
  pipeMsg.value = ''
  pipeErr.value = false
  try {
    if (!visionReady.value) throw new Error('请先配置并启用视觉模型')
    const data = await api.pipelineSync({
      force: Boolean(force),
      source_url: pipeSourceUrl.value || undefined,
    })
    pipeMsg.value = data?.skipped
      ? '图片未变化，已跳过视觉抽取'
      : `同步完成：新建 ${data?.stats?.created ?? 0} · 更新 ${data?.stats?.updated ?? 0} · 消失 ${data?.stats?.removed ?? 0}`
  } catch (e) {
    pipeErr.value = true
    const detail = e.detail
    pipeMsg.value = (typeof detail === 'object' && detail?.message) || e.message || '同步失败'
  } finally {
    pipeBusy.value = false
  }
}

async function savePipeSchedule() {
  pipeBusy.value = true
  pipeMsg.value = ''
  pipeErr.value = false
  try {
    if (!visionReady.value && pipeMode.value !== 'manual') {
      throw new Error('启用定时前请先配置视觉模型')
    }
    const data = await api.updatePipelineCrawlConfig({
      running: pipeMode.value !== 'manual',
      schedule_mode: pipeMode.value,
      interval_minutes: pipeInterval.value,
      daily_time: pipeDailyTime.value,
      weekly_day: pipeWeeklyDay.value,
      source_url: pipeSourceUrl.value,
      crawler_keys: ['simcere_pipeline'],
    })
    applyPipeConfig(data)
    pipeMsg.value = '管线调度已保存'
  } catch (e) {
    pipeErr.value = true
    pipeMsg.value = e.message || '保存失败'
  } finally {
    pipeBusy.value = false
  }
}

async function stopPipeSchedule() {
  pipeBusy.value = true
  try {
    const data = await api.updatePipelineCrawlConfig({ running: false, schedule_mode: 'manual' })
    applyPipeConfig(data)
    pipeMsg.value = '已停止管线定时'
    pipeErr.value = false
  } catch (e) {
    pipeErr.value = true
    pipeMsg.value = e.message || '停止失败'
  } finally {
    pipeBusy.value = false
  }
}

async function saveCrawler(row) {
  crawlerBusy.value = row.crawler_key
  crawlerMsg.value = ''
  crawlerErr.value = false
  try {
    const data = await api.updateAdminCrawler(row.crawler_key, {
      enabled: Boolean(draft.enabled),
      page_count: Number(draft.page_count),
      concurrency: Number(draft.concurrency),
      fetch_details: Boolean(draft.fetch_details),
    })
    Object.assign(row, data)
    crawlerSnapshot.value = {
      ...crawlerSnapshot.value,
      [row.crawler_key]: crawlerSnapKey(row),
    }
    if ((row.kind || 'news') === 'pipeline') {
      const cfg = await api.updatePipelineCrawlConfig({
        running: pipeRunning.value,
        schedule_mode: pipeMode.value,
        interval_minutes: pipeInterval.value,
        daily_time: pipeDailyTime.value,
        weekly_day: pipeWeeklyDay.value,
        source_url: draft.source_url,
        crawler_keys: [row.crawler_key],
      })
      applyPipeConfig(cfg)
    }
    openFeedbackDialog({
      title: `已保存「${row.name || row.crawler_key}」`,
      message: (row.kind || 'news') === 'pipeline'
        ? '启用状态与来源 URL 已写入；下一轮同步生效。'
        : '参数将在下一轮采集生效。',
    })
    return true
  } catch (e) {
    openFeedbackDialog({
      error: true,
      title: '爬虫配置保存失败',
      message: e.message || '保存失败',
    })
    return false
  } finally {
    crawlerBusy.value = ''
  }
}

async function saveDraft() {
  const row = crawlerRows.value.find((item) => item.crawler_key === draft.crawler_key)
  if (!row || !draftDirty.value || crawlerBusy.value) return
  const ok = await saveCrawler(row)
  if (ok) drawerOpen.value = false
}

onMounted(() => {
  window.addEventListener('keydown', onEscape)
  loadCrawlers()
})
onUnmounted(() => window.removeEventListener('keydown', onEscape))
</script>

<style scoped>
.reg-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
}
.reg-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px 28px;
  flex-wrap: wrap;
}
.reg-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h1);
  color: var(--pine);
  font-weight: 700;
}
.reg-desc { margin: 6px 0 0; color: var(--ink-mute); font-size: var(--fs-sm); max-width: 62ch; }
.reg-hero-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.reg-count { margin: 0; color: var(--ink-soft); font-size: var(--fs-sm); }
.reg-count strong {
  font-family: var(--font-serif);
  font-size: 28px;
  color: var(--pine);
  font-weight: 700;
  margin-right: 4px;
}
.unsaved { color: var(--brass); font-weight: 700; }
.reg-monitor {
  margin-top: 4px;
  font-size: var(--fs-sm);
  font-weight: 650;
  color: var(--pine);
}
.form-error { color: var(--clay); margin: 0; }
.mono { font-family: var(--font-mono); }

.reg-card {
  background: color-mix(in srgb, var(--paper-deep) 55%, transparent);
  border: 1px solid var(--rule);
  border-radius: var(--r-lg);
  min-width: 0;
  max-width: 100%;
}
.table-wrap {
  width: 0;
  min-width: 100%;
  max-width: 100%;
  overflow-x: auto;
}
.reg-table { width: 100%; border-collapse: collapse; min-width: 640px; }
.reg-table th {
  padding: 12px 14px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  border-bottom: 1px solid var(--rule);
}
.reg-table td {
  padding: 10px 14px;
  height: 56px;
  border-bottom: 1px solid var(--rule);
  vertical-align: middle;
}
.reg-table tbody tr:last-child td { border-bottom: none; }
.reg-table tbody tr:hover td { background: var(--wash); }
.empty-line { margin: 0; padding: 22px 16px; }

.src { display: flex; align-items: center; gap: 12px; min-width: 0; }
.src-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.src-copy strong { color: var(--ink); font-weight: 650; }
.mark {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex: none;
  color: var(--paper);
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 16px;
}
.mark.pine { background: var(--pine); }
.mark.moss { background: var(--moss); }
.mark.brass { background: var(--brass); }

.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-sm);
  font-weight: 650;
  white-space: nowrap;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.status.on { color: var(--moss); }
.status.off { color: var(--ink-mute); font-weight: 600; }
.status.fail { color: var(--brass); }
.status.run { color: var(--pine); }
.status.run .status-dot {
  background: var(--lime);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--lime) 70%, transparent);
  animation: pulse 1.6s ease-out infinite;
}
@keyframes pulse {
  70% { box-shadow: 0 0 0 6px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}

.act { width: 1%; text-align: right; white-space: nowrap; }
.config-btn {
  padding: 6px 8px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.sched-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr));
  gap: 16px;
  min-width: 0;
}
.sched-card { padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 12px; }
.sched-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px 16px;
  flex-wrap: wrap;
}
.sched-head h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  color: var(--ink);
}
.sched-head .meta { margin: 4px 0 0; }
.sched-status { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; }
.field { display: flex; flex-direction: column; gap: 8px; }
.field label { font-size: var(--fs-xs); font-weight: 700; letter-spacing: 0.08em; color: var(--ink-mute); }
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn { background: transparent; color: var(--pine); padding: 8px 14px; }
.seg-btn.on {
  background: color-mix(in srgb, var(--moss) 18%, var(--paper));
  border-color: color-mix(in srgb, var(--moss) 55%, var(--pine));
  color: var(--pine);
}
.seg-btn.on:hover:not(:disabled) {
  background: color-mix(in srgb, var(--moss) 26%, var(--paper));
  border-color: var(--moss);
  color: var(--pine);
  box-shadow: none;
}
.sched-card > .row > button:not(.secondary):not(.ghost) {
  background: var(--moss);
  border-color: var(--moss);
}
.sched-card > .row > button:not(.secondary):not(.ghost):hover:not(:disabled) {
  background: color-mix(in srgb, var(--moss) 78%, var(--pine));
  border-color: color-mix(in srgb, var(--moss) 78%, var(--pine));
}
.source-chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  color: var(--ink-soft);
  border: 1.5px solid var(--rule-strong);
  border-radius: var(--r-sm);
  padding: 7px 12px 7px 10px;
  font-size: var(--fs-sm);
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: background var(--dur-fast), border-color var(--dur-fast), color var(--dur-fast), box-shadow var(--dur-fast);
}
.source-chip:hover:not(:disabled):not(.on) {
  border-color: var(--pine);
  color: var(--pine);
  background: var(--wash);
  box-shadow: none;
  transform: none;
}
.chip-check {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1.5px solid var(--rule-strong);
  background: var(--paper);
  flex: none;
  position: relative;
}
.source-chip.on {
  border-color: color-mix(in srgb, var(--moss) 55%, var(--pine));
  background: color-mix(in srgb, var(--moss) 18%, var(--paper));
  color: var(--pine);
  font-weight: 700;
  box-shadow: none;
}
.source-chip.on:hover:not(:disabled) {
  background: color-mix(in srgb, var(--moss) 26%, var(--paper));
  border-color: var(--moss);
  color: var(--pine);
  transform: none;
}
.source-chip.on .chip-check {
  border-color: var(--moss);
  background: var(--moss);
}
.source-chip.on .chip-check::after {
  content: "";
  position: absolute;
  left: 4px;
  top: 1px;
  width: 4px;
  height: 8px;
  border: solid var(--paper);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}
.source-chip:disabled { opacity: 0.55; cursor: not-allowed; }

.drawer-mask,
.feedback-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(28, 36, 32, 0.42);
}
.drawer-mask { display: flex; justify-content: flex-end; }
.feedback-mask {
  z-index: 70;
  display: grid;
  place-items: center;
  padding: 24px;
}
.drawer {
  width: min(420px, 100%);
  height: 100%;
  background: var(--paper);
  border-left: 1px solid var(--rule);
  box-shadow: var(--shadow-md);
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.drawer-head,
.drawer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--rule);
}
.drawer-foot { border-bottom: none; border-top: 1px solid var(--rule); justify-content: flex-end; }
.drawer-head h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  color: var(--ink);
}
.drawer-close { padding: 6px 8px; }
.drawer-body {
  flex: 1;
  overflow: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.switch,
.check-line {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: var(--fs-sm);
  color: var(--ink);
}
.switch input,
.check-line input { position: absolute; opacity: 0; width: 1px; height: 1px; }
.switch { position: relative; }
.check-line { position: relative; }
.switch-ui {
  width: 36px;
  height: 20px;
  border-radius: 999px;
  background: var(--paper-deep);
  border: 1px solid var(--rule-strong);
  position: relative;
  flex: none;
}
.switch-ui::after {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--ink-mute);
  transition: transform var(--dur-fast) var(--ease-out), background var(--dur-fast);
}
.switch input:checked + .switch-ui {
  background: color-mix(in srgb, var(--moss) 22%, var(--paper));
  border-color: var(--moss);
}
.switch input:checked + .switch-ui::after {
  transform: translateX(16px);
  background: var(--moss);
}
.switch input:focus-visible + .switch-ui,
.check-line input:focus-visible + span {
  outline: 2px solid var(--pine);
  outline-offset: 2px;
}
.check-line input + span { padding-left: 22px; }
.check-line input + span::before {
  content: "";
  position: absolute;
  left: 0;
  top: 2px;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid var(--rule-strong);
  background: var(--paper);
}
.check-line input:checked + span::before {
  background: var(--pine);
  border-color: var(--pine);
  box-shadow: inset 0 0 0 2px var(--paper);
}

.feedback-dialog {
  width: min(360px, 100%);
  padding: 20px 22px;
  border: 1px solid var(--rule);
  border-radius: 10px;
  background: var(--paper);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.feedback-dialog h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  color: var(--pine);
}
.feedback-dialog h3.bad { color: var(--clay); }
.feedback-dialog p {
  margin: 0;
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--ink-soft);
}
.feedback-dialog-actions { display: flex; justify-content: flex-end; margin-top: 6px; }
.feedback-dialog-actions button { padding: 6px 14px; font-size: 13px; }

@media (max-width: 720px) {
  .reg-hero-side { align-items: flex-start; }
  .drawer { width: 100%; }
}
</style>
