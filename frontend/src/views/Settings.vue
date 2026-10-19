<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Admin · 系统配置</div>
      <h1 class="ed-title">系统设置</h1>
      <p class="ed-lede">模型接口、RAG 检索、爬虫注册表与过滤关键词。修改后立即对后续请求/采集生效。</p>
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
      <p v-if="usingEnv" class="card note">当前没有启用的配置，系统仍使用服务器上的 .env。嵌入和重排若未单独配置，会沿用对话的地址和密钥。</p>
      <p v-else class="card note">已启用一套接口。对话、嵌入、重排各自使用这一套里对应的地址和密钥。</p>
      <p class="card note">当前库中向量是 {{ vectorDim || '—' }} 维。启用另一维度前会要求确认，确认后清空已有新闻向量和事件中心向量并重建索引。历史新闻不会自动重新向量化，之后的采集只处理新文章。</p>

      <section class="card reveal">
        <div class="sec-mark"><span class="no">01</span><h3>新增一套</h3><span class="rule"></span></div>
        <ProfileForm
          :key="draftKey"
          :model="draft"
          :busy="busy"
          :notices="draftNotices"
          submit-label="保存"
          @submit="create"
          @test="testDraft"
        />
        <p v-if="error" class="form-error">{{ error }}</p>
      </section>

      <section class="reveal" style="margin-top:32px">
        <div class="sec-mark" v-if="profiles.length"><span class="no">02</span><h3>已保存</h3><span class="rule"></span></div>
        <article v-for="item in profiles" :key="item.id" class="card profile">
          <div class="profile-head">
            <span class="pill" :class="item.is_active ? 'ok' : ''">{{ item.is_active ? '启用中' : '未启用' }}</span>
          </div>
          <ProfileForm
            :model="item"
            :stamp="revision"
            :busy="busy"
            :notices="item.notices"
            :keep-chat="item.has_chat_key"
            :keep-embedding="item.has_embedding_key"
            :keep-rerank="item.has_reranker_key"
            submit-label="保存修改"
            @submit="save(item, $event)"
            @test="testSaved(item, $event)"
          />
          <p v-if="item.error" class="form-error">{{ item.error }}</p>
          <div class="row">
            <button type="button" class="secondary" :disabled="busy || item.is_active" @click="activate(item)">启用</button>
            <button type="button" class="ghost danger-ghost" :disabled="busy" @click="remove(item)">删除</button>
          </div>
        </article>
        <div v-if="!profiles.length && !loading" class="card empty">
          <div class="empty-title">还没有保存的接口</div>
          <p>先在上方新增一套，再点启用。</p>
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
import { onMounted, reactive, ref, watch } from 'vue'
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
const usingEnv = ref(true)
const vectorDim = ref(null)
const busy = ref(false)
const slotLabel = { chat: '对话', embedding: '嵌入', rerank: '重排' }
const draftNotices = reactive({ chat: null, embedding: null, rerank: null })
const revision = ref(0)
const draftKey = ref(0)
const draft = reactive(blank())

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
  usingEnv.value = Boolean(data.using_env)
  vectorDim.value = data.vector_dim
  applyDefaults(data.defaults)
  revision.value += 1
  loaded.models = true
}

async function create(form) {
  busy.value = true
  try {
    await api.createLlmProfile(form)
    Object.assign(draft, blank())
    draftKey.value += 1
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
    await load()
  } catch (e) {
    if (!rebuild && isDimMismatch(e) && window.confirm(e.message)) {
      try {
        await api.updateLlmProfile(item.id, { ...form, rebuild: true })
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
  busy.value = true
  try {
    await api.deleteLlmProfile(item.id)
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
.note { margin-bottom: 20px; color: var(--ink-soft); }
.profile { margin-bottom: 16px; }
.profile-head { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.form-error { color: var(--clay); margin: 8px 0 0; }
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
