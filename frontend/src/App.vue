<template>
  <div class="shell">
    <header class="masthead">
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
            <router-link v-else-if="!isLogin" to="/login" class="login-link">登录</router-link>
          </span>
        </div>
        <nav class="mast-nav">
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="mast-link"
          >{{ item.label }}</router-link>
        </nav>
      </div>
    </header>

    <main class="page" :class="{ bare: isLogin, compact: isChat }">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <AuthGate
            v-if="showGate"
            :key="route.fullPath"
            :next="route.fullPath"
            :admin="gateIsAdmin"
          />
          <component v-else :is="Component" :key="route.fullPath" />
        </Transition>
      </router-view>
    </main>

    <div
      v-if="authPrompt.open"
      class="auth-mask"
      @click.self="dismissPrompt"
      @keydown.esc="dismissPrompt"
    >
      <div class="card auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <h2 id="auth-title">{{ authPrompt.kind === 'admin' ? '需要管理员权限' : '请登录' }}</h2>
        <p>{{ authPrompt.kind === 'admin' ? '当前账户不能使用管理功能。' : promptCopy(authPrompt.next) }}</p>
        <div class="auth-actions">
          <button v-if="authPrompt.kind === 'login'" type="button" @click="goLogin">登录</button>
          <button type="button" class="secondary" @click="dismissPrompt">
            {{ authPrompt.kind === 'admin' ? '知道了' : '取消' }}
          </button>
        </div>
      </div>
    </div>

    <PageChatFab v-if="showPageChat" />

    <footer v-if="!isLogin" class="colophon">
      <div class="colophon-inner">
        <span><b>DrugIntel.ai</b> — 医药情报 · 聚类 · RAG 问答</span>
        <span>pgvector × FastAPI × Vue 3 · 毕业设计版</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from './api'
import AuthGate from './components/AuthGate.vue'
import PageChatFab from './components/chat/PageChatFab.vue'
import { authPrompt, closeAuthPrompt, promptCopy } from './authPrompt'
import { setCrawlerSources } from './format'
import { clearUser, session } from './session'

async function loadCrawlerSources() {
  try {
    setCrawlerSources(await api.crawlers())
  } catch {
    setCrawlerSources([])
  }
}

watch(
  () => session.user?.id,
  () => { loadCrawlerSources() },
)

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const isChat = computed(() => route.path === '/chat')
const showPageChat = computed(() => !isLogin.value && !isChat.value)
const showGate = computed(() => {
  if (route.meta.public) return false
  if (!session.user) return true
  return Boolean(route.meta.admin && session.user.role !== 'admin')
})
const gateIsAdmin = computed(() => Boolean(session.user && route.meta.admin && session.user.role !== 'admin'))

function goLogin() {
  const next = authPrompt.next
  closeAuthPrompt()
  router.push({ path: '/login', query: next && next !== '/' ? { next } : {} })
}

function dismissPrompt() {
  const admin = authPrompt.kind === 'admin'
  closeAuthPrompt()
  if (admin && route.path !== '/') router.replace('/')
}

function onKeydown(event) {
  if (event.key === 'Escape' && authPrompt.open) dismissPrompt()
}

onMounted(() => {
  loadCrawlerSources()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
const navItems = computed(() => {
  const items = [
    { to: '/', label: '仪表盘' },
    { to: '/news', label: '情报流' },
    { to: '/chat', label: 'AI 问答' },
    { to: '/alerts', label: '监测订阅' },
  ]
  if (session.user?.role === 'admin') {
    items.push(
      { to: '/monitor', label: '爬虫监控' },
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
    /* 会话已失效时只清本地状态 */
  }
  clearUser()
  if (!route.meta.public) router.replace('/')
}
</script>

<style scoped>
.mast-side { display: flex; align-items: center; gap: 8px; }
.who,
.login-link {
  font-size: var(--fs-xs);
  color: var(--ink-soft);
  font-weight: 600;
}
.mast-side :deep(.ghost) {
  padding: 4px 10px;
  font-size: var(--fs-xs);
  min-height: 0;
  line-height: 1.3;
}
.page.bare {
  max-width: none;
  padding: 0;
}
.page.compact {
  max-width: 1360px;
  padding-top: 12px;
  padding-bottom: 16px;
}
.auth-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(28, 36, 32, 0.42);
}
.auth-dialog {
  width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.auth-dialog h2 {
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  margin: 0;
}
.auth-dialog p { margin: 0; color: var(--ink-soft); }
.auth-actions { display: flex; gap: 10px; margin-top: 8px; }
</style>
