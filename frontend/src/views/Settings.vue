<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Admin · 系统配置</div>
      <h1 class="ed-title">系统设置</h1>
      <p class="ed-lede">模型、检索、爬虫与关键词。改完即对后续请求和采集生效。</p>
    </header>

    <nav class="tabs reveal" aria-label="设置分区">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="tab"
        :class="{ on: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >{{ tab.label }}</button>
    </nav>

    <!-- 模型配置 -->
    <div v-show="activeTab === 'models'">
      <section class="card status-strip reveal">
        <div class="status-top">
          <div>
            <div class="status-label">当前生效</div>
            <div class="status-source">{{ activeSourceLabel }}</div>
          </div>
          <div class="status-dim">
            <span class="status-label">库向量维度</span>
            <strong>{{ vectorDim || '—' }}</strong>
          </div>
        </div>
        <div class="caps">
          <div class="cap" :class="{ warn: activeCaps.chat.warn }">
            <span class="cap-k">对话</span>
            <span class="cap-v mono">{{ activeCaps.chat.text }}</span>
          </div>
          <div class="cap" :class="{ warn: activeCaps.embedding.warn }">
            <span class="cap-k">嵌入</span>
            <span class="cap-v mono">{{ activeCaps.embedding.text }}</span>
          </div>
          <div class="cap" :class="{ warn: activeCaps.rerank.warn }">
            <span class="cap-k">重排</span>
            <span class="cap-v mono">{{ activeCaps.rerank.text }}</span>
          </div>
        </div>
        <p v-if="dimMismatch" class="status-warn">启用配置的嵌入维度与库中不一致，启用前会要求确认并重建向量索引。</p>
      </section>

      <div class="list-toolbar reveal">
        <div class="sec-mark"><span class="no">01</span><h3>已保存配置</h3><span class="rule"></span></div>
        <button
          type="button"
          class="secondary"
          :disabled="busy || editingId === 'new'"
          @click="startCreate"
        >新增配置</button>
      </div>

      <section v-if="editingId === 'new'" class="card profile-edit reveal">
        <div class="edit-head">
          <strong>新增一套接口</strong>
        </div>
        <ProfileForm
          :key="draftKey"
          :model="draft"
          :busy="busy"
          :notices="draftNotices"
          allow-sync
          show-cancel
          submit-label="保存"
          @submit="create"
          @test="testDraft"
          @cancel="cancelEdit"
        />
        <p v-if="error" class="form-error">{{ error }}</p>
      </section>

      <section class="profile-list reveal">
        <article v-for="item in profiles" :key="item.id" class="card profile">
          <div class="profile-summary">
            <div class="profile-title">
              <strong>{{ item.name || `配置 #${item.id}` }}</strong>
              <span class="pill" :class="item.is_active ? 'ok' : ''">{{ item.is_active ? '启用中' : '未启用' }}</span>
            </div>
            <div class="profile-tags">
              <span class="tag" :class="{ miss: !item.has_chat_key }">对话 {{ item.chat_model || '—' }}</span>
              <span class="tag" :class="{ miss: !item.has_embedding_key }">嵌入 {{ item.embedding_model || '—' }}·{{ item.embedding_dim || '—' }}</span>
              <span class="tag" :class="{ miss: !item.has_reranker_key }">重排 {{ item.reranker_model || '—' }}</span>
            </div>
            <div class="row profile-actions">
              <button type="button" class="secondary" :disabled="busy || item.is_active" @click="activate(item)">启用</button>
              <button
                type="button"
                class="secondary"
                :disabled="busy"
                @click="toggleEdit(item.id)"
              >{{ editingId === item.id ? '收起' : '编辑' }}</button>
              <button type="button" class="ghost danger-ghost" :disabled="busy" @click="remove(item)">删除</button>
            </div>
          </div>
          <div v-if="editingId === item.id" class="profile-edit-body">
            <ProfileForm
              :model="item"
              :stamp="revision"
              :busy="busy"
              :notices="item.notices"
              :keep-chat="item.has_chat_key"
              :keep-embedding="item.has_embedding_key"
              :keep-rerank="item.has_reranker_key"
              show-cancel
              submit-label="保存修改"
              @submit="save(item, $event)"
              @test="testSaved(item, $event)"
              @cancel="cancelEdit"
            />
          </div>
          <p v-if="item.error" class="form-error">{{ item.error }}</p>
        </article>
        <div v-if="!profiles.length && !loading && editingId !== 'new'" class="card empty">
          <div class="empty-title">还没有保存的接口</div>
          <p>点上方「新增配置」，保存后再启用。</p>
        </div>
      </section>
    </div>

    <!-- RAG -->
    <section v-show="activeTab === 'rag'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>RAG 检索参数</h3><span class="rule"></span></div>
      <p class="meta hint">问答检索条数与相关性阈值。客户端不再传 top_k，一律以这里为准。</p>
      <div class="field-grid">
        <div class="field">
          <label for="rag-top-k">top_k（1–50）</label>
          <input id="rag-top-k" type="number" min="1" max="50" v-model.number="ragForm.top_k" />
        </div>
        <div class="field">
          <label for="rag-min-score">相关性阈值（0–1）</label>
          <input id="rag-min-score" type="number" min="0" max="1" step="0.01" v-model.number="ragForm.min_relevance_score" />
        </div>
      </div>
      <div class="row">
        <button type="button" :disabled="ragBusy" @click="saveRag">{{ ragBusy ? '保存中…' : '保存' }}</button>
      </div>
      <p v-if="ragMsg" class="meta" :class="{ 'form-error': ragErr }">{{ ragMsg }}</p>
    </section>

    <!-- 爬虫注册表 -->
    <section v-show="activeTab === 'crawlers'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>爬虫注册表</h3><span class="rule"></span></div>
      <p class="meta hint">禁用后不会出现在监控页勾选列表。页数 / 并发 / 是否抓详情对下一轮采集生效。</p>
      <div class="table-wrap" v-if="crawlerRows.length">
        <table class="cfg-table">
          <thead>
            <tr>
              <th>来源</th>
              <th>启用</th>
              <th>页数</th>
              <th>并发</th>
              <th>抓详情</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in crawlerRows" :key="row.crawler_key">
              <td>
                <strong>{{ row.name }}</strong>
                <div class="meta mono">{{ row.crawler_key }}</div>
              </td>
              <td><input type="checkbox" v-model="row.enabled" /></td>
              <td><input type="number" min="1" max="50" v-model.number="row.page_count" class="num" /></td>
              <td><input type="number" min="1" max="20" v-model.number="row.concurrency" class="num" /></td>
              <td><input type="checkbox" v-model="row.fetch_details" /></td>
              <td>
                <button type="button" class="secondary" :disabled="crawlerBusy === row.crawler_key" @click="saveCrawler(row)">
                  {{ crawlerBusy === row.crawler_key ? '…' : '保存' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="crawlerMsg" class="meta" :class="{ 'form-error': crawlerErr }">{{ crawlerMsg }}</p>
    </section>

    <!-- 关键词 -->
    <section v-show="activeTab === 'keywords'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>过滤关键词</h3><span class="rule"></span></div>
      <p class="meta hint">修改后下一轮采集/过滤立即生效（服务端缓存已清）。首次启动会从 keywords.yaml 导入。</p>

      <div class="kw-toolbar">
        <div class="seg">
          <button type="button" class="seg-btn" :class="{ on: kwCategory === '靶点' }" @click="setKwCategory('靶点')">靶点</button>
          <button type="button" class="seg-btn" :class="{ on: kwCategory === '公司' }" @click="setKwCategory('公司')">公司</button>
        </div>
        <input class="search" type="search" placeholder="搜索规范名或别名" v-model="kwQuery" @keyup.enter="loadKeywords(1)" />
        <button type="button" class="secondary" :disabled="kwBusy" @click="loadKeywords(1)">搜索</button>
      </div>

      <div class="kw-new">
        <input type="text" placeholder="新规范名" v-model="kwNew.canonical" />
        <input type="text" placeholder="别名，逗号分隔" v-model="kwNew.aliasesText" />
        <button type="button" :disabled="kwBusy || !kwNew.canonical.trim()" @click="createKeyword">新增</button>
      </div>

      <div class="table-wrap" v-if="kwItems.length">
        <table class="cfg-table">
          <thead>
            <tr>
              <th>规范名</th>
              <th>别名</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in kwItems" :key="item.id">
              <td><input type="text" v-model="item.canonical" class="wide" /></td>
              <td><input type="text" v-model="item.aliasesText" class="wide" placeholder="逗号分隔" /></td>
              <td class="actions">
                <button type="button" class="secondary" :disabled="kwBusy" @click="saveKeyword(item)">保存</button>
                <button type="button" class="ghost danger-ghost" :disabled="kwBusy" @click="removeKeyword(item)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!kwBusy" class="empty">
        <div class="empty-title">暂无关键词</div>
        <p>可新增，或从 YAML 重新导入。</p>
      </div>

      <div class="row kw-pager">
        <button type="button" class="secondary" :disabled="kwPage <= 1 || kwBusy" @click="loadKeywords(kwPage - 1)">上一页</button>
        <span class="meta">第 {{ kwPage }} 页 · 共 {{ kwTotal }} 条</span>
        <button type="button" class="secondary" :disabled="kwPage * kwPageSize >= kwTotal || kwBusy" @click="loadKeywords(kwPage + 1)">下一页</button>
        <button type="button" class="ghost" :disabled="kwBusy" @click="reimportKeywords">从 YAML 重新导入</button>
      </div>
      <p v-if="kwMsg" class="meta" :class="{ 'form-error': kwErr }">{{ kwMsg }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import ProfileForm from './ProfileForm.vue'

const tabs = [
  { id: 'models', label: '模型配置' },
  { id: 'rag', label: 'RAG 检索' },
  { id: 'crawlers', label: '爬虫注册表' },
  { id: 'keywords', label: '过滤关键词' },
]
const activeTab = ref('models')

const { loading, error, run } = useAsync()
const profiles = ref([])
const vectorDim = ref(null)
const busy = ref(false)
const slotLabel = { chat: '对话', embedding: '嵌入', rerank: '重排' }
const draftNotices = reactive({ chat: null, embedding: null, rerank: null })
const revision = ref(0)
const draftKey = ref(0)
const draft = reactive(blank())
/** @type {import('vue').Ref<'new' | number | null>} */
const editingId = ref(null)

const activeProfile = computed(() => profiles.value.find((item) => item.is_active) || null)

const activeSourceLabel = computed(() => {
  if (activeProfile.value) return activeProfile.value.name || `配置 #${activeProfile.value.id}`
  return '未启用配置 · 使用 .env'
})

const activeCaps = computed(() => {
  const row = activeProfile.value
  if (!row) {
    return {
      chat: { text: '.env 默认', warn: false },
      embedding: { text: '.env 默认', warn: false },
      rerank: { text: '.env 默认', warn: false },
    }
  }
  return {
    chat: {
      text: row.has_chat_key ? (row.chat_model || '—') : '缺少 Key',
      warn: !row.has_chat_key,
    },
    embedding: {
      text: row.has_embedding_key
        ? `${row.embedding_model || '—'} · ${row.embedding_dim || '—'} 维`
        : '缺少 Key',
      warn: !row.has_embedding_key,
    },
    rerank: {
      text: row.has_reranker_key ? (row.reranker_model || '—') : '缺少 Key',
      warn: !row.has_reranker_key,
    },
  }
})

const dimMismatch = computed(() => {
  const row = activeProfile.value
  if (!row || vectorDim.value == null || row.embedding_dim == null) return false
  return Number(row.embedding_dim) !== Number(vectorDim.value)
})

function startCreate() {
  error.value = ''
  Object.assign(draft, blank())
  draftKey.value += 1
  editingId.value = 'new'
}

function toggleEdit(id) {
  editingId.value = editingId.value === id ? null : id
}

function cancelEdit() {
  editingId.value = null
  error.value = ''
}

const ragForm = reactive({ top_k: 10, min_relevance_score: 0.25 })
const ragBusy = ref(false)
const ragMsg = ref('')
const ragErr = ref(false)

const crawlerRows = ref([])
const crawlerBusy = ref('')
const crawlerMsg = ref('')
const crawlerErr = ref(false)

const kwCategory = ref('靶点')
const kwQuery = ref('')
const kwItems = ref([])
const kwPage = ref(1)
const kwPageSize = 20
const kwTotal = ref(0)
const kwBusy = ref(false)
const kwMsg = ref('')
const kwErr = ref(false)
const kwNew = reactive({ canonical: '', aliasesText: '' })
const loaded = reactive({ models: false, rag: false, crawlers: false, keywords: false })

function blank() {
  return {
    name: '',
    api_key: '',
    base_url: 'https://api.siliconflow.cn/v1',
    chat_model: 'deepseek-ai/DeepSeek-V4-Flash',
    embedding_api_key: '',
    embedding_base_url: 'https://api.siliconflow.cn/v1',
    embedding_model: 'BAAI/bge-m3',
    embedding_dim: 1024,
    reranker_api_key: '',
    reranker_base_url: 'https://api.siliconflow.cn/v1',
    reranker_model: 'BAAI/bge-reranker-v2-m3',
  }
}

function parseAliases(text) {
  return String(text || '')
    .split(/[,，;；\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function applyDefaults(defaults) {
  if (!defaults) return
  draft.base_url = defaults.base_url || draft.base_url
  draft.chat_model = defaults.chat_model || draft.chat_model
  draft.embedding_base_url = defaults.embedding_base_url || draft.embedding_base_url
  draft.embedding_model = defaults.embedding_model || draft.embedding_model
  draft.embedding_dim = defaults.embedding_dim || draft.embedding_dim
  draft.reranker_base_url = defaults.reranker_base_url || draft.reranker_base_url
  draft.reranker_model = defaults.reranker_model || draft.reranker_model
}

function isDimMismatch(err) {
  return err?.status === 409 && err.detail?.code === 'dimension_mismatch'
}

async function load() {
  const data = await run(() => api.llmProfiles())
  if (!data) return
  profiles.value = (data.profiles || []).map((item) => ({
    ...item,
    api_key: '',
    embedding_api_key: '',
    reranker_api_key: '',
    notices: { chat: null, embedding: null, rerank: null },
    error: '',
  }))
  vectorDim.value = data.vector_dim
  applyDefaults(data.defaults)
  revision.value += 1
  loaded.models = true
}

async function create(form) {
  busy.value = true
  error.value = ''
  try {
    await api.createLlmProfile(form)
    Object.assign(draft, blank())
    draftKey.value += 1
    editingId.value = null
    await load()
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    busy.value = false
  }
}

async function save(item, form, rebuild = false) {
  item.error = ''
  busy.value = true
  try {
    await api.updateLlmProfile(item.id, { ...form, rebuild })
    editingId.value = null
    await load()
  } catch (e) {
    if (!rebuild && isDimMismatch(e) && window.confirm(e.message)) {
      try {
        await api.updateLlmProfile(item.id, { ...form, rebuild: true })
        editingId.value = null
        await load()
      } catch (err) {
        item.error = err.message || '保存失败'
      }
      return
    }
    item.error = e.message || '保存失败'
  } finally {
    busy.value = false
  }
}

async function activate(item, rebuild = false) {
  item.error = ''
  busy.value = true
  try {
    await api.activateLlmProfile(item.id, rebuild)
    await load()
  } catch (e) {
    if (!rebuild && isDimMismatch(e) && window.confirm(e.message)) {
      try {
        await api.activateLlmProfile(item.id, true)
        await load()
      } catch (err) {
        item.error = err.message || '启用失败'
      }
      return
    }
    item.error = e.message || '启用失败'
  } finally {
    busy.value = false
  }
}

async function remove(item) {
  if (!window.confirm(`删除「${item.name || `配置 #${item.id}`}」？`)) return
  busy.value = true
  try {
    await api.deleteLlmProfile(item.id)
    if (editingId.value === item.id) editingId.value = null
    await load()
  } catch (e) {
    error.value = e.message || '删除失败'
  } finally {
    busy.value = false
  }
}

function beginTest(target, slot) {
  const label = slotLabel[slot] || '接口'
  target[slot] = { ok: null, text: `正在测试${label}…` }
}

async function finishTest(target, slot, runFn) {
  beginTest(target, slot)
  const label = slotLabel[slot] || '接口'
  busy.value = true
  try {
    await runFn()
    target[slot] = { ok: true, text: `${label}连接成功` }
  } catch (e) {
    target[slot] = { ok: false, text: e.message || '连接失败' }
  } finally {
    busy.value = false
  }
}

async function testDraft(form) {
  await finishTest(draftNotices, form.slot, () => api.testLlmProfile({
    base_url: form.base_url,
    api_key: form.api_key,
    slot: form.slot,
  }))
}

async function testSaved(item, form) {
  await finishTest(item.notices, form.slot, () => api.testLlmProfile({
    base_url: form.base_url,
    api_key: form.api_key,
    profile_id: item.id,
    slot: form.slot,
  }))
}

async function loadRag() {
  ragMsg.value = ''
  try {
    const data = await api.ragConfig()
    ragForm.top_k = data.top_k
    ragForm.min_relevance_score = data.min_relevance_score
    loaded.rag = true
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '加载失败'
  }
}

async function saveRag() {
  ragBusy.value = true
  ragMsg.value = ''
  ragErr.value = false
  try {
    const data = await api.updateRagConfig({
      top_k: ragForm.top_k,
      min_relevance_score: ragForm.min_relevance_score,
    })
    ragForm.top_k = data.top_k
    ragForm.min_relevance_score = data.min_relevance_score
    ragMsg.value = '已保存'
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '保存失败'
  } finally {
    ragBusy.value = false
  }
}

async function loadCrawlers() {
  crawlerMsg.value = ''
  try {
    crawlerRows.value = await api.adminCrawlers()
    loaded.crawlers = true
  } catch (e) {
    crawlerErr.value = true
    crawlerMsg.value = e.message || '加载失败'
  }
}

async function saveCrawler(row) {
  crawlerBusy.value = row.crawler_key
  crawlerMsg.value = ''
  crawlerErr.value = false
  try {
    const data = await api.updateAdminCrawler(row.crawler_key, {
      enabled: row.enabled,
      page_count: row.page_count,
      concurrency: row.concurrency,
      fetch_details: row.fetch_details,
    })
    Object.assign(row, data)
    crawlerMsg.value = `已保存 ${row.name}`
  } catch (e) {
    crawlerErr.value = true
    crawlerMsg.value = e.message || '保存失败'
  } finally {
    crawlerBusy.value = ''
  }
}

function setKwCategory(cat) {
  kwCategory.value = cat
  loadKeywords(1)
}

async function loadKeywords(page = 1) {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    const data = await api.adminKeywords({
      category: kwCategory.value,
      q: kwQuery.value.trim(),
      page,
      page_size: kwPageSize,
    })
    kwItems.value = (data.items || []).map((item) => ({
      ...item,
      aliasesText: (item.aliases || []).join(', '),
    }))
    kwTotal.value = data.total || 0
    kwPage.value = data.page || page
    loaded.keywords = true
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '加载失败'
  } finally {
    kwBusy.value = false
  }
}

async function createKeyword() {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.createAdminKeyword({
      category: kwCategory.value,
      canonical: kwNew.canonical.trim(),
      aliases: parseAliases(kwNew.aliasesText),
    })
    kwNew.canonical = ''
    kwNew.aliasesText = ''
    kwMsg.value = '已新增'
    await loadKeywords(1)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '新增失败'
  } finally {
    kwBusy.value = false
  }
}

async function saveKeyword(item) {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.updateAdminKeyword(item.id, {
      category: kwCategory.value,
      canonical: item.canonical.trim(),
      aliases: parseAliases(item.aliasesText),
    })
    kwMsg.value = '已保存'
    await loadKeywords(kwPage.value)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '保存失败'
  } finally {
    kwBusy.value = false
  }
}

async function removeKeyword(item) {
  if (!window.confirm(`删除「${item.canonical}」？`)) return
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.deleteAdminKeyword(item.id)
    kwMsg.value = '已删除'
    await loadKeywords(kwPage.value)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '删除失败'
  } finally {
    kwBusy.value = false
  }
}

async function reimportKeywords() {
  const overwrite = kwTotal.value > 0
  if (overwrite && !window.confirm('将清空当前过滤关键词并从 keywords.yaml 重新导入，继续？')) {
    return
  }
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    const data = await api.reimportAdminKeywords(overwrite)
    kwMsg.value = `已导入 ${data.inserted} 条`
    await loadKeywords(1)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '导入失败'
  } finally {
    kwBusy.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'models' && !loaded.models) load()
  if (tab === 'rag' && !loaded.rag) loadRag()
  if (tab === 'crawlers' && !loaded.crawlers) loadCrawlers()
  if (tab === 'keywords' && !loaded.keywords) loadKeywords(1)
})

onMounted(load)
</script>

<style scoped>
.status-strip { margin-bottom: 28px; }
.status-top {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px 24px;
  margin-bottom: 16px;
}
.status-label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
  margin-bottom: 4px;
}
.status-source {
  font-family: var(--font-serif);
  font-size: clamp(22px, 2.4vw, 28px);
  font-weight: 700;
  color: var(--pine);
}
.status-dim strong {
  display: block;
  font-family: var(--font-mono);
  font-size: 22px;
  color: var(--pine);
}
.caps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}
.cap {
  padding: 10px 12px;
  background: var(--wash);
  border-radius: var(--r-md);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cap.warn { background: color-mix(in srgb, var(--clay) 10%, var(--paper)); }
.cap-k {
  font-size: var(--fs-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
}
.cap-v { font-size: var(--fs-sm); color: var(--ink); word-break: break-all; }
.cap.warn .cap-v { color: var(--clay); font-weight: 650; }
.status-warn { margin: 12px 0 0; color: var(--clay); font-size: var(--fs-sm); }
.list-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.list-toolbar .sec-mark { flex: 1; margin: 0; min-width: 200px; }
.profile-list { display: grid; gap: 12px; }
.profile { margin: 0; }
.profile-summary { display: grid; gap: 12px; }
.profile-title { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; }
.profile-title strong { font-family: var(--font-serif); font-size: var(--fs-h2); }
.profile-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.tag {
  font-size: var(--fs-sm);
  font-family: var(--font-mono);
  padding: 4px 10px;
  background: var(--wash);
  border-radius: var(--r-sm);
  color: var(--ink-soft);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag.miss { color: var(--clay); background: color-mix(in srgb, var(--clay) 10%, var(--paper)); }
.profile-actions { margin: 0; }
.profile-edit { margin-bottom: 16px; }
.edit-head { margin-bottom: 14px; }
.profile-edit-body {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}
.form-error { color: var(--clay); margin: 8px 0 0; }
.mono { font-family: var(--font-mono); }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 24px; }
.tab {
  border: 1px solid var(--line, #d8d2c8);
  background: transparent;
  padding: 8px 14px;
  cursor: pointer;
  color: var(--ink-soft);
}
.tab.on { background: var(--ink, #1c1916); color: #f7f3eb; border-color: transparent; }
.field-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 16px 0; }
.hint { margin: 0 0 12px; }
.cfg-table { width: 100%; border-collapse: collapse; }
.cfg-table th, .cfg-table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line, #e6e0d6); vertical-align: middle; }
.cfg-table .num { width: 72px; }
.cfg-table .wide { width: 100%; min-width: 140px; }
.actions { white-space: nowrap; display: flex; gap: 8px; }
.kw-toolbar, .kw-new, .kw-pager { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
.kw-toolbar .search { flex: 1; min-width: 160px; }
.kw-new input { flex: 1; min-width: 140px; }
</style>
