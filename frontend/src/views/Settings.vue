<template>
  <div>
    <SystemConfigPanel v-if="activeTab === 'system'" />

    <!-- 爬虫注册表 + 调度 -->
    <section v-show="activeTab === 'crawlers'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>爬虫注册表</h3><span class="rule"></span></div>
      <div class="crawler-status" :class="{ warn: crawlerOffCount > 0 }">
        <strong>已启用 {{ crawlerOnCount }} / 共 {{ crawlerRows.length }}</strong>
        <span v-if="crawlerOffCount" class="meta">停用 {{ crawlerOffCount }} 个</span>
        <span v-if="crawlerDirtyCount" class="dirty-tag">{{ crawlerDirtyCount }} 行待保存</span>
      </div>
      <p class="meta hint">
        在此启停来源与采集调度；运行态与按源进度见
        <router-link to="/monitor">爬虫监控</router-link>。
        参数<strong>保存后下一轮</strong>生效。
      </p>
      <div v-if="crawlerLoading" class="meta">加载中…</div>
      <template v-else>
        <h4 class="sub-h">新闻爬虫</h4>
        <div class="table-wrap" v-if="newsCrawlerRows.length">
          <table class="cfg-table crawler-table">
            <thead>
              <tr>
                <th>来源</th><th>启用</th><th>页数</th><th>并发</th><th>抓详情</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in newsCrawlerRows"
                :key="row.crawler_key"
                :class="{ 'is-off': !row.enabled, 'is-dirty': isCrawlerDirty(row) }"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <div class="meta mono">{{ row.crawler_key }}</div>
                </td>
                <td>
                  <label class="enable-cell">
                    <input type="checkbox" v-model="row.enabled" />
                    <span :class="row.enabled ? 'on' : 'off'">{{ row.enabled ? '启用中' : '已停用' }}</span>
                  </label>
                </td>
                <td><input type="number" min="1" max="50" v-model.number="row.page_count" class="num" /></td>
                <td><input type="number" min="1" max="20" v-model.number="row.concurrency" class="num" /></td>
                <td><input type="checkbox" v-model="row.fetch_details" /></td>
                <td class="crawler-save-cell">
                  <button
                    type="button"
                    class="secondary"
                    :disabled="crawlerBusy === row.crawler_key || !isCrawlerDirty(row)"
                    @click="saveCrawler(row)"
                  >{{ crawlerBusy === row.crawler_key ? '…' : '保存' }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">暂无新闻爬虫</p>

        <h4 class="sub-h">新闻采集调度</h4>
        <div class="crawl-status">
          <span class="pill" :class="crawlLocked ? 'ok' : ''">{{ crawlLocked ? '调度运行中' : '未启动' }}</span>
          <span class="meta" v-if="crawlActive">本轮进行中</span>
        </div>
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
              @click="toggleCrawlSource(row.crawler_key)"
            >{{ row.name || row.crawler_key }}</button>
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

        <h4 class="sub-h">管线爬虫</h4>
        <div class="table-wrap" v-if="pipelineCrawlerRows.length">
          <table class="cfg-table crawler-table">
            <thead>
              <tr>
                <th>来源</th><th>启用</th><th>来源 URL</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in pipelineCrawlerRows"
                :key="row.crawler_key"
                :class="{ 'is-off': !row.enabled, 'is-dirty': isCrawlerDirty(row) }"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <div class="meta mono">{{ row.crawler_key }}</div>
                  <div class="meta">下载管线图片 → 视觉模型抽取</div>
                </td>
                <td>
                  <label class="enable-cell">
                    <input type="checkbox" v-model="row.enabled" />
                    <span :class="row.enabled ? 'on' : 'off'">{{ row.enabled ? '启用中' : '已停用' }}</span>
                  </label>
                </td>
                <td>
                  <input
                    v-model="pipeSourceUrl"
                    type="url"
                    class="wide"
                    placeholder="https://www.simcere.com/kxcx/yggx.aspx"
                  />
                </td>
                <td class="crawler-save-cell">
                  <button
                    type="button"
                    class="secondary"
                    :disabled="crawlerBusy === row.crawler_key || !isCrawlerDirty(row)"
                    @click="saveCrawler(row)"
                  >{{ crawlerBusy === row.crawler_key ? '…' : '保存' }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">暂无管线爬虫</p>

        <h4 class="sub-h">管线同步调度</h4>
        <p v-if="!visionReady" class="form-error">
          请先在
          <router-link to="/settings?tab=system">系统设置</router-link>
          中启用视觉模型后再同步管线。
        </p>
        <p v-else class="meta">视觉模型：{{ visionModel || '已就绪' }}</p>
        <div class="field">
          <label>节奏</label>
          <div class="pipe-schedule-row">
            <div class="seg">
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'manual' }" @click="pipeMode = 'manual'">手动</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'interval' }" @click="pipeMode = 'interval'">间隔</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'daily' }" @click="pipeMode = 'daily'">每天</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'weekly' }" @click="pipeMode = 'weekly'">每周</button>
            </div>
            <div class="row pipe-actions">
              <button type="button" :disabled="!visionReady || pipeBusy" @click="syncPipeline(false)">
                {{ pipeBusy ? '同步中…' : '立即同步管线' }}
              </button>
              <button type="button" class="secondary" :disabled="!visionReady || pipeBusy" @click="syncPipeline(true)">强制重跑视觉</button>
              <button type="button" class="secondary" :disabled="pipeBusy" @click="savePipeSchedule">保存调度</button>
              <button type="button" class="ghost" :disabled="pipeBusy || !pipeRunning" @click="stopPipeSchedule">停止定时</button>
            </div>
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
        <p v-if="pipeMsg" class="meta" :class="{ 'form-error': pipeErr }">{{ pipeMsg }}</p>
        <p class="meta">定时状态：{{ pipeRunning ? `运行中（${pipeMode}）` : '未启动' }}</p>
      </template>
      <p v-if="crawlerMsg" class="meta" :class="{ 'form-error': crawlerErr }">{{ crawlerMsg }}</p>
    </section>

    <Teleport to="body">
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

    <!-- 关键词 -->
    <section v-show="activeTab === 'keywords'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>过滤关键词</h3><span class="rule"></span></div>
      <p class="meta hint">修改后下一轮采集/过滤立即生效（服务端缓存已清）。首次启动会从 keywords.yaml 导入。</p>

      <div class="kw-toolbar">
        <div class="seg">
          <button type="button" class="seg-btn" :class="{ on: kwCategory === '靶点' }" @click="setKwCategory('靶点')">靶点</button>
          <button type="button" class="seg-btn" :class="{ on: kwCategory === '公司' }" @click="setKwCategory('公司')">公司</button>
        </div>
        <input class="search" type="search" placeholder="搜索规范名或别名" v-model="kwQuery" @keyup.enter="loadKeywords(1)" />
        <button type="button" class="secondary" :disabled="kwBusy" @click="loadKeywords(1)">搜索</button>
      </div>

      <div class="kw-new">
        <input type="text" placeholder="新规范名" v-model="kwNew.canonical" />
        <input type="text" placeholder="别名，逗号分隔" v-model="kwNew.aliasesText" />
        <button type="button" :disabled="kwBusy || !kwNew.canonical.trim()" @click="createKeyword">新增</button>
      </div>

      <div class="table-wrap" v-if="kwItems.length">
        <table class="cfg-table">
          <thead>
            <tr>
              <th>规范名</th>
              <th>别名</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in kwItems" :key="item.id">
              <td><input type="text" v-model="item.canonical" class="wide" /></td>
              <td><input type="text" v-model="item.aliasesText" class="wide" placeholder="逗号分隔" /></td>
              <td class="actions">
                <button type="button" class="secondary" :disabled="kwBusy" @click="saveKeyword(item)">保存</button>
                <button type="button" class="ghost danger-ghost" :disabled="kwBusy" @click="removeKeyword(item)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!kwBusy" class="empty">
        <div class="empty-title">暂无关键词</div>
        <p>可新增，或从 YAML 重新导入。</p>
      </div>

      <div class="row kw-pager">
        <button type="button" class="secondary" :disabled="kwPage <= 1 || kwBusy" @click="loadKeywords(kwPage - 1)">上一页</button>
        <span class="meta">第 {{ kwPage }} 页 · 共 {{ kwTotal }} 条</span>
        <button type="button" class="secondary" :disabled="kwPage * kwPageSize >= kwTotal || kwBusy" @click="loadKeywords(kwPage + 1)">下一页</button>
        <button type="button" class="ghost" :disabled="kwBusy" @click="reimportKeywords">从 YAML 重新导入</button>
      </div>
      <p v-if="kwMsg" class="meta" :class="{ 'form-error': kwErr }">{{ kwMsg }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import SystemConfigPanel from '../components/settings/SystemConfigPanel.vue'

const route = useRoute()
const router = useRouter()

const LEGACY_SYSTEM_TABS = new Set(['models', 'rag', 'mail'])
const tabIds = new Set(['system', 'crawlers', 'keywords', ...LEGACY_SYSTEM_TABS])

function normalizeTab(raw) {
  if (!raw || typeof raw !== 'string') return 'system'
  if (LEGACY_SYSTEM_TABS.has(raw)) return 'system'
  if (tabIds.has(raw)) return raw
  return 'system'
}

const activeTab = ref(normalizeTab(route.query.tab))

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

function openFeedbackDialog({ error = false, title, message }) {
  feedbackDialog.open = true
  feedbackDialog.error = Boolean(error)
  feedbackDialog.title = title
  feedbackDialog.message = message
}

function closeFeedbackDialog() {
  feedbackDialog.open = false
}

function onFeedbackEsc(e) {
  if (e.key === 'Escape' && feedbackDialog.open) closeFeedbackDialog()
}

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
const crawlerDirtyCount = computed(() => crawlerRows.value.filter((r) => isCrawlerDirty(r)).length)
const newsCrawlerRows = computed(() => crawlerRows.value.filter((r) => (r.kind || 'news') === 'news'))
const pipelineCrawlerRows = computed(() => crawlerRows.value.filter((r) => r.kind === 'pipeline'))
const newsEnabledRows = computed(() => newsCrawlerRows.value.filter((r) => r.enabled))
const crawlLocked = computed(() => Boolean(crawlStatus.value?.running))
const crawlActive = computed(() => Boolean(crawlStatus.value?.active))
const canStartCrawl = computed(() => {
  if (crawlLocked.value || crawlActionBusy.value) return false
  if (crawlStatus.value?.llm_ready === false) return false
  if (!crawlSelected.value.length) return false
  if (crawlMode.value === 'daily' && !crawlDailyTime.value) return false
  if (crawlMode.value === 'interval' && Number(crawlInterval.value) < 15) return false
  return true
})

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

function isPipeSourceDirty() {
  return String(pipeSourceUrl.value || '').trim() !== String(pipeSourceUrlSnap.value || '').trim()
}

function isCrawlerDirty(row) {
  const prev = crawlerSnapshot.value[row.crawler_key]
  if (!prev) return false
  if (prev !== crawlerSnapKey(row)) return true
  if ((row.kind || 'news') === 'pipeline') return isPipeSourceDirty()
  return false
}

const kwCategory = ref('靶点')
const kwQuery = ref('')
const kwItems = ref([])
const kwPage = ref(1)
const kwPageSize = 20
const kwTotal = ref(0)
const kwBusy = ref(false)
const kwMsg = ref('')
const kwErr = ref(false)
const kwNew = reactive({ canonical: '', aliasesText: '' })
const loaded = reactive({ crawlers: false, keywords: false })

function parseAliases(text) {
  return String(text || '')
    .split(/[,，;；\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
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
    loaded.crawlers = true
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

function ensureTabLoaded(tab) {
  if (tab === 'crawlers' && !loaded.crawlers) loadCrawlers()
  if (tab === 'keywords' && !loaded.keywords) loadKeywords(1)
}

async function saveCrawler(row) {
  crawlerBusy.value = row.crawler_key
  crawlerMsg.value = ''
  crawlerErr.value = false
  try {
    const data = await api.updateAdminCrawler(row.crawler_key, {
      enabled: row.enabled,
      page_count: row.page_count,
      concurrency: row.concurrency,
      fetch_details: row.fetch_details,
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
        source_url: pipeSourceUrl.value,
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
  } catch (e) {
    openFeedbackDialog({
      error: true,
      title: '爬虫配置保存失败',
      message: e.message || '保存失败',
    })
  } finally {
    crawlerBusy.value = ''
  }
}

function setKwCategory(cat) {
  kwCategory.value = cat
  loadKeywords(1)
}

async function loadKeywords(page = 1) {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    const data = await api.adminKeywords({
      category: kwCategory.value,
      q: kwQuery.value.trim(),
      page,
      page_size: kwPageSize,
    })
    kwItems.value = (data.items || []).map((item) => ({
      ...item,
      aliasesText: (item.aliases || []).join(', '),
    }))
    kwTotal.value = data.total || 0
    kwPage.value = data.page || page
    loaded.keywords = true
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '加载失败'
  } finally {
    kwBusy.value = false
  }
}

async function createKeyword() {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.createAdminKeyword({
      category: kwCategory.value,
      canonical: kwNew.canonical.trim(),
      aliases: parseAliases(kwNew.aliasesText),
    })
    kwNew.canonical = ''
    kwNew.aliasesText = ''
    kwMsg.value = '已新增'
    await loadKeywords(1)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '新增失败'
  } finally {
    kwBusy.value = false
  }
}

async function saveKeyword(item) {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.updateAdminKeyword(item.id, {
      category: kwCategory.value,
      canonical: item.canonical.trim(),
      aliases: parseAliases(item.aliasesText),
    })
    kwMsg.value = '已保存'
    await loadKeywords(kwPage.value)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '保存失败'
  } finally {
    kwBusy.value = false
  }
}

async function removeKeyword(item) {
  if (!window.confirm(`删除「${item.canonical}」？`)) return
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.deleteAdminKeyword(item.id)
    kwMsg.value = '已删除'
    await loadKeywords(kwPage.value)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '删除失败'
  } finally {
    kwBusy.value = false
  }
}

async function reimportKeywords() {
  const overwrite = kwTotal.value > 0
  if (overwrite && !window.confirm('将清空当前过滤关键词并从 keywords.yaml 重新导入，继续？')) {
    return
  }
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    const data = await api.reimportAdminKeywords(overwrite)
    kwMsg.value = `已导入 ${data.inserted} 条`
    await loadKeywords(1)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '导入失败'
  } finally {
    kwBusy.value = false
  }
}

watch(activeTab, (tab) => {
  const next = normalizeTab(tab)
  if (next !== tab) {
    activeTab.value = next
    return
  }
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab } })
  }
  ensureTabLoaded(tab)
})

watch(
  () => route.query.tab,
  (tab) => {
    const next = normalizeTab(typeof tab === 'string' ? tab : '')
    if (activeTab.value !== next) activeTab.value = next
  },
)

onMounted(() => {
  window.addEventListener('keydown', onFeedbackEsc)
  if (normalizeTab(route.query.tab) !== route.query.tab) {
    router.replace({ query: { ...route.query, tab: activeTab.value } })
  }
  ensureTabLoaded(activeTab.value)
})
onUnmounted(() => window.removeEventListener('keydown', onFeedbackEsc))
</script>

<style scoped>
.sub-h {
  margin: 18px 0 10px;
  font-size: var(--fs-sm);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
}
.status-label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
  margin-bottom: 4px;
}
.status-warn { margin: 8px 0 0; color: var(--clay); font-size: var(--fs-sm); line-height: 1.45; }
.form-error { color: var(--clay); margin: 8px 0 0; }
.mono { font-family: var(--font-mono); }
.crawler-status {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  margin: 12px 0 8px;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--lime) 18%, transparent);
  color: var(--pine);
  font-size: var(--fs-sm);
}
.crawler-status.warn {
  background: color-mix(in srgb, var(--brass, #9a6b2f) 12%, var(--paper));
  color: var(--ink);
}
.crawler-status .dirty-tag {
  font-size: var(--fs-xs);
  font-weight: 700;
  color: var(--clay);
}
.cfg-table { width: 100%; border-collapse: collapse; }
.cfg-table th, .cfg-table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line, #e6e0d6); vertical-align: middle; }
.cfg-table .num { width: 72px; }
.cfg-table .wide { width: 100%; min-width: 140px; }
.col-hint {
  font-size: 10px;
  font-weight: 500;
  color: var(--ink-mute);
  letter-spacing: 0;
  text-transform: none;
  margin-top: 2px;
}
.crawler-table tbody tr.is-off {
  opacity: 0.62;
  box-shadow: inset 3px 0 0 var(--ink-mute);
}
.crawler-table tbody tr.is-dirty {
  background: color-mix(in srgb, var(--brass, #9a6b2f) 8%, transparent);
}
.enable-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: var(--fs-xs);
}
.enable-cell .on { color: var(--moss); font-weight: 650; }
.enable-cell .off { color: var(--ink-mute); }
.crawler-save-cell {
  width: 88px;
  white-space: nowrap;
  vertical-align: middle;
}
.crawler-save-cell .secondary {
  min-width: 64px;
}
.feedback-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(28, 36, 32, 0.42);
}
.feedback-dialog {
  width: min(360px, 100%);
  padding: 20px 22px;
  border: 1px solid var(--rule, var(--line));
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
.feedback-dialog-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}
.feedback-dialog-actions button {
  padding: 6px 14px;
  font-size: 13px;
}
.dirty-dot {
  font-size: 10px;
  font-weight: 700;
  color: var(--clay);
}
.actions { white-space: nowrap; display: flex; gap: 8px; }
.kw-toolbar, .kw-new, .kw-pager { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
.kw-toolbar .search { flex: 1; min-width: 160px; }
.kw-new input { flex: 1; min-width: 140px; }

.crawl-status {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  margin: 8px 0 14px;
}
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: transparent;
  color: var(--pine);
  padding: 8px 14px;
}
.seg-btn.on { background: var(--pine); color: var(--paper); }
.source-chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.source-chip {
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--line);
  border-radius: var(--r-sm);
  padding: 6px 12px;
  font-size: var(--fs-sm);
  cursor: pointer;
}
.source-chip.on {
  border-color: var(--pine);
  background: color-mix(in srgb, var(--pine) 10%, var(--paper));
  color: var(--pine);
  font-weight: 650;
}
.source-chip:disabled { opacity: 0.75; cursor: not-allowed; }
.pipe-schedule-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.pipe-actions { margin: 0; flex-wrap: wrap; }
</style>
