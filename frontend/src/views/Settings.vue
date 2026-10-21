<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Admin · 系统配置</div>
      <h1 class="ed-title">系统设置</h1>
      <p class="ed-lede">大模型、检索、邮件、爬虫与关键词。改完即对后续请求和采集生效。</p>
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

    <!-- 大模型 -->
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
          <div class="cap" :class="{ warn: activeCaps.vision.warn }">
            <span class="cap-k">视觉</span>
            <span class="cap-v mono">{{ activeCaps.vision.text }}</span>
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
              <span class="tag" :class="{ miss: !item.vision_model }">视觉 {{ item.vision_model || '未配置' }}</span>
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
              :profile-id="item.id"
              :keep-chat="item.has_chat_key"
              :keep-embedding="item.has_embedding_key"
              :keep-rerank="item.has_reranker_key"
              :keep-vision="item.has_vision_key"
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

    <!-- 邮件 SMTP -->
    <section v-show="activeTab === 'mail'" class="card reveal mail-card">
      <div class="sec-mark"><span class="no">01</span><h3>告警邮件 SMTP</h3><span class="rule"></span></div>
      <p class="meta hint">
        监测订阅命中后经此通道发信。建议先保存配置，再发测试邮件确认可通。
        <span v-if="smtpForm.source === 'env' && smtpForm.env_host">当前生效来自 .env，保存后将写入数据库。</span>
      </p>
      <div class="mail-status" :class="{ ok: smtpForm.ready, bad: !smtpForm.ready }">
        <strong>{{ smtpForm.message || (smtpForm.ready ? '通道已就绪' : '通道未就绪') }}</strong>
        <span v-if="smtpForm.password_set" class="meta">密码已保存</span>
      </div>
      <div class="smtp-fields">
        <div class="field">
          <label for="smtp-host">SMTP 主机</label>
          <p class="field-help">邮箱服务商的发信服务器，如 QQ <code>smtp.qq.com</code>、163 <code>smtp.163.com</code>、Gmail <code>smtp.gmail.com</code></p>
          <input id="smtp-host" type="text" v-model="smtpForm.host" placeholder="smtp.qq.com" autocomplete="off" />
        </div>
        <div class="field">
          <label for="smtp-port">端口</label>
          <p class="field-help">网易/QQ 等若 587 超时，改用 <code>465</code>（SSL，无需 STARTTLS）；<code>587</code> 则勾选 STARTTLS</p>
          <input id="smtp-port" type="number" min="1" max="65535" v-model.number="smtpForm.port" />
        </div>
        <div class="field">
          <label for="smtp-user">用户名（登录账号）</label>
          <p class="field-help">用来<strong>登录 SMTP</strong>的账号，多数邮箱填完整邮箱地址（如 <code>name@qq.com</code>），不是昵称</p>
          <input id="smtp-user" type="text" v-model="smtpForm.user" placeholder="name@qq.com" autocomplete="username" />
        </div>
        <div class="field">
          <label for="smtp-password">密码 / 授权码</label>
          <p class="field-help">多数服务商要填网页邮箱里生成的<strong>授权码</strong>，不是登录密码；已保存后留空表示不改</p>
          <input
            id="smtp-password"
            type="password"
            v-model="smtpForm.password"
            :placeholder="smtpForm.password_set ? '已设置，留空不改' : '粘贴授权码'"
            autocomplete="new-password"
          />
        </div>
        <div class="field smtp-from">
          <label for="smtp-from">发件人（收件人看到的 From）</label>
          <p class="field-help">出现在邮件「发件人」里的地址；个人邮箱一般与用户名填<strong>同一个邮箱</strong>即可</p>
          <input id="smtp-from" type="text" v-model="smtpForm.from_addr" placeholder="name@qq.com（可与用户名相同）" />
        </div>
      </div>
      <div class="smtp-toggles">
        <label class="check"><input type="checkbox" v-model="smtpForm.use_tls" /> 启用 STARTTLS（仅端口 587；465 会自动走 SSL）</label>
        <label class="check"><input type="checkbox" v-model="smtpForm.enabled" /> 启用邮件通道</label>
      </div>
      <div class="smtp-actions-block">
        <div class="row smtp-actions">
          <button type="button" :disabled="smtpBusy" @click="saveSmtp">{{ smtpBusy ? '保存中…' : '保存配置' }}</button>
        </div>
        <div class="smtp-test-row">
          <div class="field smtp-test-input">
            <label for="smtp-test-to">测试收件邮箱</label>
            <p class="field-help">配置齐备后发一封测试信，确认通道可通</p>
            <input id="smtp-test-to" type="email" v-model="smtpTestTo" placeholder="you@example.com" />
          </div>
          <button
            type="button"
            class="secondary"
            :disabled="smtpBusy || !canTestSmtp || !smtpTestTo.trim()"
            @click="testSmtp"
          >{{ smtpBusy ? '处理中…' : '发送测试邮件' }}</button>
        </div>
        <p v-if="!canTestSmtp" class="meta smtp-test-hint">请先填完主机、登录账号、密码（或已保存密码）并启用通道，再测试。</p>
      </div>
      <p v-if="smtpMsg" class="meta" :class="{ 'form-error': smtpErr }">{{ smtpMsg }}</p>
    </section>

    <!-- 爬虫注册表 -->
    <section v-show="activeTab === 'crawlers'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>爬虫注册表</h3><span class="rule"></span></div>
      <div class="crawler-status" :class="{ warn: crawlerOffCount > 0 }">
        <strong>已启用 {{ crawlerOnCount }} / 共 {{ crawlerRows.length }}</strong>
        <span v-if="crawlerOffCount" class="meta">停用 {{ crawlerOffCount }} 个</span>
        <span v-if="crawlerDirtyCount" class="dirty-tag">{{ crawlerDirtyCount }} 行待保存</span>
      </div>
      <p class="meta hint">
        新闻爬虫与管线爬虫分开管理。停用后不会出现在
        <router-link to="/monitor">爬虫监控</router-link>
        对应分区；参数在<strong>保存后下一轮</strong>生效。
      </p>
      <div v-if="crawlerLoading" class="meta">加载中…</div>
      <template v-else>
        <h4 class="sub-h">新闻爬虫</h4>
        <div class="table-wrap" v-if="newsCrawlerRows.length">
          <table class="cfg-table crawler-table">
            <thead>
              <tr>
                <th>来源</th><th>启用</th><th>页数</th><th>并发</th><th>抓详情</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in newsCrawlerRows"
                :key="row.crawler_key"
                :class="{ 'is-off': !row.enabled, 'is-dirty': isCrawlerDirty(row) }"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <div class="meta mono">{{ row.crawler_key }}</div>
                </td>
                <td>
                  <label class="enable-cell">
                    <input type="checkbox" v-model="row.enabled" />
                    <span :class="row.enabled ? 'on' : 'off'">{{ row.enabled ? '启用中' : '已停用' }}</span>
                  </label>
                </td>
                <td><input type="number" min="1" max="50" v-model.number="row.page_count" class="num" /></td>
                <td><input type="number" min="1" max="20" v-model.number="row.concurrency" class="num" /></td>
                <td><input type="checkbox" v-model="row.fetch_details" /></td>
                <td class="crawler-save-cell">
                  <button
                    type="button"
                    class="secondary"
                    :disabled="crawlerBusy === row.crawler_key || !isCrawlerDirty(row)"
                    @click="saveCrawler(row)"
                  >{{ crawlerBusy === row.crawler_key ? '…' : (crawlerSavedKey === row.crawler_key ? '已保存' : '保存') }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">暂无新闻爬虫</p>

        <h4 class="sub-h">管线爬虫</h4>
        <div class="table-wrap" v-if="pipelineCrawlerRows.length">
          <table class="cfg-table crawler-table">
            <thead>
              <tr>
                <th>来源</th><th>启用</th><th>说明</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in pipelineCrawlerRows"
                :key="row.crawler_key"
                :class="{ 'is-off': !row.enabled, 'is-dirty': isCrawlerDirty(row) }"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <div class="meta mono">{{ row.crawler_key }}</div>
                </td>
                <td>
                  <label class="enable-cell">
                    <input type="checkbox" v-model="row.enabled" />
                    <span :class="row.enabled ? 'on' : 'off'">{{ row.enabled ? '启用中' : '已停用' }}</span>
                  </label>
                </td>
                <td class="meta">下载管线图片 → 视觉模型抽取（调度见监控页）</td>
                <td class="crawler-save-cell">
                  <button
                    type="button"
                    class="secondary"
                    :disabled="crawlerBusy === row.crawler_key || !isCrawlerDirty(row)"
                    @click="saveCrawler(row)"
                  >{{ crawlerBusy === row.crawler_key ? '…' : (crawlerSavedKey === row.crawler_key ? '已保存' : '保存') }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">暂无管线爬虫</p>
      </template>
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
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useAsync } from '../composables'
import ProfileForm from './ProfileForm.vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { id: 'models', label: '大模型' },
  { id: 'rag', label: 'RAG 检索' },
  { id: 'mail', label: '邮件服务' },
  { id: 'crawlers', label: '爬虫注册表' },
  { id: 'keywords', label: '过滤关键词' },
]
const tabIds = new Set(tabs.map((t) => t.id))
const activeTab = ref(tabIds.has(route.query.tab) ? String(route.query.tab) : 'models')

const { loading, error, run } = useAsync()
const profiles = ref([])
const vectorDim = ref(null)
const busy = ref(false)
const slotLabel = { chat: '对话', embedding: '嵌入', rerank: '重排', vision: '视觉' }
const draftNotices = reactive({ chat: null, embedding: null, rerank: null, vision: null })
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
      vision: { text: '未配置', warn: true },
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
    vision: {
      text: row.vision_model || '未配置（管线同步需要）',
      warn: !row.vision_model,
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
const smtpForm = reactive({
  host: '',
  port: 587,
  user: '',
  password: '',
  from_addr: '',
  use_tls: true,
  enabled: true,
  password_set: false,
  ready: false,
  message: '',
  source: 'db',
  env_host: '',
})
const smtpBusy = ref(false)
const smtpMsg = ref('')
const smtpErr = ref(false)
const smtpTestTo = ref('')
const ragMsg = ref('')
const ragErr = ref(false)

const crawlerRows = ref([])
const crawlerSnapshot = ref({})
const crawlerLoading = ref(false)
const crawlerBusy = ref('')
const crawlerSavedKey = ref('')
const crawlerMsg = ref('')
const crawlerErr = ref(false)
let crawlerSavedTimer = null

const crawlerOnCount = computed(() => crawlerRows.value.filter((r) => r.enabled).length)
const crawlerOffCount = computed(() => crawlerRows.value.length - crawlerOnCount.value)
const crawlerDirtyCount = computed(() => crawlerRows.value.filter((r) => isCrawlerDirty(r)).length)
const newsCrawlerRows = computed(() => crawlerRows.value.filter((r) => (r.kind || 'news') === 'news'))
const pipelineCrawlerRows = computed(() => crawlerRows.value.filter((r) => r.kind === 'pipeline'))

const canTestSmtp = computed(() => {
  if (!smtpForm.enabled) return false
  if (!smtpForm.host.trim()) return false
  if (!smtpForm.user.trim() && !smtpForm.from_addr.trim()) return false
  if (!smtpForm.password.trim() && !smtpForm.password_set) return false
  return true
})

function crawlerSnapKey(row) {
  return JSON.stringify({
    enabled: Boolean(row.enabled),
    page_count: Number(row.page_count),
    concurrency: Number(row.concurrency),
    fetch_details: Boolean(row.fetch_details),
  })
}

function rememberCrawlerSnapshot(rows) {
  const map = {}
  for (const row of rows) map[row.crawler_key] = crawlerSnapKey(row)
  crawlerSnapshot.value = map
}

function isCrawlerDirty(row) {
  const prev = crawlerSnapshot.value[row.crawler_key]
  if (!prev) return false
  return prev !== crawlerSnapKey(row)
}

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
const loaded = reactive({ models: false, rag: false, mail: false, crawlers: false, keywords: false })

function applySmtp(data) {
  smtpForm.host = data.host || ''
  smtpForm.port = data.port ?? 587
  smtpForm.user = data.user || ''
  smtpForm.from_addr = data.from_addr || ''
  smtpForm.use_tls = data.use_tls !== false
  smtpForm.enabled = data.enabled !== false
  smtpForm.password_set = Boolean(data.password_set)
  smtpForm.ready = Boolean(data.ready)
  smtpForm.message = data.message || ''
  smtpForm.source = data.source || 'db'
  smtpForm.env_host = data.env_host || ''
  smtpForm.password = ''
}

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
    vision_api_key: '',
    vision_base_url: 'https://api.siliconflow.cn/v1',
    vision_model: '',
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
  draft.vision_base_url = defaults.vision_base_url || draft.vision_base_url
  draft.vision_model = defaults.vision_model || draft.vision_model
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
    vision_api_key: '',
    notices: { chat: null, embedding: null, rerank: null, vision: null },
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
  if (form.ok === true || form.ok === false) {
    draftNotices[form.slot] = { ok: form.ok, text: form.text || (form.ok ? '成功' : '失败') }
    return
  }
  await finishTest(draftNotices, form.slot, () => api.testLlmProfile({
    base_url: form.base_url,
    api_key: form.api_key,
    slot: form.slot,
  }))
}

async function testSaved(item, form) {
  if (form.ok === true || form.ok === false) {
    item.notices[form.slot] = { ok: form.ok, text: form.text || (form.ok ? '成功' : '失败') }
    return
  }
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

async function loadSmtp() {
  smtpMsg.value = ''
  smtpErr.value = false
  try {
    applySmtp(await api.smtpConfig())
    loaded.mail = true
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '加载失败'
  }
}

async function saveSmtp({ quiet = false } = {}) {
  smtpBusy.value = true
  if (!quiet) {
    smtpMsg.value = ''
    smtpErr.value = false
  }
  try {
    const body = {
      host: smtpForm.host.trim(),
      port: smtpForm.port,
      user: smtpForm.user.trim(),
      from_addr: smtpForm.from_addr.trim() || smtpForm.user.trim(),
      use_tls: smtpForm.use_tls,
      enabled: smtpForm.enabled,
    }
    if (smtpForm.password.trim()) body.password = smtpForm.password.trim()
    applySmtp(await api.updateSmtpConfig(body))
    if (!quiet) {
      smtpMsg.value = smtpForm.ready
        ? '已保存，通道就绪'
        : (smtpForm.message ? `已保存。${smtpForm.message}` : '已保存，通道仍未就绪')
    }
    return true
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '保存失败'
    return false
  } finally {
    smtpBusy.value = false
  }
}

async function testSmtp() {
  const to = smtpTestTo.value.trim()
  if (!to || !canTestSmtp.value) return
  smtpMsg.value = ''
  smtpErr.value = false
  // 先保存当前表单，避免测到旧库配置
  const saved = await saveSmtp({ quiet: true })
  if (!saved) return
  if (!smtpForm.ready) {
    smtpErr.value = true
    smtpMsg.value = smtpForm.message || '配置仍未就绪，无法发送测试邮件'
    return
  }
  smtpBusy.value = true
  try {
    await api.testSmtpConfig({ to_email: to })
    smtpMsg.value = `测试邮件已发出，请到 ${to} 查收收件箱（含垃圾箱）`
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '测试失败'
  } finally {
    smtpBusy.value = false
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
  crawlerErr.value = false
  crawlerLoading.value = true
  crawlerSavedKey.value = ''
  try {
    const data = await api.adminCrawlers()
    crawlerRows.value = Array.isArray(data) ? data : []
    rememberCrawlerSnapshot(crawlerRows.value)
    loaded.crawlers = true
  } catch (e) {
    crawlerErr.value = true
    crawlerMsg.value = e.message || '加载失败'
    crawlerRows.value = []
    crawlerSnapshot.value = {}
  } finally {
    crawlerLoading.value = false
  }
}

function ensureTabLoaded(tab) {
  if (tab === 'models' && !loaded.models) load()
  if (tab === 'rag' && !loaded.rag) loadRag()
  if (tab === 'mail' && !loaded.mail) loadSmtp()
  if (tab === 'crawlers' && !loaded.crawlers) loadCrawlers()
  if (tab === 'keywords' && !loaded.keywords) loadKeywords(1)
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
    crawlerSnapshot.value = {
      ...crawlerSnapshot.value,
      [row.crawler_key]: crawlerSnapKey(row),
    }
    crawlerMsg.value = `已保存「${row.name}」；下一轮采集生效`
    crawlerSavedKey.value = row.crawler_key
    if (crawlerSavedTimer) clearTimeout(crawlerSavedTimer)
    crawlerSavedTimer = setTimeout(() => {
      if (crawlerSavedKey.value === row.crawler_key) crawlerSavedKey.value = ''
    }, 1800)
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
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab } })
  }
  ensureTabLoaded(tab)
})

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && tabIds.has(tab) && activeTab.value !== tab) {
      activeTab.value = tab
    }
  },
)

onMounted(() => {
  ensureTabLoaded(activeTab.value)
})
</script>

<style scoped>
.sub-h {
  margin: 18px 0 10px;
  font-size: var(--fs-sm);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
}
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
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.field label {
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}
.field input[type="text"],
.field input[type="email"],
.field input[type="password"],
.field input[type="number"] {
  width: 100%;
  box-sizing: border-box;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-sm);
  color: var(--ink-soft);
  cursor: pointer;
}
.mail-status {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 12px;
  font-size: var(--fs-sm);
  padding: 10px 12px;
  border-radius: var(--r-sm);
  margin: 12px 0 4px;
}
.mail-status strong { font-weight: 700; }
.mail-status.ok {
  color: var(--moss);
  background: color-mix(in srgb, var(--lime) 22%, transparent);
}
.mail-status.bad {
  color: var(--clay);
  background: color-mix(in srgb, var(--clay) 10%, var(--paper));
}
.smtp-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  margin: 16px 0 12px;
  align-items: stretch;
}
.smtp-fields > .field {
  /* 同行两列等高，说明区撑开，输入框底对齐 */
  height: 100%;
}
.smtp-fields > .field .field-help {
  flex: 1 1 auto;
  min-height: 2.9em;
}
.smtp-fields .smtp-from { grid-column: 1 / -1; }
.smtp-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin: 0 0 14px;
}
.field-help {
  margin: 0;
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  line-height: 1.45;
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
  /* 预留约两行，避免与邻列说明长短差导致输入框错位 */
  min-height: 2.9em;
}
.field-help code {
  font-family: var(--font-mono);
  font-size: 0.95em;
  background: var(--wash);
  padding: 0 4px;
  border-radius: 3px;
}
.smtp-actions-block {
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px dashed var(--rule, #d8d2c8);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.smtp-actions { margin: 0; }
.smtp-test-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.smtp-test-input { flex: 1 1 240px; min-width: 0; }
.smtp-test-row button { flex: none; }
.smtp-test-hint { margin: 0; color: var(--ink-mute); }
.compact-empty { margin-top: 12px; padding: 20px; }
@media (max-width: 700px) {
  .smtp-fields { grid-template-columns: 1fr; }
  .smtp-fields .smtp-from { grid-column: auto; }
}
.hint { margin: 0 0 12px; }
.crawler-status {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  margin: 12px 0 8px;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--lime) 18%, transparent);
  color: var(--pine);
  font-size: var(--fs-sm);
}
.crawler-status.warn {
  background: color-mix(in srgb, var(--brass, #9a6b2f) 12%, var(--paper));
  color: var(--ink);
}
.crawler-status .dirty-tag {
  font-size: var(--fs-xs);
  font-weight: 700;
  color: var(--clay);
}
.cfg-table { width: 100%; border-collapse: collapse; }
.cfg-table th, .cfg-table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line, #e6e0d6); vertical-align: middle; }
.cfg-table .num { width: 72px; }
.cfg-table .wide { width: 100%; min-width: 140px; }
.col-hint {
  font-size: 10px;
  font-weight: 500;
  color: var(--ink-mute);
  letter-spacing: 0;
  text-transform: none;
  margin-top: 2px;
}
.crawler-table tbody tr.is-off {
  opacity: 0.62;
  box-shadow: inset 3px 0 0 var(--ink-mute);
}
.crawler-table tbody tr.is-dirty {
  background: color-mix(in srgb, var(--brass, #9a6b2f) 8%, transparent);
}
.enable-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: var(--fs-xs);
}
.enable-cell .on { color: var(--moss); font-weight: 650; }
.enable-cell .off { color: var(--ink-mute); }
.crawler-save-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.dirty-dot {
  font-size: 10px;
  font-weight: 700;
  color: var(--clay);
}
.actions { white-space: nowrap; display: flex; gap: 8px; }
.kw-toolbar, .kw-new, .kw-pager { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
.kw-toolbar .search { flex: 1; min-width: 160px; }
.kw-new input { flex: 1; min-width: 140px; }
</style>
