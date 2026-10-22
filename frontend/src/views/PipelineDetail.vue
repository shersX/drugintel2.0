<template>
  <div>
    <header class="ed-head reveal">
      <router-link to="/pipeline" class="meta">← 返回管线列表</router-link>
      <div class="ed-kicker">Pipeline · 资产详情</div>
      <h1 class="ed-title">{{ form.drug_name || asset?.drug_name || '…' }}</h1>
      <p class="ed-lede">
        {{ form.company_name || asset?.company_name }} · {{ form.indication || '适应症未标注' }} ·
        {{ stageLabel(form.current_stage) }}
        <span v-if="asset?.review_status" class="rev">· {{ reviewLabel(asset.review_status) }}</span>
      </p>
    </header>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="saveMsg" class="ok-msg">{{ saveMsg }}</p>
    <div v-if="loading" class="meta">加载中…</div>

    <template v-else-if="asset">
      <section class="detail-edit reveal">
        <div class="sec-mark">
          <span class="no">01</span>
          <h3>{{ isAdmin ? '校对编辑' : '当前状态' }}</h3>
          <span class="rule"></span>
        </div>
        <p v-if="isAdmin" class="meta tip">
          保存后对应字段将锁定，后续管线同步不会覆盖。可勾选「标记已复核」。
        </p>
        <div class="form-grid">
          <label>药物名称<input v-model="form.drug_name" :disabled="!isAdmin" /></label>
          <label>通用名<input v-model="form.generic_name" :disabled="!isAdmin" /></label>
          <label>靶点<input v-model="form.target" :disabled="!isAdmin" /></label>
          <label>机制<input v-model="form.mechanism" :disabled="!isAdmin" /></label>
          <label>
            分子类型
            <UiSelect
              v-model="form.modality"
              :options="modalityOptions"
              :disabled="!isAdmin"
              :allow-empty="false"
              size="md"
              placeholder="选择分子类型"
            />
          </label>
          <label>
            阶段
            <UiSelect
              v-model="form.current_stage"
              :options="stageOptions"
              :disabled="!isAdmin"
              :allow-empty="false"
              size="md"
              placeholder="选择阶段"
            />
          </label>
          <label>适应症<input v-model="form.indication" :disabled="!isAdmin" /></label>
          <label>治疗领域<input v-model="form.therapeutic_area" :disabled="!isAdmin" /></label>
          <label>区域<input v-model="form.region" :disabled="!isAdmin" /></label>
          <label>
            状态
            <UiSelect
              v-model="form.status"
              :options="statusOptions"
              :disabled="!isAdmin"
              :allow-empty="false"
              size="md"
              placeholder="选择状态"
            />
          </label>
          <label class="span2">来源 URL<input v-model="form.source_url" :disabled="!isAdmin" /></label>
        </div>
        <div v-if="lockedFieldLabels.length" class="meta locks">
          已锁定字段：{{ lockedFieldLabels.join('、') }}
        </div>
        <div v-if="isAdmin" class="actions">
          <label class="chk">
            <input v-model="markReviewed" type="checkbox" />
            标记已复核
          </label>
          <button type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存校对' }}</button>
          <button type="button" class="secondary" :disabled="saving" @click="softDelete">软删除</button>
        </div>
        <div class="stage-preview">
          <span class="meta">进度预览</span>
          <PipelineStageBar :stage="form.current_stage" :label="stageLabel(form.current_stage)" />
        </div>
      </section>

      <section class="detail-block reveal">
        <div class="sec-mark"><span class="no">02</span><h3>变更时间线</h3><span class="rule"></span></div>
        <p v-if="!(asset.changes || []).length" class="meta empty-line">暂无变更记录</p>
        <ul v-else class="timeline">
          <li v-for="c in asset.changes" :key="c.id">
            <div class="t-head">
              <span class="kind" :class="c.change_kind">{{ kindLabel(c.change_kind) }}</span>
              <span v-if="c.source === 'manual'" class="src">人工</span>
              <span class="mono">{{ formatTime(c.detected_at) }}</span>
            </div>
            <p>
              <strong>{{ fieldLabel(c.field) }}</strong>：
              {{ c.old_label || c.old_value || '—' }} → {{ c.new_label || c.new_value || '—' }}
            </p>
            <div v-if="c.snapshot_id" class="snap-img">
              <img :src="api.pipelineSnapshotImageUrl(c.snapshot_id, 0)" alt="当次管线快照" loading="lazy" />
            </div>
          </li>
        </ul>
      </section>

      <section class="detail-block reveal">
        <div class="sec-mark"><span class="no">03</span><h3>关联交易（新闻）</h3><span class="rule"></span></div>
        <ul v-if="(asset.deals || []).length" class="deal-list">
          <li v-for="d in asset.deals" :key="d.id">
            <span class="pill">{{ d.deal_type }}</span>
            <router-link v-if="d.news_id" :to="`/news/${d.news_id}`">
              {{ d.news_title || d.summary || '新闻' }}
            </router-link>
            <span v-else>{{ d.summary }}</span>
          </li>
        </ul>
        <p v-else class="meta empty-line">暂无</p>
      </section>

      <section class="detail-block reveal">
        <div class="sec-mark"><span class="no">04</span><h3>关联新闻</h3><span class="rule"></span></div>
        <ul v-if="(asset.related_news || []).length" class="news-list">
          <li v-for="n in asset.related_news" :key="n.id">
            <router-link :to="`/news/${n.id}`">{{ n.title }}</router-link>
            <span class="mono meta">{{ formatTime(n.publish_time) }}</span>
          </li>
        </ul>
        <p v-else class="meta empty-line">暂无匹配新闻</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import PipelineStageBar from '../components/PipelineStageBar.vue'
import UiSelect from '../components/UiSelect.vue'
import { formatTime } from '../format'
import { useAsync } from '../composables'
import { session } from '../session'

const route = useRoute()
const router = useRouter()
const asset = ref(null)
const saveMsg = ref('')
const saving = ref(false)
const markReviewed = ref(false)
const { loading, error, run } = useAsync()

const isAdmin = computed(() => session.user?.role === 'admin')

const form = reactive({
  drug_name: '',
  company_name: '',
  generic_name: '',
  target: '',
  mechanism: '',
  modality: 'unknown',
  current_stage: 'unknown',
  indication: '',
  therapeutic_area: '',
  region: '',
  status: 'active',
  source_url: '',
})

const stageOptions = [
  { value: 'preclinical', label: '临床前' },
  { value: 'phase1', label: 'I 期' },
  { value: 'phase2', label: 'II 期' },
  { value: 'phase3', label: 'III 期' },
  { value: 'nda', label: '申报上市' },
  { value: 'approved', label: '已获批' },
  { value: 'partner', label: '合作方推进' },
  { value: 'unknown', label: '未知' },
]

const modalityOptions = [
  { value: 'small_molecule', label: '小分子' },
  { value: 'antibody', label: '抗体' },
  { value: 'cell_therapy', label: '细胞治疗' },
  { value: 'gene_therapy', label: '基因治疗' },
  { value: 'nucleic_acid', label: '核酸药物' },
  { value: 'other', label: '其他' },
  { value: 'unknown', label: '未知' },
]

const statusOptions = [
  { value: 'active', label: '在册' },
  { value: 'inactive', label: '已消失' },
]

const FIELD_LABELS = {
  drug_name: '药物名称',
  generic_name: '通用名',
  target: '靶点',
  mechanism: '机制',
  modality: '分子类型',
  current_stage: '阶段',
  stage: '阶段',
  indication: '适应症',
  therapeutic_area: '治疗领域',
  region: '区域',
  status: '状态',
  source_url: '来源 URL',
}

const lockedFieldLabels = computed(() =>
  (asset.value?.manual_fields || []).map((f) => FIELD_LABELS[f] || f),
)

function fieldLabel(key) {
  return FIELD_LABELS[key] || key
}
function stageLabel(s) {
  return stageOptions.find((x) => x.value === s)?.label || s || '—'
}
function reviewLabel(s) {
  return { auto: '自动抽取', reviewed: '已复核', corrected: '已校对' }[s] || s
}
function kindLabel(k) {
  return { created: '新建', updated: '更新', removed: '消失' }[k] || k
}

function fillForm(data) {
  form.drug_name = data.drug_name || ''
  form.company_name = data.company_name || ''
  form.generic_name = data.generic_name || ''
  form.target = data.target || ''
  form.mechanism = data.mechanism || ''
  form.modality = data.modality || 'unknown'
  form.current_stage = data.current_stage || 'unknown'
  form.indication = data.indication || ''
  form.therapeutic_area = data.therapeutic_area || ''
  form.region = data.region || ''
  form.status = data.status || 'active'
  form.source_url = data.source_url || ''
}

async function load() {
  saveMsg.value = ''
  const id = Number(route.params.id)
  const data = await run(() => api.pipelineAsset(id))
  asset.value = data || null
  if (data) fillForm(data)
}

async function save() {
  if (!asset.value) return
  saving.value = true
  saveMsg.value = ''
  try {
    const data = await api.patchPipelineAsset(asset.value.id, {
      target: form.target,
      mechanism: form.mechanism,
      generic_name: form.generic_name,
      modality: form.modality,
      current_stage: form.current_stage,
      indication: form.indication,
      therapeutic_area: form.therapeutic_area,
      region: form.region,
      status: form.status,
      source_url: form.source_url,
      mark_reviewed: markReviewed.value,
    })
    asset.value = data
    fillForm(data)
    saveMsg.value = '已保存校对'
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function softDelete() {
  if (!asset.value || !confirm('确认将该资产标为已消失？')) return
  await api.deletePipelineAsset(asset.value.id)
  router.push('/pipeline')
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<style scoped>
.detail-edit {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r-lg);
  padding: clamp(18px, 2.4vw, 28px);
}
.detail-block {
  margin-top: clamp(28px, 4vw, 40px);
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}
.detail-block .sec-mark { margin-bottom: 12px; }
.empty-line { margin: 0; }
.rev { color: var(--moss); font-weight: 700; }
.tip { margin: 0 0 12px; }
.ok-msg { color: var(--moss); font-weight: 700; }
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-mute);
}
.form-grid input {
  font-weight: 500;
  color: var(--ink);
}
.span2 { grid-column: 1 / -1; }
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-top: 16px;
}
.chk { font-size: 13px; display: flex; gap: 6px; align-items: center; font-weight: 600; }
.locks { margin-top: 10px; }
.stage-preview {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.stage-preview > .meta {
  flex-shrink: 0;
  white-space: nowrap;
}
.stage-preview :deep(.stage-bar) {
  width: auto;
  flex: 1;
  min-width: 168px;
  max-width: 280px;
}
.timeline { list-style: none; padding: 0; margin: 0; display: grid; gap: 16px; }
.timeline li { border-left: 2px solid var(--line); padding-left: 14px; }
.t-head { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
.kind { font-size: 12px; font-weight: 700; }
.kind.removed { color: var(--clay); }
.src {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--pine) 12%, transparent);
}
.snap-img img {
  max-width: min(100%, 480px);
  border-radius: 8px;
  border: 1px solid var(--line);
  margin-top: 8px;
}
.deal-list, .news-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.news-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: baseline;
}
</style>
