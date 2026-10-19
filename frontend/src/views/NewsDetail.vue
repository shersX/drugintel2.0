<template>
  <article v-if="news" class="detail" :class="{ 'has-aside': hasAside }">
    <div class="detail-sticky">
      <router-link to="/news" class="back">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round">
          <path d="M19 12H5M11 6l-6 6 6 6" />
        </svg>
        返回情报目录
      </router-link>
      <span class="sticky-title">{{ news.title }}</span>
    </div>

    <div class="detail-layout">
      <div class="detail-main">
        <header class="reveal">
          <div class="ed-kicker">Dispatch · {{ crawlerLabel(news.crawler) }}</div>
          <h1 class="title">{{ news.title }}</h1>
          <div class="byline">
            <span class="meta">{{ news.publish_time ? formatDateTimeMinute(news.publish_time) : '时间未知' }}</span>
            <i class="dot"></i>
            <a v-if="news.detail_url" :href="news.detail_url" target="_blank" rel="noopener" class="origin-link">
              查看原文
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round">
                <path d="M7 17L17 7M9 7h8v8" />
              </svg>
            </a>
          </div>
        </header>

        <section v-if="news.abstract" class="abstract-block reveal" style="--reveal-delay:80ms">
          <div class="q-src">AI 摘要</div>
          <div class="abstract-md" v-html="abstractHtml" />
        </section>

        <section class="body reveal" style="--reveal-delay:140ms">
          <div
            v-if="bodyHtml"
            class="prose"
            v-html="bodyHtml"
          />
          <div v-else class="prose plain">{{ news.content }}</div>
        </section>
      </div>

      <aside v-if="hasAside" class="detail-aside reveal" style="--reveal-delay:180ms">
        <section v-if="matchedList.length" class="aside-block">
          <div class="aside-head"><span class="no">※</span> 命中关键词</div>
          <div class="aside-pills">
            <span v-for="k in matchedList" :key="k" class="pill">{{ k }}</span>
          </div>
        </section>

        <section v-if="news.related_news?.length" class="aside-block">
          <div class="aside-head">
            <span class="no">§</span> 同一事件 · {{ news.related_news.length }}
          </div>
          <router-link
            v-for="r in news.related_news"
            :key="r.id"
            :to="`/news/${r.id}`"
            class="related-card"
          >
            <span>{{ r.title }}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </router-link>
        </section>
      </aside>
    </div>

    <router-link to="/news" class="back-fab" title="返回情报目录" aria-label="返回情报目录">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round">
        <path d="M19 12H5M11 6l-6 6 6 6" />
      </svg>
    </router-link>
  </article>

  <div v-else-if="loading" class="card">
    <div class="skeleton" style="width:60%;height:32px"></div>
    <div class="skeleton" style="width:100%;height:14px;margin-top:22px"></div>
    <div class="skeleton" style="width:100%;height:14px;margin-top:10px"></div>
    <div class="skeleton" style="width:90%;height:14px;margin-top:10px"></div>
  </div>

  <div v-else class="card empty">
    <div class="empty-title">新闻不存在或加载失败</div>
    <p>{{ error || '该条目可能已被移除' }}</p>
    <router-link to="/news" class="back">返回情报目录</router-link>
  </div>
</template>

<script setup>
import { marked } from 'marked'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import { crawlerLabel, formatDateTimeMinute } from '../format'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({ id: { type: [String, Number], required: true } })
const news = ref(null)
const { loading, error, run } = useAsync()
const mastOffset = ref(96)
const mastOffsetPx = computed(() => `${mastOffset.value}px`)
const asideTopPx = computed(() => `${mastOffset.value + 12}px`)

function syncMastOffset() {
  const mast = document.querySelector('.masthead')
  mastOffset.value = Math.ceil(mast?.getBoundingClientRect().height || 96)
}

const matchedList = computed(() => {
  const mk = news.value?.matched_keywords || {}
  return Object.values(mk)
    .flatMap((v) => String(v || '').split(','))
    .map((s) => s.trim())
    .filter(Boolean)
})

const hasAside = computed(() =>
  matchedList.value.length > 0 || Boolean(news.value?.related_news?.length),
)

const abstractHtml = computed(() => {
  const raw = String(news.value?.abstract || '').trim()
  if (!raw) return ''
  return marked.parse(raw, { async: false })
})

const bodyHtml = computed(() => {
  const html = String(news.value?.content_html || '').trim()
  if (html) return html
  const legacy = String(news.value?.content || '')
  return /<\/?[a-z][\s\S]*>/i.test(legacy) ? legacy : ''
})

async function load() {
  const data = await run(() => api.newsDetail(props.id))
  news.value = data
}
onMounted(() => {
  load()
  syncMastOffset()
  window.addEventListener('resize', syncMastOffset)
})
onUnmounted(() => window.removeEventListener('resize', syncMastOffset))
watch(() => props.id, load)
</script>

<style scoped>
.detail { max-width: 1120px; position: relative; }

.detail-sticky {
  position: sticky;
  top: v-bind(mastOffsetPx);
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 14px;
  margin: -6px 0 12px;
  padding: 10px 0;
  background: color-mix(in srgb, var(--paper) 94%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--rule);
}
.sticky-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-sm);
  color: var(--ink-mute);
}

.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}

.detail-main { min-width: 0; max-width: 780px; }

.detail-aside {
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-width: 0;
}

.aside-block {
  padding-bottom: 4px;
}
.aside-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink-mute);
}
.aside-head .no { color: var(--moss); letter-spacing: 0; }
.aside-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: none;
  color: var(--ink-mute);
  font-size: var(--fs-sm);
  margin: 0;
  transition: color var(--dur-fast), gap var(--dur-fast) var(--ease-spring);
}
.back:hover { color: var(--pine); gap: 9px; }

.back-fab {
  position: fixed;
  right: max(20px, calc((100vw - 1120px) / 2 + 16px));
  bottom: 28px;
  z-index: 35;
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--pine);
  color: var(--paper);
  box-shadow: 0 10px 24px -10px rgba(28, 75, 51, 0.55);
  transition: transform var(--dur-fast) var(--ease-spring), background var(--dur-fast);
}
.back-fab:hover {
  transform: translateY(-2px);
  background: var(--moss);
  color: var(--paper);
}

.title {
  font-family: var(--font-serif);
  font-size: clamp(20px, 2.6vw, 28px);
  line-height: 1.4;
  letter-spacing: 0.005em;
  text-wrap: balance;
  margin-top: 8px;
}

.byline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin: 18px 0 0;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ink);
}
.dot { width: 3px; height: 3px; border-radius: 50%; background: var(--ink-mute); }
.origin-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-sm);
  margin-left: auto;
  border-bottom: 1px solid transparent;
  transition: border-color var(--dur-fast);
}
.origin-link:hover { border-color: var(--pine); }

.abstract-block {
  margin: 22px 0 28px;
  padding: 14px 0 14px 18px;
  border-left: 3px solid var(--lime);
}
.abstract-block .q-src {
  display: block;
  margin: 0 0 10px;
  font-size: var(--fs-xs);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-mute);
}
.abstract-md {
  color: var(--ink);
  font-size: 15px;
  line-height: 1.75;
}
.abstract-md :deep(h1),
.abstract-md :deep(h2),
.abstract-md :deep(h3),
.abstract-md :deep(h4) {
  font-family: var(--font-serif);
  font-size: 1.05em;
  font-weight: 700;
  margin: 0.9em 0 0.35em;
  line-height: 1.35;
}
.abstract-md :deep(h1:first-child),
.abstract-md :deep(h2:first-child),
.abstract-md :deep(h3:first-child) { margin-top: 0; }
.abstract-md :deep(p) { margin: 0 0 0.65em; }
.abstract-md :deep(p:last-child) { margin-bottom: 0; }
.abstract-md :deep(ul),
.abstract-md :deep(ol) {
  margin: 0.35em 0 0.75em;
  padding-left: 1.25em;
}
.abstract-md :deep(li) { margin: 0.2em 0; }
.abstract-md :deep(strong),
.abstract-md :deep(b) { font-weight: 700; }
.abstract-md :deep(em),
.abstract-md :deep(i) { font-style: italic; }

.body { font-size: 16px; }
.prose {
  line-height: 1.9;
  color: var(--ink);
  letter-spacing: 0.015em;
}
.prose.plain {
  white-space: pre-wrap;
  line-height: 2;
}
.prose :deep(p) { margin: 0 0 1em; }
.prose :deep(p:last-child) { margin-bottom: 0; }
.prose :deep(h2),
.prose :deep(h3),
.prose :deep(h4) {
  font-family: var(--font-serif);
  font-weight: 700;
  color: var(--ink);
  margin: 1.4em 0 0.6em;
  line-height: 1.35;
}
.prose :deep(h2) { font-size: 1.25em; }
.prose :deep(h3) { font-size: 1.12em; }
.prose :deep(h4) { font-size: 1.05em; }
.prose :deep(ul),
.prose :deep(ol) {
  margin: 0.6em 0 1em;
  padding-left: 1.4em;
}
.prose :deep(li) { margin: 0.35em 0; }
.prose :deep(ul ul),
.prose :deep(ol ol),
.prose :deep(ul ol),
.prose :deep(ol ul) {
  margin: 0.25em 0 0.4em;
}
.prose :deep(i),
.prose :deep(em) { font-style: italic; }
.prose :deep(b),
.prose :deep(strong) { font-weight: 700; }
.prose :deep(a) {
  color: var(--pine);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.prose :deep(a:hover) { color: var(--moss); }
.prose :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 0.92em;
}
.prose :deep(th),
.prose :deep(td) {
  border: 1px solid var(--rule);
  padding: 8px 10px;
  vertical-align: top;
}
.prose :deep(th) {
  background: var(--wash);
  font-weight: 700;
}
.prose :deep(sup) { font-size: 0.75em; }

.related-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  color: inherit;
  padding: 10px 0;
  border-bottom: 1px solid var(--rule);
  font-size: 13.5px;
  line-height: 1.45;
  transition: color var(--dur-fast), padding-left var(--dur-base) var(--ease-spring);
}
.related-card:first-of-type { border-top: 1px solid var(--rule); }
.related-card:hover { color: var(--pine); padding-left: 6px; }
.related-card span { flex: 1; min-width: 0; }
.related-card svg {
  color: var(--pine);
  flex: none;
  opacity: 0.45;
  margin-top: 2px;
  transition: opacity var(--dur-fast), transform var(--dur-base) var(--ease-spring);
}
.related-card:hover svg { opacity: 1; transform: translateX(2px); }

@media (min-width: 960px) {
  .detail.has-aside .detail-layout {
    grid-template-columns: minmax(0, 1fr) 260px;
    gap: 36px;
  }
  .detail.has-aside .detail-main { max-width: none; }
  .detail-aside {
    position: sticky;
    top: v-bind(asideTopPx);
  }
}

@media (max-width: 959px) {
  .detail-aside {
    padding-top: 8px;
    border-top: 1px solid var(--rule);
  }
}
</style>
