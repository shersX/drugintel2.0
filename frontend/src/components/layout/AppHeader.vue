<template>
  <header class="app-header">
    <div class="hdr-left">
      <button
        v-if="showSideDrawerBtn"
        type="button"
        class="drawer-btn"
        aria-label="打开侧栏菜单"
        title="菜单"
        @click="toggleDrawer"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path d="M3 5h12M3 9h12M3 13h12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
      </button>
      <router-link to="/" class="brand">
        <svg class="leaf" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 20c0-8 5-14 14-15 .5 9-4 14-11 14.5" />
          <path d="M5 20c3-5 7-9 12-11.5" />
        </svg>
        DrugIntel<span class="dot">.ai</span>
      </router-link>
      <nav class="top-nav" aria-label="一级导航">
        <router-link
          v-for="item in modules"
          :key="item.key"
          :to="item.to"
          class="top-link"
          :class="{ on: currentKey === item.key }"
        >{{ item.label }}</router-link>
      </nav>
    </div>
    <div class="hdr-right">
      <form class="search" @submit.prevent="onSearch">
        <input v-model="q" type="search" placeholder="全局搜索情报…" aria-label="全局搜索" />
      </form>
      <template v-if="session.user">
        <div class="user-menu" ref="menuRef">
          <button type="button" class="user-btn" @click="open = !open" :aria-expanded="open">
            <span class="avatar">{{ initials }}</span>
            <span class="uname">{{ session.user.display_name }}</span>
          </button>
          <div v-if="open" class="dropdown" role="menu">
            <router-link to="/account" role="menuitem" @click="open = false">账号设置</router-link>
            <button type="button" role="menuitem" @click="onLogout">退出登录</button>
          </div>
        </div>
      </template>
      <button v-else type="button" class="login-link" @click="onLogin">登录</button>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../api'
import { openLoginPrompt } from '../../authPrompt'
import { useSidebarDrawer } from '../../composables/useSidebarDrawer'
import { moduleShowsSidebar, resolveModule, visibleTopModules } from '../../nav.config'
import { clearUser, session } from '../../session'

defineProps({
  currentKey: { type: String, default: '' },
})

const route = useRoute()
const router = useRouter()
const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
const open = ref(false)
const menuRef = ref(null)
const { toggleDrawer } = useSidebarDrawer()

const modules = computed(() => visibleTopModules(session.user))
const showSideDrawerBtn = computed(() =>
  moduleShowsSidebar(resolveModule(route), session.user),
)
const initials = computed(() => {
  const n = session.user?.display_name || session.user?.email || '?'
  return String(n).trim().slice(0, 1).toUpperCase()
})

function onSearch() {
  const term = q.value.trim()
  router.push({ path: '/news', query: term ? { q: term } : {} })
}

function onLogin() {
  openLoginPrompt(route.fullPath)
}

async function onLogout() {
  open.value = false
  try {
    await api.logout()
  } catch { /* ignore */ }
  clearUser()
  if (!route.meta.public) router.replace('/')
}

function onDocClick(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) open.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

watch(
  () => route.query.q,
  (v) => {
    if (typeof v === 'string') q.value = v
  },
)
</script>

<style scoped>
.app-header {
  height: var(--header-h, 64px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 var(--app-pad-x);
  background: rgba(245, 242, 233, 0.96);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--ink);
  z-index: 40;
}
.hdr-left {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
  flex: 1;
}
.drawer-btn {
  display: none;
  place-items: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--surface);
  color: var(--pine);
  cursor: pointer;
  flex: none;
}
.drawer-btn:hover {
  border-color: var(--pine);
  background: color-mix(in srgb, var(--moss) 10%, transparent);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
  flex: none;
  white-space: nowrap;
}
.brand .dot { color: var(--moss); }
.leaf { width: 20px; height: 20px; color: var(--pine); }
.top-nav {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  min-width: 0;
  scrollbar-width: none;
}
.top-nav::-webkit-scrollbar { display: none; }
.top-link {
  position: relative;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-mute);
  white-space: nowrap;
  border-radius: 6px;
  transition: color 160ms, background 160ms;
}
.top-link:hover { color: var(--ink); background: color-mix(in srgb, var(--moss) 8%, transparent); }
.top-link.on {
  color: var(--pine);
  background: color-mix(in srgb, var(--moss) 14%, transparent);
}
.top-link.on::after {
  content: "";
  position: absolute;
  left: 12px; right: 12px; bottom: 2px;
  height: 2px;
  background: var(--pine);
  border-radius: 2px;
}
.hdr-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
}
.search input {
  width: min(220px, 28vw);
  padding: 7px 12px;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: var(--surface);
  font-size: 13px;
}
.user-menu { position: relative; }
.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
}
.user-btn:hover { background: color-mix(in srgb, var(--moss) 10%, transparent); }
.avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--pine);
  color: var(--paper);
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
}
.uname {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-soft);
  max-width: 10ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dropdown {
  position: absolute;
  right: 0; top: calc(100% + 6px);
  min-width: 160px;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  box-shadow: var(--shadow-md);
  padding: 6px;
  display: grid;
  gap: 2px;
  z-index: 50;
}
.dropdown a,
.dropdown button {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: 4px;
  font-size: 13px;
  color: var(--ink);
  cursor: pointer;
  text-decoration: none;
}
.dropdown a:hover,
.dropdown button:hover { background: color-mix(in srgb, var(--moss) 12%, transparent); }
.login-link {
  font-size: 13px;
  font-weight: 600;
  color: var(--pine);
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
  font: inherit;
}
@media (max-width: 1024px) {
  .drawer-btn { display: inline-grid; }
}
@media (max-width: 900px) {
  .uname { display: none; }
  .search input { width: 120px; }
}
</style>
