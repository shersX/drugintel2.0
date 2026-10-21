<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Pipeline · 研发管线</div>
      <h1 class="ed-title">研发管线跟踪</h1>
      <p class="ed-lede">先声试点：官方管线图视觉抽取 · 进度变更留痕与订阅通知。</p>
    </header>

    <section class="card reveal filters">
      <input v-model="q" type="search" placeholder="搜索药物 / 适应症 / 公司" @keyup.enter="load" />
      <select v-model="stage">
        <option value="">全部阶段</option>
        <option v-for="s in stageOptions" :key="s" :value="s">{{ stageLabel(s) }}</option>
      </select>
      <select v-model="status">
        <option value="active">在册</option>
        <option value="inactive">已消失</option>
        <option value="">全部状态</option>
      </select>
      <button type="button" @click="load">筛选</button>
    </section>

    <p v-if="error" class="form-error">{{ error }}</p>

    <section class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>管线资产</h3><span class="rule"></span></div>
      <div v-if="loading" class="meta">加载中…</div>
      <div v-else-if="!items.length" class="empty"><div class="empty-title">暂无管线数据</div></div>
      <div v-else class="table-wrap">
        <table class="cfg-table">
          <thead>
            <tr>
              <th>药物</th><th>公司</th><th>适应症</th><th>阶段</th><th>领域</th><th>更新</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.id" class="clickable" @click="$router.push(`/pipeline/${row.id}`)">
              <td><strong>{{ row.drug_name }}</strong></td>
              <td>{{ row.company_name }}</td>
              <td>{{ row.indication || '—' }}</td>
              <td><span class="pill">{{ row.stage_label || row.current_stage }}</span></td>
              <td>{{ row.therapeutic_area || '—' }}</td>
              <td class="mono">{{ formatTime(row.updated_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="meta">共 {{ total }} 条</p>
    </section>

    <section class="card reveal">
      <div class="sec-mark"><span class="no">02</span><h3>最近变更</h3><span class="rule"></span></div>
      <div v-if="!changes.length" class="meta">暂无变更</div>
      <ul v-else class="change-list">
        <li v-for="c in changes" :key="c.id">
          <span class="kind" :class="c.change_kind">{{ kindLabel(c.change_kind) }}</span>
          <strong>{{ c.drug_name }}</strong>
          <span class="meta">{{ c.field }}：{{ c.old_label || c.old_value || '—' }} → {{ c.new_label || c.new_value || '—' }}</span>
          <span class="mono">{{ formatTime(c.detected_at) }}</span>
        </li>
      </ul>
    </section>

    <section class="card reveal">
      <div class="sec-mark"><span class="no">03</span><h3>交易 / 合作</h3><span class="rule"></span></div>
      <div v-if="!deals.length" class="meta">暂无交易记录</div>
      <ul v-else class="deal-list">
        <li v-for="d in deals" :key="d.id">
          <strong>{{ d.drug_name || d.company_name }}</strong>
          <span class="pill">{{ d.deal_type }}</span>
          <span>{{ d.counterparty || '' }}</span>
          <p class="meta">{{ d.summary }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { formatTime } from '../format'
import { useAsync } from '../composables'

const q = ref('')
const stage = ref('')
const status = ref('active')
const items = ref([])
const total = ref(0)
const changes = ref([])
const deals = ref([])
const { loading, error, run } = useAsync()

const stageOptions = ['preclinical', 'phase1', 'phase2', 'phase3', 'nda', 'approved', 'partner', 'unknown']
const stageMap = {
  preclinical: '临床前',
  phase1: 'I 期',
  phase2: 'II 期',
  phase3: 'III 期',
  nda: '申报上市',
  approved: '已获批',
  partner: '合作方推进',
  unknown: '未知',
}
function stageLabel(s) {
  return stageMap[s] || s
}
function kindLabel(k) {
  return { created: '新建', updated: '更新', removed: '消失' }[k] || k
}

async function load() {
  const data = await run(() =>
    Promise.all([
      api.pipelineAssets({ q: q.value, stage: stage.value, status: status.value, page: 1, page_size: 50 }),
      api.pipelineChanges({ limit: 20 }),
      api.pipelineDeals(20),
    ]),
  )
  if (!data) return
  const [a, c, d] = data
  items.value = a?.items || []
  total.value = a?.total || 0
  changes.value = c?.items || []
  deals.value = d?.items || []
}

onMounted(load)
</script>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
  align-items: center;
}
.filters input, .filters select { min-width: 160px; }
.clickable { cursor: pointer; }
.clickable:hover { background: color-mix(in srgb, var(--moss) 8%, transparent); }
.change-list, .deal-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.change-list li, .deal-list li {
  display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: baseline;
  padding: 8px 0; border-bottom: 1px solid var(--line);
}
.kind { font-size: 12px; font-weight: 700; text-transform: uppercase; }
.kind.removed { color: var(--clay); }
.kind.created { color: var(--moss); }
.kind.updated { color: var(--pine); }
</style>
