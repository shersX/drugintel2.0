<template>
  <div class="card auth-panel">
    <h2>{{ admin ? '需要管理员权限' : '请登录' }}</h2>
    <p>{{ admin ? '当前账户不能使用管理功能。' : promptCopy(next) }}</p>
    <div class="auth-actions">
      <button v-if="!admin" type="button" @click="openLogin">登录</button>
      <button type="button" class="secondary" @click="leave">{{ admin ? '回到首页' : '取消' }}</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { openLoginPrompt, promptCopy } from '../authPrompt'

const props = defineProps({
  next: { type: String, default: '/' },
  admin: { type: Boolean, default: false },
})

const router = useRouter()

function openLogin() {
  openLoginPrompt(props.next)
}

function leave() {
  router.push('/')
}

onMounted(() => {
  if (!props.admin) openLoginPrompt(props.next)
})
</script>

<style scoped>
.auth-panel {
  max-width: 420px;
  margin: 48px auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
h2 {
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  margin: 0;
}
p { margin: 0; color: var(--ink-soft); }
.auth-actions { display: flex; gap: 10px; margin-top: 8px; }
</style>
