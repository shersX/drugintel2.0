<template>
  <article v-if="news" class="detail">
    <header class="reveal">
      <router-link to="/news" class="back">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round">
          <path d="M19 12H5M11 6l-6 6 6 6" />
        </svg>
        返回情报目录
      </router-link>
      <div class="ed-kicker">Dispatch · {{ crawlerLabel(news.crawler) }}</div>
      <h1 class="title">{{ news.title }}</h1>
      <div class="byline">
        <span class="meta">{{ news.publish_time || '时间未知' }}</span>
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

    <section v-if="news.abstract" class="pullquote reveal" style="--reveal-delay:80ms">
      <span class="qmark">“</span>
      <p>{{ news.abstract }}</p>
      <span class="q-src">AI 摘要</span>
    </section>

    <section class="body reveal" style="--reveal-delay:140ms">
      <div class="prose">{{ news.content }}</div>
    </section>

    <section v-if="matchedList.length" class="reveal" style="--reveal-delay:200ms; margin-top:40px">
      <div class="sec-mark"><span class="no">※</span><h3>命中关键词</h3><span class="rule"></span></div>
      <div class="row">
        <span v-for="k in matchedList" :key="k" class="pill">{{ k }}</span>
      </div>
    </section>

    <section v-if="news.related_news?.length" class="reveal" style="--reveal-delay:260ms; margin-top:48px">
      <div class="sec-mark"><span class="no">§</span><h3>同一事件 · {{ news.related_news.length }} 篇相关报道</h3><span class="rule"></span></div>
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
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import { crawlerLabel } from '../format'

const props = defineProps({ id: { type: [String, Number], required: true } })
const news = ref(null)
const { loading, error, run } = useAsync()

const matchedList = computed(() => {
  const mk = news.value?.matched_keywords || {}
  return Object.values(mk)
    .flatMap((v) => String(v || '').split(','))
    .map((s) => s.trim())
    .filter(Boolean)
})

async function load() {
  const data = await run(() => api.newsDetail(props.id))
  news.value = data
}
onMounted(load)
watch(() => props.id, load)
</script>

<style scoped>
.detail { max-width: 780px; }

.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-mute);
  font-size: var(--fs-sm);
  margin-bottom: 20px;
  transition: color var(--dur-fast), gap var(--dur-fast) var(--ease-spring);
}
.back:hover { color: var(--pine); gap: 9px; }

.title {
  font-family: var(--font-serif);
  font-size: clamp(26px, 4.4vw, 44px);
  line-height: 1.32;
  letter-spacing: 0.005em;
  text-wrap: balance;
  margin-top: 12px;
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

/* 摘要 = 刊物的拉引语 */
.pullquote {
  position: relative;
  margin: 32px 0;
  padding: 8px 0 8px 26px;
  border-left: 3px solid var(--lime);
}
.pullquote .qmark {
  font-family: var(--font-serif);
  font-size: 56px;
  line-height: 0.6;
  color: var(--lime);
  float: left;
  margin: 6px 10px 0 0;
}
.pullquote p {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(17px, 2vw, 21px);
  line-height: 1.85;
  color: var(--ink);
}
.q-src {
  display: block;
  margin-top: 10px;
  font-size: var(--fs-xs);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-mute);
}

/* 正文直接排在纸面上 */
.body { font-size: 16px; }
.prose {
  white-space: pre-wrap;
  line-height: 2;
  color: var(--ink);
  letter-spacing: 0.015em;
}
.prose::first-letter {
  font-family: var(--font-serif);
  font-size: 2.4em;
  font-weight: 700;
  color: var(--pine);
  line-height: 1;
  margin-right: 4px;
}

.related-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: inherit;
  padding: 14px 8px;
  border-bottom: 1px solid var(--rule);
  font-size: 14.5px;
  transition: background var(--dur-fast), padding-left var(--dur-base) var(--ease-spring);
}
.related-card:first-of-type { border-top: 1px solid var(--rule); }
.related-card:hover { background: var(--wash); padding-left: 14px; }
.related-card svg {
  color: var(--pine);
  flex: none;
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity var(--dur-fast), transform var(--dur-base) var(--ease-spring);
}
.related-card:hover svg { opacity: 1; transform: none; }
</style>
