<template>
  <div class="shell">
    <AppLayout>
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <AuthGate
            v-if="showGate"
            :key="route.fullPath"
            :next="route.fullPath"
            :admin="gateIsAdmin"
          />
          <component v-else :is="Component" :key="route.path" />
        </Transition>
      </router-view>
    </AppLayout>

    <div
      v-if="authPrompt.open"
      class="auth-mask"
      @click.self="dismissPrompt"
    >
      <div
        class="card auth-dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="authPrompt.kind === 'admin' ? 'auth-title' : undefined"
      >
        <template v-if="authPrompt.kind === 'admin'">
          <h2 id="auth-title">需要管理员权限</h2>
          <p>当前账户不能使用管理功能。</p>
          <div class="auth-actions">
            <button type="button" class="secondary" @click="dismissPrompt">知道了</button>
          </div>
        </template>
        <LoginModal
          v-else
          :next="authPrompt.next"
          :hint="promptCopy(authPrompt.next)"
          @success="closeAuthPrompt"
          @cancel="dismissPrompt"
        />
      </div>
    </div>

    <PageChatFab v-if="showPageChat" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from './api'
import AuthGate from './components/AuthGate.vue'
import LoginModal from './components/LoginModal.vue'
import AppLayout from './components/layout/AppLayout.vue'
import PageChatFab from './components/chat/PageChatFab.vue'
import { authPrompt, closeAuthPrompt, promptCopy } from './authPrompt'
import { setCrawlerSources } from './format'
import { session } from './session'

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
const isChat = computed(() => route.path === '/chat')
const showPageChat = computed(() => !isChat.value)
const showGate = computed(() => {
  if (route.meta.public) return false
  if (!session.user) return true
  return Boolean(route.meta.admin && session.user.role !== 'admin')
})
const gateIsAdmin = computed(() => Boolean(session.user && route.meta.admin && session.user.role !== 'admin'))

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
</script>

<style scoped>
.auth-mask {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(28, 36, 32, 0.42);
}
.auth-dialog {
  width: min(360px, 100%);
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
