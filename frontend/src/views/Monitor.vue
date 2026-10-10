<template>
  <div>
    <header class="ed-head reveal">
      <div class="head-row">
        <div>
          <div class="ed-kicker">System · 印务检查</div>
          <h1 class="ed-title">运行监控</h1>
          <p class="ed-lede">基础设施健康、流水线状态与爬虫任务记录。</p>
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

      <!-- 流水线状态 -->
      <section class="card reveal" style="margin-top:32px;--reveal-delay:160ms">
        <div class="sec-mark"><span class="no">02</span><h3>处理流水线</h3><span class="rule"></span></div>
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
        <div class="sec-mark"><span class="no">03</span><h3>爬虫任务</h3><span class="rule"></span></div>
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
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import { formatTime } from '../format'

const health = ref(null)
const processing = ref(null)
const tasks = ref([])
const { loading, error, run } = useAsync()

const checked = computed(() => health.value !== null)

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

async function load() {
  const data = await run(() => api.monitor())
  if (data) {
    health.value = data.health || null
    processing.value = data.processing || null
    tasks.value = data.crawler_tasks || []
  }
}
onMounted(load)
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
</style>
