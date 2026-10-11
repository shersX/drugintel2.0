<template>
  <div>
    <header class="ed-head">
      <div class="ed-kicker">Directory</div>
      <h1 class="ed-title">用户</h1>
      <p class="ed-lede">由管理员开户。停用后该账户立刻无法继续使用已登录的会话。</p>
    </header>

    <section class="card">
      <div class="sec-mark"><span class="no">01</span><h3>开户</h3><span class="rule"></span></div>
      <form class="create" @submit.prevent="create">
        <label>邮箱<input v-model="draft.email" type="email" required /></label>
        <label>显示名<input v-model="draft.display_name" /></label>
        <label>初始密码<input v-model="draft.password" type="password" required minlength="8" /></label>
        <label>角色
          <select v-model="draft.role">
            <option value="user">用户</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <label>每日问答上限<input v-model.number="draft.daily_chat_limit" type="number" min="0" max="10000" /></label>
        <button type="submit" :disabled="busy">创建</button>
      </form>
      <p v-if="error" class="form-error">{{ error }}</p>
    </section>

    <section class="list">
      <article v-for="item in items" :key="item.id" class="card user-card">
        <div>
          <strong>{{ item.display_name }}</strong>
          <span class="pill" :class="item.status === 'active' ? 'ok' : ''">{{ item.status === 'active' ? '启用' : '已停用' }}</span>
          <span class="pill">{{ item.role === 'admin' ? '管理员' : '用户' }}</span>
          <div class="meta">{{ item.email }}</div>
        </div>
        <label class="limit">每日问答
          <input v-model.number="item.daily_chat_limit" type="number" min="0" max="10000" />
        </label>
        <div class="actions">
          <button type="button" class="secondary" @click="saveLimit(item)">保存上限</button>
          <button type="button" class="secondary" @click="resetPassword(item)">重置密码</button>
          <button type="button" class="ghost" @click="kick(item)">踢下线</button>
          <button
            type="button"
            class="ghost danger-ghost"
            @click="toggle(item)"
          >{{ item.status === 'active' ? '停用' : '启用' }}</button>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const items = ref([])
const error = ref('')
const busy = ref(false)
const draft = reactive({
  email: '',
  display_name: '',
  password: '',
  role: 'user',
  daily_chat_limit: 50,
})

async function load() {
  items.value = await api.users()
}

async function create() {
  error.value = ''
  busy.value = true
  try {
    await api.createUser({ ...draft })
    draft.email = ''
    draft.display_name = ''
    draft.password = ''
    draft.role = 'user'
    draft.daily_chat_limit = 50
    await load()
  } catch (err) {
    error.value = err.message || '创建失败'
  } finally {
    busy.value = false
  }
}

async function run(action) {
  error.value = ''
  try {
    await action()
    await load()
  } catch (err) {
    error.value = err.message || '操作失败'
  }
}

function saveLimit(item) {
  return run(() => api.setChatLimit(item.id, item.daily_chat_limit))
}

function resetPassword(item) {
  const password = window.prompt(`为 ${item.email} 设置新密码（至少 8 位）`)
  if (!password) return
  return run(() => api.resetUserPassword(item.id, password))
}

function kick(item) {
  return run(() => api.kickUser(item.id))
}

function toggle(item) {
  return run(() => (item.status === 'active' ? api.disableUser(item.id) : api.enableUser(item.id)))
}

onMounted(load)
</script>

<style scoped>
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  align-items: end;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--fs-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
}
.form-error { color: var(--clay); }
.list { display: flex; flex-direction: column; gap: 12px; margin-top: 20px; }
.user-card { display: grid; gap: 12px; }
.meta { color: var(--ink-mute); font-size: var(--fs-sm); }
.pill { margin-left: 8px; }
.limit { max-width: 160px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
