<template>
  <div>
    <header class="ed-head reveal">
      <div class="head-row">
        <div>
          <div class="ed-kicker">Newsroom · 情报目录</div>
          <h1 class="ed-title">情报流</h1>
          <p class="ed-lede">经关键词命中、LLM 相关性过滤与聚类归事件的多源新闻，按期次排列。</p>
        </div>
        <button class="secondary" :disabled="loading" @click="reload">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" :class="{ spinning: loading }">
            <path d="M21 12a9 9 0 1 1-2.6-6.3" /><path d="M21 3v6h-6" />
          </svg>
          刷新
        </button>
      </div>
    </header>

    <div class="filters">
      <input
        v-model="keyword"
        type="search"
        placeholder="搜索标题或摘要"
        aria-label="搜索新闻"
        @keydown.enter="applySearch"
      />
      <button class="secondary" :disabled="loading" @click="applySearch">搜索</button>
      <div class="picker" ref="sourcePicker">
        <button
          type="button"
          class="picker-btn"
          :aria-expanded="sourceOpen"
          @click="sourceOpen = !sourceOpen; dateOpen = false"
        >{{ sourceLabel }}</button>
        <div v-if="sourceOpen" class="picker-menu" role="group" aria-label="来源">
          <label v-for="src in sources" :key="src.key" class="picker-option">
            <input v-model="selectedSources" type="checkbox" :value="src.key" />
            {{ src.label }}
          </label>
        </div>
      </div>
      <div class="picker" ref="datePicker">
        <button
          type="button"
          class="picker-btn"
          :aria-expanded="dateOpen"
          @click="toggleDate"
        >{{ dateLabel }}</button>
        <div v-if="dateOpen" class="picker-menu cal" :class="{ up: dateOpensUp }" role="dialog" aria-label="更新时间">
          <div class="cal-head">
            <button type="button" class="cal-nav" aria-label="上个月" @click="shiftMonth(-1)">‹</button>
            <span class="cal-title">{{ viewYear }} 年 {{ viewMonth }} 月</span>
            <button type="button" class="cal-nav" aria-label="下个月" @click="shiftMonth(1)">›</button>
          </div>
          <div class="cal-week">
            <span v-for="day in weekdays" :key="day">{{ day }}</span>
          </div>
          <div class="cal-grid">
            <button
              v-for="(cell, index) in calendarCells"
              :key="index"
              type="button"
              class="cal-day"
              :class="dayClass(cell)"
              :disabled="!cell"
              @click="cell && pickDay(cell)"
            >{{ cell ? cell.getDate() : '' }}</button>
          </div>
          <button type="button" class="cal-clear" @click="clearDates">清除</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="card empty">
      <div class="empty-title">暂时无法加载</div>
      <p>请稍后重试。</p>
      <button class="secondary" @click="reload">重试</button>
    </div>

    <!-- 骨架屏 -->
    <template v-else-if="loading && !items.length">
      <div v-for="i in 5" :key="i" class="entry skeleton-entry">
        <div class="skeleton" style="width:28px;height:28px"></div>
        <div style="flex:1">
          <div class="skeleton" style="width:120px;height:11px"></div>
          <div class="skeleton" style="width:65%;height:20px;margin-top:10px"></div>
          <div class="skeleton" style="width:90%;height:13px;margin-top:10px"></div>
        </div>
      </div>
    </template>

    <!-- 空状态 -->
    <div v-else-if="!items.length" class="card empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
        <path d="M4 5h13a2 2 0 0 1 2 2v10a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2z" />
        <path d="M8 9h7M8 13h7" />
      </svg>
      <div class="empty-title">{{ filtered ? '没有符合条件的新闻' : '暂无新闻' }}</div>
      <p v-if="filtered">换一个关键词、来源或时间再试。</p>
      <p v-else-if="session.user?.role === 'admin'">到<router-link to="/monitor">系统监控</router-link>选择爬虫并启动采集，处理完成后会出现在这里。</p>
    </div>

    <!-- 目录式条目 -->
    <div v-else class="toc">
      <router-link
        v-for="(n, i) in items"
        :key="n.id"
        :to="`/news/${n.id}`"
        class="entry reveal"
        :style="{ '--reveal-delay': i * 45 + 'ms' }"
      >
        <span class="entry-no">{{ String((page - 1) * 20 + i + 1).padStart(2, '0') }}</span>
        <span class="entry-body">
          <span class="entry-meta">
            <b>{{ crawlerLabel(n.crawler) }}</b>
            <i class="dot"></i>
            <span class="time">{{ formatTime(n.publish_time) }}</span>
          </span>
          <h3 class="entry-title">{{ n.title }}</h3>
          <p class="entry-abstract">{{ n.abstract || '暂无摘要' }}</p>
        </span>
        <span class="entry-go" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.8" stroke-linecap="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </span>
      </router-link>
    </div>

    <!-- 分页 -->
    <nav class="pager reveal" v-if="total > 0">
      <button class="ghost" :disabled="page <= 1" @click="go(page - 1)">← 上一页</button>
      <span class="page-indicator">
        第 <b>{{ page }}</b> / {{ totalPages }} 期 · 共 {{ total }} 条
      </span>
      <button class="ghost" :disabled="page >= totalPages" @click="go(page + 1)">下一页 →</button>
    </nav>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'
import { session } from '../session'
import { useAsync } from '../composables'
import { crawlerLabel, crawlerSources, formatTime } from '../format'

const sources = crawlerSources
const items = ref([])
const page = ref(1)
const total = ref(0)
const keyword = ref('')
const appliedKeyword = ref('')
const selectedSources = ref([])
const appliedSources = ref([])
const dateFrom = ref('')
const dateTo = ref('')
const appliedDateFrom = ref('')
const appliedDateTo = ref('')
const sourceOpen = ref(false)
const sourcePicker = ref(null)
const dateOpen = ref(false)
const dateOpensUp = ref(false)
const datePicker = ref(null)
const viewYear = ref(new Date().getFullYear())
const viewMonth = ref(new Date().getMonth() + 1)
const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const { loading, error, run } = useAsync()
const filtered = computed(() => Boolean(
  appliedKeyword.value || appliedSources.value.length || appliedDateFrom.value || appliedDateTo.value,
))
const sourceLabel = computed(() => {
  if (!selectedSources.value.length) return '来源'
  return sources
    .filter((src) => selectedSources.value.includes(src.key))
    .map((src) => src.label)
    .join('、')
})
const dateLabel = computed(() => {
  if (dateFrom.value && dateTo.value) return `${dateFrom.value} 至 ${dateTo.value}`
  if (dateFrom.value) return `${dateFrom.value} 起`
  return '更新时间'
})
const calendarCells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value - 1, 1)
  const pad = (first.getDay() + 6) % 7
  const count = new Date(viewYear.value, viewMonth.value, 0).getDate()
  const cells = Array(pad).fill(null)
  for (let day = 1; day <= count; day += 1) {
    cells.push(new Date(viewYear.value, viewMonth.value - 1, day))
  }
  return cells
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / 20)))

async function load() {
  const data = await run(() => api.news(page.value, {
    q: appliedKeyword.value,
    crawlers: appliedSources.value,
    dateFrom: appliedDateFrom.value,
    dateTo: appliedDateTo.value,
  }))
  if (data) {
    items.value = data.items || []
    total.value = data.total || 0
  }
}

function applySearch() {
  appliedKeyword.value = keyword.value.trim()
  appliedSources.value = [...selectedSources.value]
  appliedDateFrom.value = dateFrom.value
  appliedDateTo.value = dateTo.value
  sourceOpen.value = false
  dateOpen.value = false
  page.value = 1
  load()
}

function isoDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function placeCalendar() {
  const root = datePicker.value
  const menu = root?.querySelector('.cal')
  if (!root || !menu) return
  const trigger = root.getBoundingClientRect()
  const height = menu.offsetHeight
  const spaceBelow = window.innerHeight - trigger.bottom
  dateOpensUp.value = spaceBelow < height + 8 && trigger.top > spaceBelow
}

function toggleDate() {
  sourceOpen.value = false
  dateOpen.value = !dateOpen.value
  if (!dateOpen.value) return
  const [year, month] = (dateFrom.value || isoDate(new Date())).split('-')
  viewYear.value = Number(year)
  viewMonth.value = Number(month)
  nextTick(placeCalendar)
}

function shiftMonth(step) {
  const next = new Date(viewYear.value, viewMonth.value - 1 + step, 1)
  viewYear.value = next.getFullYear()
  viewMonth.value = next.getMonth() + 1
}

function pickDay(date) {
  const value = isoDate(date)
  if (!dateFrom.value || dateTo.value) {
    dateFrom.value = value
    dateTo.value = ''
    return
  }
  if (value < dateFrom.value) {
    dateTo.value = dateFrom.value
    dateFrom.value = value
  } else {
    dateTo.value = value
  }
}

function dayClass(cell) {
  if (!cell) return 'is-empty'
  const value = isoDate(cell)
  return {
    'is-edge': value === dateFrom.value || value === dateTo.value,
    'in-range': dateFrom.value && dateTo.value && value > dateFrom.value && value < dateTo.value,
  }
}

function clearDates() {
  dateFrom.value = ''
  dateTo.value = ''
}

function onDocumentClick(event) {
  if (sourcePicker.value && !sourcePicker.value.contains(event.target)) sourceOpen.value = false
  if (datePicker.value && !datePicker.value.contains(event.target)) dateOpen.value = false
}

function reload() { load() }

function go(p) {
  page.value = Math.min(Math.max(1, p), totalPages.value)
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  load()
  document.addEventListener('click', onDocumentClick)
})
onUnmounted(() => document.removeEventListener('click', onDocumentClick))
</script>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}
.filters input[type="search"] {
  flex: 1 1 220px;
  min-width: 180px;
}
.picker { position: relative; }
.picker-btn {
  background: transparent;
  color: var(--ink-soft);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-md);
  padding: 11px 14px;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picker-btn:hover:not(:disabled) {
  background: var(--wash);
  color: var(--pine);
  border-color: var(--pine);
  box-shadow: none;
  transform: none;
}
.picker-menu {
  position: absolute;
  z-index: 5;
  top: calc(100% + 6px);
  left: 0;
  min-width: 180px;
  padding: 8px;
  background: var(--surface);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-md);
  box-shadow: 0 12px 28px -16px rgba(28, 36, 32, 0.45);
}
.picker-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  color: var(--ink-soft);
  font-size: var(--fs-sm);
}
.cal { left: auto; right: 0; width: 280px; padding: 12px; }
.cal.up { top: auto; bottom: calc(100% + 6px); }
.cal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.cal-title {
  font-family: var(--font-serif);
  color: var(--ink);
  font-size: var(--fs-sm);
}
.cal-nav,
.cal-clear,
.cal-day {
  background: transparent;
  color: var(--ink-soft);
  border: 0;
  box-shadow: none;
  transform: none;
}
.cal-nav {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: var(--r-sm);
  font-size: 18px;
  line-height: 1;
}
.cal-nav:hover:not(:disabled),
.cal-clear:hover:not(:disabled),
.cal-day:hover:not(:disabled) {
  background: var(--wash);
  color: var(--pine);
  border-color: transparent;
  box-shadow: none;
  transform: none;
}
.cal-week,
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}
.cal-week span {
  text-align: center;
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  padding-bottom: 4px;
}
.cal-day {
  height: 32px;
  padding: 0;
  border-radius: var(--r-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
}
.cal-day.is-empty { visibility: hidden; }
.cal-day.in-range { background: var(--wash); color: var(--pine); border-radius: 0; }
.cal-day.is-edge {
  background: var(--pine);
  color: var(--paper);
}
.cal-day.is-edge:hover:not(:disabled) {
  background: var(--moss);
  color: var(--paper);
}
.cal-clear {
  width: 100%;
  margin-top: 8px;
  padding: 6px 0 2px;
  border-top: 1px solid var(--rule);
  border-radius: 0;
  letter-spacing: 0.08em;
  font-size: var(--fs-xs);
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.toc { border-top: 1px solid var(--ink); }
.entry {
  display: flex;
  align-items: flex-start;
  gap: clamp(14px, 2.6vw, 28px);
  color: inherit;
  padding: clamp(18px, 2.4vw, 26px) 8px;
  border-bottom: 1px solid var(--rule);
  transition: background var(--dur-fast), padding-left var(--dur-base) var(--ease-spring);
}
.entry:hover { background: var(--wash); padding-left: 16px; }

.entry-no {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: clamp(20px, 2.4vw, 28px);
  color: var(--lime);
  -webkit-text-stroke: 0.8px var(--pine);
  line-height: 1.2;
  min-width: 2ch;
  transition: transform var(--dur-base) var(--ease-spring);
}
.entry:hover .entry-no { transform: translateY(-2px); }

.entry-body { flex: 1; min-width: 0; display: block; }
.entry-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--fs-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin-bottom: 6px;
}
.entry-meta b { color: var(--moss); font-weight: 700; }
.dot { width: 3px; height: 3px; border-radius: 50%; background: var(--ink-mute); }
.time { font-family: var(--font-mono); text-transform: none; letter-spacing: 0.02em; }

.entry-title {
  font-family: var(--font-serif);
  font-size: clamp(16px, 1.9vw, 20px);
  line-height: 1.5;
  transition: color var(--dur-fast);
}
.entry:hover .entry-title { color: var(--pine); }

.entry-abstract {
  color: var(--ink-soft);
  font-size: 14px;
  line-height: 1.7;
  margin: 6px 0 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.entry-go {
  align-self: center;
  color: var(--pine);
  opacity: 0;
  transform: translateX(-8px);
  transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-spring);
}
.entry:hover .entry-go { opacity: 1; transform: none; }

.skeleton-entry { display: flex; gap: 24px; border-bottom: 1px solid var(--rule); padding: 24px 8px; }

.empty a { color: var(--pine); font-weight: 700; }
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 24px;
}
.page-indicator { font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--ink-mute); }
.page-indicator b { color: var(--pine); }
</style>
