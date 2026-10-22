<template>
  <form class="login-modal" @submit.prevent="submit">
    <h2 id="auth-title">登录</h2>
    <p class="hint">{{ hint || '管理员开通的账户' }}</p>
    <label for="login-email">邮箱</label>
    <input
      id="login-email"
      v-model="email"
      type="email"
      autocomplete="username"
      required
      autofocus
    />
    <label for="login-password">密码</label>
    <input
      id="login-password"
      v-model="password"
      type="password"
      autocomplete="current-password"
      required
    />
    <p v-if="error" class="form-error">{{ error }}</p>
    <div class="auth-actions">
      <button type="submit" :disabled="busy">{{ busy ? '正在登录…' : '进入' }}</button>
      <button type="button" class="secondary" :disabled="busy" @click="$emit('cancel')">取消</button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { setUser } from '../session'

const props = defineProps({
  next: { type: String, default: '/' },
  hint: { type: String, default: '' },
})

const emit = defineEmits(['success', 'cancel'])

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
    emit('success')
    const next = props.next
    if (next && next.startsWith('/') && !next.startsWith('//') && next !== router.currentRoute.value.fullPath) {
      await router.replace(next)
    }
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login-modal {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
h2 {
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  margin: 0;
}
.hint {
  margin: 0 0 4px;
  font-size: var(--fs-sm);
  color: var(--ink-mute);
}
label {
  font-size: var(--fs-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
}
.form-error {
  margin: 0;
  color: var(--clay);
  font-size: var(--fs-sm);
}
.auth-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}
</style>
