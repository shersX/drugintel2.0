<template>
  <section class="card reveal">
    <div class="sec-mark"><span class="no">E</span><h3>实体词典</h3><span class="rule"></span></div>
    <p class="meta hint">
      canonical + aliases 归一化。中英文智能合并：高置信自动并，中置信进「待合并」审核。
    </p>

    <div class="tabs">
      <button type="button" :class="{ active: tab === 'lexicon' }" @click="tab = 'lexicon'">词典</button>
      <button type="button" :class="{ active: tab === 'merge' }" @click="switchMerge">
        待合并
        <span v-if="mergeTotal" class="badge">{{ mergeTotal }}</span>
      </button>
    </div>

    <template v-if="tab === 'lexicon'">
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
        <button class="secondary" :disabled="busy" @click="doResolve">跑智能合并</button>
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
    </template>

    <template v-else>
      <div class="filters">
        <select v-model="mergeType" @change="reloadMerge">
          <option value="">全部类型</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>
        <select v-model="mergeStatus" @change="reloadMerge">
          <option value="pending">pending</option>
          <option value="auto">auto</option>
          <option value="accepted">accepted</option>
          <option value="rejected">rejected</option>
        </select>
        <button class="secondary" :disabled="busy" @click="reloadMerge">刷新</button>
        <button class="secondary" :disabled="busy" @click="doResolve">跑智能合并</button>
      </div>
      <p v-if="msg" class="meta" :class="{ 'form-error': err }">{{ msg }}</p>
      <div v-if="!mergeItems.length" class="meta empty">暂无待审合并候选</div>
      <ul class="merge-list">
        <li v-for="c in mergeItems" :key="c.id" class="merge-card">
          <div class="merge-top">
            <span class="pill">{{ c.entity_type }}</span>
            <span class="score">置信 {{ Number(c.score || 0).toFixed(2) }}</span>
            <span class="meta">{{ c.status }}</span>
          </div>
          <div class="pair">
            <div>
              <strong class="mono">{{ c.left?.canonical }}</strong>
              <p class="meta">{{ (c.left?.aliases || []).join(', ') || '无别名' }}</p>
            </div>
            <span class="vs">↔</span>
            <div>
              <strong class="mono">{{ c.right?.canonical }}</strong>
              <p class="meta">{{ (c.right?.aliases || []).join(', ') || '无别名' }}</p>
            </div>
          </div>
          <p v-if="c.llm_reason" class="reason">{{ c.llm_reason }}</p>
          <p class="meta tip">
            共现 {{ c.signals?.cooccur ?? 0 }}
            · 中英形态 {{ c.signals?.cjk_latin ? '是' : '否' }}
            <template v-if="c.signals?.embed_sim != null"> · 嵌入召回 {{ c.signals.embed_sim }}</template>
          </p>
          <ul v-if="(c.signals?.titles || []).length" class="titles">
            <li v-for="(t, i) in c.signals.titles" :key="i">{{ t }}</li>
          </ul>
          <div class="ops" v-if="c.status === 'pending'">
            <button type="button" :disabled="busy" @click="acceptMerge(c)">确认合并</button>
            <button type="button" class="secondary" :disabled="busy" @click="rejectMerge(c)">拒绝</button>
          </div>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api'

const types = ['product', 'drug', 'org', 'target', 'indication']
const tab = ref('lexicon')
const items = ref([])
const mergeItems = ref([])
const mergeTotal = ref(0)
const busy = ref(false)
const msg = ref('')
const err = ref(false)
const entityType = ref('')
const status = ref('')
const q = ref('')
const mergeType = ref('')
const mergeStatus = ref('pending')
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

async function reloadMerge() {
  busy.value = true
  msg.value = ''
  try {
    const data = await api.entityMergeCandidates({
      status: mergeStatus.value,
      entity_type: mergeType.value,
      page: 1,
      page_size: 50,
    })
    mergeItems.value = data.items || []
    if (mergeStatus.value === 'pending') mergeTotal.value = data.total || 0
  } catch (e) {
    err.value = true
    msg.value = e.message || '加载失败'
  } finally {
    busy.value = false
  }
}

function switchMerge() {
  tab.value = 'merge'
  reloadMerge()
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

async function doResolve() {
  busy.value = true
  err.value = false
  try {
    const stats = await api.resolveEntityAliases({ limit: 50, use_embedding: true })
    msg.value = `智能合并完成：自动 ${stats.auto_merged || 0}，待审 ${stats.queued || 0}，低分丢弃 ${stats.dropped_low || 0}`
    await reload()
    await reloadMerge()
    tab.value = 'merge'
  } catch (e) {
    err.value = true
    msg.value = e.message || '智能合并失败'
  } finally {
    busy.value = false
  }
}

async function acceptMerge(c) {
  busy.value = true
  try {
    const r = await api.acceptEntityMergeCandidate(c.id)
    msg.value = `已合并 → ${r.canonical || r.keep_id}`
    err.value = false
    await reloadMerge()
  } catch (e) {
    err.value = true
    msg.value = e.message || '确认失败'
  } finally {
    busy.value = false
  }
}

async function rejectMerge(c) {
  busy.value = true
  try {
    await api.rejectEntityMergeCandidate(c.id)
    msg.value = '已拒绝该候选'
    err.value = false
    await reloadMerge()
  } catch (e) {
    err.value = true
    msg.value = e.message || '拒绝失败'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await reload()
  try {
    const data = await api.entityMergeCandidates({ status: 'pending', page: 1, page_size: 1 })
    mergeTotal.value = data.total || 0
  } catch {
    /* ignore */
  }
})
</script>

<style scoped>
.tabs { display: flex; gap: 8px; margin: 12px 0; }
.tabs button {
  border: 1px solid var(--rule, #e5e7eb); background: var(--paper); padding: 6px 14px;
  border-radius: 8px; cursor: pointer;
}
.tabs button.active {
  border-color: var(--moss, #4a7c59);
  background: var(--wash, #eef3ea);
  color: var(--pine, #1f4d3a);
}
.badge {
  display: inline-block; margin-left: 6px; background: #111; color: #fff;
  border-radius: 999px; padding: 0 6px; font-size: 11px;
}
.filters, .create-row, .ops { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; align-items: center; }
.filters input, .create-row input, select { min-width: 120px; }
.ops button { font-size: 12px; }
.merge-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
.merge-card {
  border: 1px solid var(--rule, #e5e7eb); border-radius: 10px; padding: 12px 14px;
}
.merge-top { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.score { font-variant-numeric: tabular-nums; font-weight: 600; }
.pair {
  display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: start;
}
.vs { color: var(--ink-mute, #6b7280); padding-top: 2px; }
.reason { margin: 8px 0 4px; line-height: 1.5; }
.tip { margin: 4px 0; }
.titles { margin: 4px 0 0; padding-left: 18px; color: var(--ink-mute, #6b7280); font-size: 13px; }
.empty { padding: 16px 0; }
</style>
