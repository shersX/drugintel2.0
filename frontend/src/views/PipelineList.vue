<template>
  <div class="pipe-page">
    <p v-if="error" class="form-error">{{ error }}</p>

    <div class="pipe-grid">
      <section class="main-panel">
        <div class="modality-tabs" role="tablist">
          <button
            v-for="m in modalityTabs"
            :key="m.value"
            type="button"
            class="mod-tab"
            :class="{ on: state.modality === m.value }"
            @click="setModality(m.value)"
          >{{ m.label }}</button>
        </div>

        <div class="toolbar">
          <input
            v-model="state.q"
            type="search"
            class="search"
            placeholder="搜索药物 / 靶点 / 公司"
            @keyup.enter="onSearch"
          />
          <button type="button" class="export-btn" @click="exportCsv">导出</button>
          <span v-if="hasActiveFilters" class="meta filtered">已筛选</span>
        </div>

        <div class="table-wrap">
          <table class="pipe-table">
            <thead>
              <tr>
                <th class="col-check">
                  <input
                    type="checkbox"
                    :checked="allSelected"
                    :indeterminate.prop="someSelected"
                    @change="toggleAll"
                    @click.stop
                  />
                </th>
                <th>药物名称</th>
                <th>靶点</th>
                <th>适应症</th>
                <th>研发公司</th>
                <th class="progress-h">
                  <span>临床前</span><span>I期</span><span>II期</span><span>III期</span><span>申报</span><span>上市</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading && !items.length">
                <td colspan="6" class="empty-cell">加载中…</td>
              </tr>
              <tr v-else-if="!items.length">
                <td colspan="6" class="empty-cell">
                  <template v-if="hasActiveFilters">
                    <p>当前筛选条件下暂无管线资产</p>
                    <button type="button" class="ghost" @click="clearFilters">清空筛选</button>
                  </template>
                  <template v-else>
                    <p>暂无管线数据。可在系统管理 → 爬虫监控触发同步，或确认展示种子已导入。</p>
                    <router-link to="/monitor">前往爬虫监控</router-link>
                  </template>
                </td>
              </tr>
              <tr
                v-for="row in items"
                :key="row.id"
                class="clickable"
                @click="$router.push(`/pipeline/${row.id}`)"
              >
                <td class="col-check" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedIds.has(row.id)"
                    @change="toggleOne(row.id, $event)"
                  />
                </td>
                <td>
                  <strong>{{ row.drug_name }}</strong>
                  <span v-if="row.review_status === 'corrected'" class="rev-tag">已校对</span>
                </td>
                <td>{{ row.target || '—' }}</td>
                <td class="cell-ind">{{ row.indication || '—' }}</td>
                <td>{{ row.company_name || '—' }}</td>
                <td>
                  <PipelineStageBar :stage="row.current_stage" :label="row.stage_label" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <nav class="pager" v-if="total > 0">
          <button type="button" class="ghost" :disabled="state.page <= 1" @click="setPage(state.page - 1)">← 上一页</button>
          <span class="page-indicator">
            第 <b>{{ state.page }}</b> / {{ totalPages }} 页 · 共 {{ total }} 条
          </span>
          <button type="button" class="ghost" :disabled="state.page >= totalPages" @click="setPage(state.page + 1)">下一页 →</button>
        </nav>
      </section>

      <aside class="analytics-panel">
        <div class="analytics-card">
          <div class="card-h">
            <h3>靶点赛道对比</h3>
            <UiSelect
              v-model="compareTarget"
              class="compare-select"
              :options="compareTargetOptions"
              placeholder="全部靶点"
              size="sm"
              @change="loadAnalytics"
            />
          </div>
          <div v-if="!(compare.series || []).length" class="meta empty-side">暂无对比数据</div>
          <div v-else class="bars">
            <div v-for="s in compare.series" :key="s.company" class="bar-row">
              <div class="bar-name" :title="s.company">{{ s.company }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: barPct(s) + '%' }" />
              </div>
              <span class="bar-n">{{ sumCounts(s.counts) }}</span>
            </div>
          </div>
        </div>
        <div class="analytics-card">
          <div class="card-h"><h3>竞争格局</h3></div>
          <ol v-if="(competition.items || []).length" class="rank-list">
            <li v-for="c in competition.items" :key="c.company">
              <span class="rank">{{ c.rank }}</span>
              <div class="rank-body">
                <strong>{{ c.company }}</strong>
                <span class="meta">{{ c.pipeline_count }} 在研 · {{ c.clinical_count }} 临床</span>
              </div>
            </li>
          </ol>
          <p v-else class="meta empty-side">暂无企业数据</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import PipelineStageBar from '../components/PipelineStageBar.vue'
import UiSelect from '../components/UiSelect.vue'
import { useAsync } from '../composables'
import { usePipelineFilters } from '../composables/usePipelineFilters'

const {
  state,
  facets,
  revision,
  hasActiveFilters,
  filterParams,
  clearFilters,
  setModality,
  setPage,
  loadFacets,
  bump,
} = usePipelineFilters()

const items = ref([])
const total = ref(0)
const selectedIds = ref(new Set())
const compare = ref({ series: [], available_targets: [] })
const competition = ref({ items: [] })
const compareTarget = ref('')
const { loading, error, run } = useAsync()

const modalityTabs = [
  { value: '', label: '全部' },
  { value: 'small_molecule', label: '小分子' },
  { value: 'antibody', label: '抗体' },
  { value: 'cell_therapy', label: '细胞治疗' },
  { value: 'gene_therapy', label: '基因治疗' },
  { value: 'nucleic_acid', label: '核酸药物' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / state.pageSize)))
const allSelected = computed(
  () => items.value.length > 0 && items.value.every((r) => selectedIds.value.has(r.id)),
)
const someSelected = computed(
  () => items.value.some((r) => selectedIds.value.has(r.id)) && !allSelected.value,
)
const compareTargetOptions = computed(() =>
  (compare.value.available_targets || []).map((t) => ({
    value: t.value,
    label: t.value,
  })),
)

function onSearch() {
  state.page = 1
  bump()
}

function toggleOne(id, event) {
  const next = new Set(selectedIds.value)
  if (event.target.checked) next.add(id)
  else next.delete(id)
  selectedIds.value = next
}

function toggleAll(event) {
  if (event.target.checked) {
    selectedIds.value = new Set(items.value.map((r) => r.id))
  } else {
    selectedIds.value = new Set()
  }
}

function sumCounts(arr) {
  return (arr || []).reduce((a, b) => a + b, 0)
}

function barPct(s) {
  const n = sumCounts(s.counts)
  const max = Math.max(1, ...(compare.value.series || []).map((x) => sumCounts(x.counts)))
  return Math.round((n / max) * 100)
}

async function loadAnalytics() {
  try {
    const [tc, comp] = await Promise.all([
      api.pipelineTargetCompare(compareTarget.value),
      api.pipelineCompetition(8),
    ])
    compare.value = tc || { series: [], available_targets: [] }
    competition.value = comp || { items: [] }
  } catch {
    /* ignore */
  }
}

async function reload() {
  const data = await run(() =>
    Promise.all([
      api.pipelineAssets(filterParams()),
      api.pipelineFacets('active'),
    ]),
  )
  if (!data) return
  const [a, f] = data
  items.value = a?.items || []
  total.value = a?.total || 0
  if (f) facets.value = f
  selectedIds.value = new Set()
  await loadAnalytics()
}

function exportCsv() {
  window.open(api.pipelineAssetsExportUrl(filterParams()), '_blank')
}

watch(revision, () => { reload() })

onMounted(async () => {
  await loadFacets()
  await reload()
})
</script>

<style scoped>
.pipe-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 250px;
  gap: 12px;
  align-items: start;
}
.main-panel {
  min-width: 0;
  padding: 10px 12px 14px;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r-md);
}
.modality-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.mod-tab {
  border: 1px solid var(--line);
  background: transparent;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink-soft);
}
.mod-tab.on { background: var(--pine); color: var(--paper); border-color: var(--pine); }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.search { flex: 1; min-width: 160px; font-size: 13px; padding: 6px 10px; }
.export-btn {
  background: var(--pine);
  color: var(--paper);
  border: none;
  padding: 6px 12px;
  font-weight: 700;
  font-size: 12px;
  cursor: pointer;
  border-radius: 6px;
}
.filtered { margin-left: auto; font-size: 12px; }
.table-wrap { overflow-x: auto; }
.pipe-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pipe-table th, .pipe-table td {
  text-align: left;
  padding: 0 8px;
  height: 46px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}
.pipe-table th { font-size: 11px; color: var(--ink-mute); font-weight: 700; height: 36px; }
.col-check { width: 32px; text-align: center; }
.cell-ind { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.progress-h {
  display: grid !important;
  grid-template-columns: repeat(6, 1fr);
  gap: 0;
  font-size: 9px !important;
  min-width: 180px;
  text-align: center !important;
}
.clickable { cursor: pointer; }
.clickable:hover { background: color-mix(in srgb, var(--moss) 7%, transparent); }
.rev-tag { margin-left: 6px; font-size: 10px; color: var(--moss); font-weight: 700; }
.empty-cell {
  text-align: center;
  padding: 28px 16px !important;
  height: auto !important;
  color: var(--ink-mute);
  font-size: 13px;
}
.empty-cell p { margin: 0 0 8px; }
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}
.page-indicator {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--ink-mute);
}
.page-indicator b { color: var(--pine); }

.analytics-panel { display: grid; gap: 10px; align-content: start; }
.analytics-card {
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r-md);
  overflow: visible;
}
.analytics-card .card-h {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  overflow: visible;
}
.analytics-card h3 { margin: 0; font-size: 13px; flex: none; }
.compare-select {
  --ui-select-w: min(120px, 48%);
  flex: none;
}
.bars { display: grid; gap: 6px; max-height: 180px; overflow-y: auto; }
.bar-row {
  display: grid;
  grid-template-columns: 64px 1fr 24px;
  gap: 4px;
  align-items: center;
  font-size: 11px;
}
.bar-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track {
  height: 6px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--pine) 10%, transparent);
  overflow: hidden;
}
.bar-fill { height: 100%; background: var(--moss); border-radius: 99px; }
.bar-n { text-align: right; color: var(--ink-mute); }
.rank-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
.rank-list li { display: flex; gap: 8px; align-items: flex-start; }
.rank {
  width: 18px; height: 18px; border-radius: 50%;
  background: color-mix(in srgb, var(--moss) 16%, transparent);
  color: var(--pine); font-weight: 800; font-size: 10px;
  display: grid; place-items: center; flex-shrink: 0;
}
.rank-body { display: grid; gap: 1px; min-width: 0; }
.rank-body strong { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-side { font-size: 12px; padding: 4px 0; }

@media (max-width: 1100px) {
  .pipe-grid { grid-template-columns: 1fr; }
  .analytics-panel { grid-template-columns: 1fr 1fr; display: grid; }
}
@media (max-width: 700px) {
  .analytics-panel { grid-template-columns: 1fr; }
}
</style>
