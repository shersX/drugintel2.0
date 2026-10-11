<template>
  <div>
    <header class="ed-head">
      <div class="ed-kicker">Account</div>
      <h1 class="ed-title">我的账户</h1>
      <p class="ed-lede">{{ session.user?.email }} · {{ session.user?.role === 'admin' ? '管理员' : '用户' }}</p>
    </header>

    <section class="card">
      <form class="stack" @submit.prevent="save">
        <label for="name">显示名</label>
        <input id="name" v-model="displayName" required />
        <label for="old">原密码（修改密码时填写）</label>
        <input id="old" v-model="oldPassword" type="password" autocomplete="current-password" />
        <label for="next">新密码</label>
        <input id="next" v-model="newPassword" type="password" autocomplete="new-password" />
        <p v-if="error" class="form-error">{{ error }}</p>
        <p v-if="saved" class="ok-note">已保存</p>
        <button type="submit" :disabled="busy">保存</button>
      </form>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { session, setUser } from '../session'

const displayName = ref(session.user?.display_name || '')
const oldPassword = ref('')
const newPassword = ref('')
const error = ref('')
const saved = ref(false)
const busy = ref(false)

async function save() {
  error.value = ''
  saved.value = false
  busy.value = true
  try {
    const user = await api.updateProfile({
      display_name: displayName.value.trim(),
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    setUser(user)
    oldPassword.value = ''
    newPassword.value = ''
    saved.value = true
  } catch (err) {
    error.value = err.message || '保存失败'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.stack { display: flex; flex-direction: column; gap: 10px; max-width: 420px; }
label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
}
.form-error { margin: 0; color: var(--clay); }
.ok-note { margin: 0; color: var(--moss); }
</style>
