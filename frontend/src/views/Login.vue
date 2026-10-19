<template>
  <div class="login">
    <form class="card login-card" @submit.prevent="submit">
      <div class="ed-kicker">Sign in</div>
      <h1>登录</h1>
      <p class="lede">账户由管理员开通。</p>
      <label for="email">邮箱</label>
      <input id="email" v-model="email" type="email" autocomplete="username" required />
      <label for="password">密码</label>
      <input id="password" v-model="password" type="password" autocomplete="current-password" required />
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="busy">{{ busy ? '正在登录…' : '进入' }}</button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { setUser } from '../session'

const route = useRoute()
const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const user = await api.login({ email: email.value.trim(), password: password.value })
    setUser(user)
    const next = typeof route.query.next === 'string' ? route.query.next : '/'
    router.replace(next.startsWith('/') && !next.startsWith('//') ? next : '/')
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login {
  min-height: 70vh;
  display: grid;
  place-items: center;
  padding: 24px;
}
.login-card {
  width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
h1 {
  font-family: var(--font-serif);
  font-size: var(--fs-display);
  margin: 0;
}
.lede {
  margin: 0 0 8px;
  color: var(--ink-soft);
}
label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
}
.form-error { margin: 0; color: var(--clay); font-size: var(--fs-sm); }
button { margin-top: 8px; }
</style>
