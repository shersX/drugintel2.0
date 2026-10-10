<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Watchlist · 订阅名单</div>
      <h1 class="ed-title">告警订阅</h1>
      <p class="ed-lede">关注药物、公司或关键词，新情报入库后自动邮件推送。</p>
    </header>

    <!-- 新建订阅 -->
    <section class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>新增订阅</h3><span class="rule"></span></div>
      <form class="sub-form" @submit.prevent="create">
        <div class="field">
          <label>订阅类型</label>
          <div class="seg">
            <button
              type="button"
              v-for="t in types"
              :key="t.value"
              class="seg-btn"
              :class="{ on: form.entity_type === t.value }"
              @click="form.entity_type = t.value"
            >{{ t.label }}</button>
          </div>
        </div>
        <div class="field grow">
          <label for="wl-name">实体名称</label>
          <input id="wl-name" v-model="form.entity_name" placeholder="如：司美格鲁肽 / 诺和诺德 / GLP-1" required />
        </div>
        <div class="field grow">
          <label for="wl-mail">通知邮箱（可选）</label>
          <input id="wl-mail" v-model="form.email" type="email" placeholder="you@example.com" />
        </div>
        <button type="submit" :disabled="loading || !form.entity_name.trim()">添加订阅</button>
      </form>
      <div v-if="error" class="form-error">{{ error }}</div>
    </section>

    <!-- 订阅列表 -->
    <section class="reveal" style="--reveal-delay:120ms; margin-top:40px">
      <div class="sec-mark" v-if="items.length || loading"><span class="no">02</span><h3>我的名单</h3><span class="rule"></span></div>
      <template v-if="loading && !items.length">
        <div v-for="i in 2" :key="i" class="card wl-card">
          <div class="skeleton" style="width:140px;height:18px"></div>
          <div class="skeleton" style="width:220px;height:12px;margin-top:10px"></div>
        </div>
      </template>

      <div v-else-if="!items.length" class="card empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        <div class="empty-title">还没有订阅</div>
        <p>在上方添加第一个关注实体，相关情报将自动通知你</p>
      </div>

      <div
        v-for="(w, i) in items"
        :key="w.id"
        class="card wl-card card-hover reveal"
        :style="{ '--reveal-delay': i * 60 + 'ms' }"
      >
        <div class="wl-main">
          <span class="pill" :class="typeClass(w.entity_type)">{{ typeLabel(w.entity_type) }}</span>
          <strong class="wl-name">{{ w.entity_name }}</strong>
        </div>
        <div class="meta wl-sub">
          {{ w.email ? `通知至 ${w.email}` : '未配置邮箱' }}
          <span :class="['state', w.enabled ? 'on' : 'off']">{{ w.enabled ? '启用中' : '已停用' }}</span>
        </div>
        <button class="ghost danger-ghost wl-del" @click="remove(w.id)" aria-label="删除订阅">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.8" stroke-linecap="round">
            <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />
          </svg>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'

const items = ref([])
const { loading, error, run } = useAsync()
const form = reactive({
  user_id: 1,
  entity_type: 'keyword',
  entity_name: '',
  email: '',
  enabled: true,
})

const types = [
  { value: 'keyword', label: '关键词' },
  { value: 'drug', label: '药物' },
  { value: 'company', label: '公司' },
]
const typeLabel = (v) => types.find((t) => t.value === v)?.label || v
const typeClass = (v) => (v === 'drug' ? 'ok' : v === 'company' ? 'warn' : '')

async function load() {
  const data = await run(() => api.watchlist())
  if (data) items.value = data
}
async function create() {
  const ok = await run(() => api.createWatchlist({ ...form }))
  if (ok) {
    form.entity_name = ''
    await load()
  }
}
async function remove(id) {
  await run(() => api.deleteWatchlist(id))
  items.value = items.value.filter((w) => w.id !== id)
}
onMounted(load)
</script>

<style scoped>
.sub-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  align-items: flex-end;
}
.field { display: flex; flex-direction: column; gap: var(--sp-2); }
.field.grow { flex: 1; min-width: 200px; }
.field label {
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 700;
}

.seg {
  display: inline-flex;
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-md);
  padding: 3px;
  gap: 3px;
  background: var(--paper-deep);
}
.seg-btn {
  background: transparent;
  color: var(--ink-soft);
  border: none;
  padding: var(--sp-2) var(--sp-4);
  font-size: var(--fs-sm);
  border-radius: var(--r-sm);
}
.seg-btn:hover:not(.on) { color: var(--ink); background: rgba(255, 255, 255, 0.55); box-shadow: none; }
.seg-btn.on {
  background: var(--pine);
  color: var(--paper);
  box-shadow: 0 4px 12px -4px rgba(28, 75, 51, 0.5);
}
.seg-btn.on:hover:not(:disabled) { background: var(--moss); color: var(--paper); }

.form-error { margin-top: var(--sp-3); color: var(--clay); font-size: var(--fs-sm); }

.wl-card {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: var(--sp-4);
  margin-bottom: var(--sp-3);
  padding: var(--sp-4) var(--sp-5);
}
.wl-main { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
.wl-name { font-family: var(--font-serif); font-size: var(--fs-h2); }
.wl-sub { display: flex; gap: var(--sp-3); align-items: center; margin-top: 4px; }
.state.on { color: var(--moss); }
.state.off { color: var(--ink-mute); }
.wl-del { opacity: 0; transition: opacity var(--dur-fast); }
.wl-card:hover .wl-del { opacity: 1; }

@media (max-width: 900px) {
  .wl-card { grid-template-columns: 1fr auto; }
  .wl-sub { grid-column: 1 / -1; }
  .wl-del { opacity: 1; }
}
</style>
