<template>
  <div>
    <h2>告警订阅</h2>
    <div class="card">
      <div class="row">
        <select v-model="form.entity_type">
          <option value="keyword">keyword</option>
          <option value="drug">drug</option>
          <option value="company">company</option>
        </select>
        <input v-model="form.entity_name" placeholder="实体名，如 司美格鲁肽" />
        <input v-model="form.email" placeholder="通知邮箱（可选）" />
        <button @click="create">添加</button>
      </div>
    </div>
    <div class="card" v-for="w in items" :key="w.id">
      <div class="row" style="justify-content:space-between">
        <div>
          <strong>{{ w.entity_name }}</strong>
          <div class="meta">{{ w.entity_type }} · {{ w.email || '无邮箱' }} · {{ w.enabled ? '启用' : '停用' }}</div>
        </div>
        <button class="secondary" @click="remove(w.id)">删除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const items = ref([])
const form = reactive({
  user_id: 1,
  entity_type: 'keyword',
  entity_name: '',
  email: '',
  enabled: true,
})

async function load() {
  items.value = await api.watchlist()
}
async function create() {
  await api.createWatchlist({ ...form })
  form.entity_name = ''
  await load()
}
async function remove(id) {
  await api.deleteWatchlist(id)
  await load()
}
onMounted(load)
</script>
