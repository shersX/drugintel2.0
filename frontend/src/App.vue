<template>
  <div class="shell">
    <header v-if="!isLogin" class="masthead">
      <div class="masthead-inner">
        <div class="mast-top">
          <router-link to="/" class="mast-brand">
            <svg class="leaf" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 20c0-8 5-14 14-15 .5 9-4 14-11 14.5" />
              <path d="M5 20c3-5 7-9 12-11.5" />
            </svg>
            DrugIntel<span style="color: var(--moss)">.ai</span>
          </router-link>
          <span class="mast-side">
            <template v-if="session.user">
              <router-link to="/account" class="who">{{ session.user.display_name }}</router-link>
              <button type="button" class="ghost" @click="logout">退出</button>
            </template>
            <span v-else class="mast-date">Vol. {{ issue }} · {{ today }}</span>
          </span>
        </div>
        <nav v-if="session.user" class="mast-nav">
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="mast-link"
          >{{ item.label }}</router-link>
        </nav>
      </div>
    </header>

    <main class="page" :class="{ bare: isLogin }">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>

    <footer v-if="!isLogin" class="colophon">
      <div class="colophon-inner">
        <span><b>DrugIntel.ai</b> — 医药情报 · 聚类 · RAG 问答</span>
        <span>pgvector × FastAPI × Vue 3 · 毕业设计版</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from './api'
import { setCrawlerSources } from './format'
import { clearUser, session } from './session'

watch(
  () => session.user,
  async (user) => {
    if (!user) {
      setCrawlerSources([])
      return
    }
    try {
      setCrawlerSources(await api.crawlers())
    } catch {
      setCrawlerSources([])
    }
  },
  { immediate: true },
)

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const navItems = computed(() => {
  const items = [
    { to: '/', label: '仪表盘' },
    { to: '/news', label: '情报流' },
    { to: '/chat', label: 'AI 问答' },
    { to: '/alerts', label: '监测订阅' },
  ]
  if (session.user?.role === 'admin') {
    items.push(
      { to: '/monitor', label: '系统监控' },
      { to: '/settings', label: '模型配置' },
      { to: '/users', label: '用户' },
    )
  }
  return items
})

async function logout() {
  try {
    await api.logout()
  } catch {
    /* 会话已失效时直接回到登录页 */
  }
  clearUser()
  router.replace('/login')
}

const now = new Date()
const today = `${now.getFullYear()} 年 ${now.getMonth() + 1} 月 ${now.getDate()} 日`
const issue = String(Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 864e5))
</script>

<style scoped>
.mast-side { display: flex; align-items: center; gap: 8px; }
.who {
  font-size: var(--fs-sm);
  color: var(--ink-soft);
  font-weight: 600;
}
.page.bare {
  max-width: none;
  padding: 0;
}
</style>
