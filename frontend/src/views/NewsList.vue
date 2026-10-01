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

    <div v-if="error" class="card empty">
      <div class="empty-title">加载失败</div>
      <p>{{ error }}</p>
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
      <div class="empty-title">暂无新闻</div>
      <p>运行 <code>python main.py</code> 采集并处理新闻后，这里会出现情报目录</p>
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
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import { crawlerLabel, formatTime } from '../format'

const items = ref([])
const page = ref(1)
const total = ref(0)
const { loading, error, run } = useAsync()

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / 20)))

async function load() {
  const data = await run(() => api.news(page.value))
  if (data) {
    items.value = data.items || []
    total.value = data.total || 0
  }
}

function reload() { load() }

function go(p) {
  page.value = Math.min(Math.max(1, p), totalPages.value)
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(load)
</script>

<style scoped>
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
