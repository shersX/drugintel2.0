<template>
  <section class="card reveal">
    <div class="sec-mark"><span class="no">E</span><h3>实体词典</h3><span class="rule"></span></div>
    <p class="meta hint">canonical + aliases 归一化（如 礼来 → eli lilly）。pending 达到 3 次自动升格。</p>

    <div class="filters">
      <select v-model="entityType" @change="reload">
        <option value="">全部类型</option>
        <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-model="status" @change="reload">
        <option value="">全部状态</option>
        <option value="active">active</option>
        <option value="pending">pending</option>
        <option value="merged">merged</option>
        <option value="rejected">rejected</option>
      </select>
      <input v-model="q" type="search" placeholder="搜索 canonical / 别名" @keydown.enter="reload" />
      <button class="secondary" :disabled="busy" @click="reload">刷新</button>
      <button class="secondary" :disabled="busy" @click="doImport">从关键词导入</button>
    </div>

    <form class="create-row" @submit.prevent="createOne">
      <select v-model="form.entity_type" required>
        <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
      </select>
      <input v-model="form.canonical" placeholder="canonical" required />
      <input v-model="form.aliasesText" placeholder="别名，逗号分隔" />
      <button type="submit" :disabled="busy">新建</button>
    </form>

    <p v-if="msg" class="meta" :class="{ 'form-error': err }">{{ msg }}</p>

    <div class="table-wrap">
      <table class="cfg-table">
        <thead>
          <tr>
            <th>类型</th><th>canonical</th><th>别名</th><th>状态</th><th>seen</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in items" :key="row.id">
            <td><span class="pill">{{ row.entity_type }}</span></td>
            <td class="mono">{{ row.canonical }}</td>
            <td class="meta">{{ (row.aliases || []).join(', ') }}</td>
            <td>{{ row.status }}</td>
            <td>{{ row.seen_count }}</td>
            <td class="ops">
              <button type="button" class="secondary" @click="promote(row)" v-if="row.status === 'pending'">升格</button>
              <button type="button" class="secondary" @click="reject(row)" v-if="row.status !== 'rejected'">拒绝</button>
              <button type="button" class="secondary" @click="watch(row)">关注</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api'

const types = ['product', 'drug', 'org', 'target', 'indication']
const items = ref([])
const busy = ref(false)
const msg = ref('')
const err = ref(false)
const entityType = ref('')
const status = ref('')
const q = ref('')
const form = reactive({ entity_type: 'org', canonical: '', aliasesText: '' })

async function reload() {
  busy.value = true
  msg.value = ''
  try {
    const data = await api.entities({
      entity_type: entityType.value,
      status: status.value,
      q: q.value,
      page: 1,
      page_size: 100,
    })
    items.value = data.items || []
  } catch (e) {
    err.value = true
    msg.value = e.message || '加载失败'
  } finally {
    busy.value = false
  }
}

async function createOne() {
  busy.value = true
  err.value = false
  try {
    await api.createEntity({
      entity_type: form.entity_type,
      canonical: form.canonical,
      aliases: form.aliasesText.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      status: 'active',
    })
    form.canonical = ''
    form.aliasesText = ''
    msg.value = '已创建'
    await reload()
  } catch (e) {
    err.value = true
    msg.value = e.message || '创建失败'
  } finally {
    busy.value = false
  }
}

async function promote(row) {
  await api.updateEntity(row.id, { status: 'active' })
  await reload()
}

async function reject(row) {
  await api.updateEntity(row.id, { status: 'rejected' })
  await reload()
}

async function watch(row) {
  try {
    await api.addEntityWatch(row.id)
    msg.value = `已关注 ${row.canonical}`
    err.value = false
  } catch (e) {
    err.value = true
    msg.value = e.message || '关注失败（需登录）'
  }
}

async function doImport() {
  busy.value = true
  try {
    const stats = await api.importEntities()
    msg.value = `导入完成：${JSON.stringify(stats)}`
    err.value = false
    await reload()
  } catch (e) {
    err.value = true
    msg.value = e.message || '导入失败'
  } finally {
    busy.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.filters, .create-row, .ops { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; align-items: center; }
.filters input, .create-row input, select { min-width: 120px; }
.ops button { font-size: 12px; }
</style>
