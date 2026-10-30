<template>
  <div class="sys-page reveal">
    <header class="sys-hero">
      <h2 class="sys-title">系统设置</h2>
      <p class="sys-desc">配置模型服务、RAG 检索与邮件通道，确保问答与告警稳定运行。</p>
    </header>

    <!-- 模型配置：对话 / 嵌入 / 重排 / 视觉各自独立 -->
    <section class="cfg-card model-split">
      <header class="cfg-card-head studio-head">
        <div class="studio-head-copy">
          <div class="cfg-card-title">
            <span class="cfg-ico" aria-hidden="true">◎</span>
            <h3>模型配置</h3>
            <span class="cfg-status" :class="modelReady ? 'ok' : 'bad'">
              {{ modelReady ? '已配置' : '未就绪' }}
            </span>
          </div>
          <p class="studio-lead">对话、嵌入、重排、视觉分开填写。地址和密钥可以各不相同，保存后写入当前正在使用的服务。</p>
        </div>
        <div class="head-actions">
          <button type="button" class="cfg-test" :disabled="busy" @click="saveModel">
            {{ busy && !testBusy ? '…' : '保存' }}
          </button>
        </div>
      </header>

      <div class="split-grid">
        <article class="slot-card">
          <div class="slot-head">
            <div>
              <h4>对话</h4>
              <p>问答生成</p>
            </div>
            <button type="button" class="secondary cfg-test" :disabled="busy" @click="testSlot('chat')">
              {{ testBusy === 'chat' ? '…' : '测试' }}
            </button>
          </div>
          <div class="field">
            <label>模型</label>
            <input v-model="editBuf.chat_model" class="mono" type="text" placeholder="模型 ID" :disabled="busy" />
          </div>
          <div class="field">
            <label>API 地址</label>
            <input v-model="editBuf.base_url" class="mono" type="text" placeholder="https://…" :disabled="busy" />
          </div>
          <div class="field">
            <label>API Key <span class="field-note">{{ keepFlags.chat ? '已保存，留空不改' : '尚未保存' }}</span></label>
            <div class="key-row">
              <input v-model="editBuf.api_key" class="mono" :type="showKey.chat ? 'text' : 'password'" autocomplete="off" :placeholder="keyPlaceholder" :disabled="busy" />
              <button type="button" class="key-toggle" :disabled="busy" @click="showKey.chat = !showKey.chat">{{ showKey.chat ? '隐藏' : '显示' }}</button>
            </div>
          </div>
        </article>

        <article class="slot-card">
          <div class="slot-head">
            <div>
              <h4>嵌入</h4>
              <p>把资料写成向量</p>
            </div>
            <button type="button" class="secondary cfg-test" :disabled="busy" @click="testSlot('embedding')">
              {{ testBusy === 'embedding' ? '…' : '测试' }}
            </button>
          </div>
          <div class="slot-pair">
            <div class="field">
              <label>模型</label>
              <input v-model="editBuf.embedding_model" class="mono" type="text" :disabled="busy" />
            </div>
            <div class="field">
              <label>维度</label>
              <input v-model.number="editBuf.embedding_dim" type="number" min="1" max="4096" :disabled="busy" />
            </div>
          </div>
          <div class="field">
            <label>API 地址</label>
            <input v-model="editBuf.embedding_base_url" class="mono" type="text" placeholder="https://…" :disabled="busy" />
          </div>
          <div class="field">
            <label>API Key <span class="field-note">{{ keepFlags.embedding ? '已保存，留空不改' : '尚未保存' }}</span></label>
            <div class="key-row">
              <input v-model="editBuf.embedding_api_key" class="mono" :type="showKey.embedding ? 'text' : 'password'" autocomplete="off" :placeholder="embedKeyPlaceholder" :disabled="busy" />
              <button type="button" class="key-toggle" :disabled="busy" @click="showKey.embedding = !showKey.embedding">{{ showKey.embedding ? '隐藏' : '显示' }}</button>
            </div>
          </div>
          <button type="button" class="linkish" :disabled="busy" @click="copyChatInto('embedding')">填入对话的地址与密钥</button>
        </article>

        <article class="slot-card">
          <div class="slot-head">
            <div>
              <h4>重排</h4>
              <p>检索结果二次排序</p>
            </div>
            <button type="button" class="secondary cfg-test" :disabled="busy" @click="testSlot('rerank')">
              {{ testBusy === 'rerank' ? '…' : '测试' }}
            </button>
          </div>
          <div class="field">
            <label>模型</label>
            <input v-model="editBuf.reranker_model" class="mono" type="text" :disabled="busy" @change="rerankModel = editBuf.reranker_model" />
          </div>
          <div class="field">
            <label>API 地址</label>
            <input v-model="editBuf.reranker_base_url" class="mono" type="text" placeholder="https://…" :disabled="busy" />
          </div>
          <div class="field">
            <label>API Key <span class="field-note">{{ keepFlags.rerank ? '已保存，留空不改' : '尚未保存' }}</span></label>
            <div class="key-row">
              <input v-model="editBuf.reranker_api_key" class="mono" :type="showKey.rerank ? 'text' : 'password'" autocomplete="off" :placeholder="rerankKeyPlaceholder" :disabled="busy" />
              <button type="button" class="key-toggle" :disabled="busy" @click="showKey.rerank = !showKey.rerank">{{ showKey.rerank ? '隐藏' : '显示' }}</button>
            </div>
          </div>
          <button type="button" class="linkish" :disabled="busy" @click="copyChatInto('rerank')">填入对话的地址与密钥</button>
        </article>

        <article class="slot-card">
          <div class="slot-head">
            <div>
              <h4>视觉</h4>
              <p>管线抽图才需要，可留空</p>
            </div>
            <button type="button" class="secondary cfg-test" :disabled="busy" @click="testSlot('vision')">
              {{ testBusy === 'vision' ? '…' : '测试' }}
            </button>
          </div>
          <div class="field">
            <label>模型</label>
            <input v-model="editBuf.vision_model" class="mono" type="text" placeholder="可选" :disabled="busy" />
          </div>
          <div class="field">
            <label>API 地址</label>
            <input v-model="editBuf.vision_base_url" class="mono" type="text" placeholder="https://…" :disabled="busy" />
          </div>
          <div class="field">
            <label>API Key <span class="field-note">{{ keepFlags.vision ? '已保存，留空不改' : '可选' }}</span></label>
            <div class="key-row">
              <input v-model="editBuf.vision_api_key" class="mono" :type="showKey.vision ? 'text' : 'password'" autocomplete="off" :placeholder="visionKeyPlaceholder" :disabled="busy" />
              <button type="button" class="key-toggle" :disabled="busy" @click="showKey.vision = !showKey.vision">{{ showKey.vision ? '隐藏' : '显示' }}</button>
            </div>
          </div>
          <button type="button" class="linkish" :disabled="busy" @click="copyChatInto('vision')">填入对话的地址与密钥</button>
        </article>
      </div>

      <div v-if="selectedDimMismatch || modelError || modelTestMsg" class="studio-foot">
        <p v-if="selectedDimMismatch" class="status-warn">
          嵌入维度与库不一致（库 {{ vectorDim }} / 当前 {{ editBuf.embedding_dim }}），保存时将确认重建。
        </p>
        <p v-if="modelError" class="form-error">{{ modelError }}</p>
        <p v-if="modelTestMsg" class="meta" :class="{ 'form-error': modelTestErr }">{{ modelTestMsg }}</p>
      </div>
    </section>

    <!-- 下方三列：RAG | 邮件 | 说明 -->
    <div class="tri-row">
      <!-- 左：RAG -->
      <section class="cfg-card tri-card">
        <div class="cfg-card-head">
          <div class="cfg-card-title">
            <span class="cfg-ico" aria-hidden="true">⌕</span>
            <h3>RAG 检索</h3>
            <span class="cfg-status ok">已配置</span>
          </div>
          <div class="head-actions">
            <button type="button" class="cfg-test" :disabled="ragBusy" @click="saveRag">
              {{ ragBusy && testBusy !== 'rag' ? '…' : '保存' }}
            </button>
            <button type="button" class="secondary cfg-test" :disabled="ragBusy || testBusy === 'rag'" @click="testRag">
              {{ testBusy === 'rag' ? '…' : '测试检索' }}
            </button>
          </div>
        </div>
        <div class="cfg-card-pad stack-fields">
          <div class="field">
            <label>向量数据库</label>
            <UiSelect
              model-value="pg"
              :options="vectorDbOptions"
              :allow-empty="false"
              :disabled="true"
              size="md"
              placeholder="PostgreSQL"
            />
          </div>
          <div class="field">
            <label>索引名称</label>
            <input type="text" :value="INDEX_NAME" disabled />
          </div>
          <div class="field">
            <label for="rag-top-k">Top-K（1–50）</label>
            <input id="rag-top-k" type="number" min="1" max="50" v-model.number="ragForm.top_k" :disabled="ragBusy" />
          </div>
          <div class="field">
            <label>重排模型</label>
            <UiSelect
              :model-value="rerankModel"
              :options="rerankOptions"
              :allow-empty="false"
              size="md"
              placeholder="选择重排模型"
              @update:model-value="onRerankChange"
            />
            <button type="button" class="linkish" :disabled="busy || fetchingRerank" @click="fetchRerankModels">
              {{ fetchingRerank ? '拉取中…' : '拉取模型列表' }}
            </button>
          </div>

          <details class="adv">
            <summary>高级参数</summary>
            <div class="stack-fields adv-body">
              <div class="field">
                <label for="rag-min-score">相似度阈值（0–1）</label>
                <input id="rag-min-score" type="number" min="0" max="1" step="0.01" v-model.number="ragForm.min_relevance_score" :disabled="ragBusy" />
              </div>
              <div class="field">
                <label for="rag-vec-w">向量权重（BM25 ≈ {{ ragBm25Weight }}）</label>
                <input id="rag-vec-w" type="number" min="0" max="1" step="0.05" v-model.number="ragForm.hybrid_vector_weight" :disabled="ragBusy" />
              </div>
              <div class="field">
                <label for="rag-mult">重排候选倍数（1–5）</label>
                <input id="rag-mult" type="number" min="1" max="5" v-model.number="ragForm.rerank_pool_multiplier" :disabled="ragBusy" />
              </div>
              <div class="field">
                <label for="rag-hist">对话历史轮数（1–40）</label>
                <input id="rag-hist" type="number" min="1" max="40" v-model.number="ragForm.history_turns" :disabled="ragBusy" />
              </div>
              <div class="field">
                <label for="rag-temp">生成温度（0–2）</label>
                <input id="rag-temp" type="number" min="0" max="2" step="0.05" v-model.number="ragForm.temperature" :disabled="ragBusy" />
              </div>
              <div class="field">
                <label for="rag-test-q">测试查询</label>
                <input id="rag-test-q" type="text" v-model="ragTestQuery" placeholder="医药新闻" :disabled="testBusy === 'rag'" />
              </div>
            </div>
          </details>
          <p v-if="ragMsg" class="meta" :class="{ 'form-error': ragErr }">{{ ragMsg }}</p>
        </div>
      </section>

      <!-- 中：邮件 -->
      <section class="cfg-card tri-card">
        <div class="cfg-card-head">
          <div class="cfg-card-title">
            <span class="cfg-ico" aria-hidden="true">✉</span>
            <h3>邮件服务</h3>
            <span class="cfg-status" :class="smtpForm.ready ? 'ok' : 'bad'">
              {{ smtpForm.ready ? '已配置' : '未就绪' }}
            </span>
          </div>
          <div class="head-actions">
            <button type="button" class="cfg-test" :disabled="smtpBusy" @click="saveMail">
              {{ smtpBusy && testBusy !== 'mail' ? '…' : '保存' }}
            </button>
            <button
              type="button"
              class="secondary cfg-test"
              :disabled="smtpBusy || !canTestSmtp || !smtpTestTo.trim()"
              @click="testSmtp"
            >{{ smtpBusy && testBusy === 'mail' ? '…' : '测试发送' }}</button>
          </div>
        </div>
        <div class="cfg-card-pad stack-fields">
          <div class="field">
            <label for="smtp-host">SMTP 服务器</label>
            <input id="smtp-host" type="text" v-model="smtpForm.host" placeholder="smtp.qq.com" autocomplete="off" />
          </div>
          <div class="field">
            <label>端口</label>
            <UiSelect
              :model-value="String(smtpForm.port)"
              :options="portOptions"
              :allow-empty="false"
              size="md"
              placeholder="端口"
              @update:model-value="onPortChange"
            />
          </div>
          <div class="field">
            <label for="smtp-from">发件人邮箱</label>
            <input id="smtp-from" type="text" v-model="smtpForm.from_addr" placeholder="name@qq.com" />
          </div>
          <div class="field">
            <label for="smtp-user">用户名</label>
            <input id="smtp-user" type="text" v-model="smtpForm.user" placeholder="name@qq.com" autocomplete="username" />
          </div>
          <div class="field">
            <label for="smtp-password">密码 / 授权码</label>
            <input
              id="smtp-password"
              type="password"
              v-model="smtpForm.password"
              :placeholder="smtpForm.password_set ? '已设置，留空不改' : '粘贴授权码'"
              autocomplete="new-password"
            />
          </div>
          <div class="field">
            <label for="smtp-test-to">测试收件邮箱</label>
            <input id="smtp-test-to" type="email" v-model="smtpTestTo" placeholder="you@example.com" />
          </div>
          <div class="smtp-toggles">
            <label class="check"><input type="checkbox" v-model="smtpForm.use_tls" /> STARTTLS（587 建议勾选）</label>
            <label class="check"><input type="checkbox" v-model="smtpForm.enabled" /> 启用邮件通道</label>
          </div>
          <p v-if="smtpForm.source === 'env' && smtpForm.env_host" class="meta">
            当前生效来自 .env，保存后将写入数据库。
          </p>
          <p v-if="smtpMsg" class="meta" :class="{ 'form-error': smtpErr }">{{ smtpMsg }}</p>
        </div>
      </section>

      <!-- 右：使用说明 -->
      <aside class="cfg-card tri-card help-card">
        <div class="cfg-card-head">
          <div class="cfg-card-title">
            <span class="cfg-ico" aria-hidden="true">?</span>
            <h3>使用说明</h3>
          </div>
        </div>
        <div class="cfg-card-pad help-body">
          <h4>模型配置</h4>
          <p>对话、嵌入、重排、视觉分开配置，地址和密钥不必相同。嵌入维度须与向量库一致；管线图片抽取需填写视觉模型。</p>
          <h4>RAG 检索</h4>
          <p>向量库与索引由系统固定使用 PostgreSQL。Top-K 控制进入回答的资料条数。重排模型在上方「重排」中修改，这里的下拉与它是同一项。</p>
          <h4>邮件服务</h4>
          <p>多数邮箱需使用授权码而非登录密码。465 走 SSL；587 请勾选 STARTTLS。建议先保存再测试发送。</p>
          <div class="help-links">
            <a href="https://docs.siliconflow.cn/" target="_blank" rel="noopener">硅基流动文档</a>
            <a href="https://cloud.tencent.com/document/product/1288/51045" target="_blank" rel="noopener">腾讯企业邮 SMTP</a>
          </div>
        </div>
      </aside>
    </div>

    <Teleport to="body">
      <div
        v-if="testDialog.open"
        class="test-mask"
        @click.self="closeTestDialog"
        @keydown.esc="closeTestDialog"
      >
        <div
          class="test-dialog"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="'test-dialog-title'"
        >
          <h3 id="test-dialog-title" :class="{ bad: testDialog.error }">{{ testDialog.title }}</h3>
          <p>{{ testDialog.message }}</p>
          <div class="test-dialog-actions">
            <button type="button" @click="closeTestDialog">知道了</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api } from '../../api'
import { useAsync } from '../../composables'
import UiSelect from '../UiSelect.vue'

const INDEX_NAME = 'news（embedding）'
const vectorDbOptions = [{ value: 'pg', label: 'PostgreSQL + pgvector' }]
const portOptions = ref([
  { value: '465', label: '465（SSL）' },
  { value: '587', label: '587（STARTTLS）' },
  { value: '25', label: '25' },
])

const { run } = useAsync()
const profiles = ref([])
const vectorDim = ref(null)
const busy = ref(false)
const testBusy = ref('')
const revision = ref(0)
const editingId = ref(null)
const selectedId = ref(null)
const editBuf = reactive(blank())
const showKey = reactive({ chat: false, embedding: false, rerank: false, vision: false })
const keepFlags = reactive({
  chat: false,
  embedding: false,
  rerank: false,
  vision: false,
})
const modelError = ref('')
const modelTestMsg = ref('')
const modelTestErr = ref(false)
const SLOT_LABEL = { chat: '对话', embedding: '嵌入', rerank: '重排', vision: '视觉' }
const testDialog = reactive({
  open: false,
  error: false,
  title: '',
  message: '',
})

function openTestDialog({ error = false, title, message }) {
  testDialog.open = true
  testDialog.error = Boolean(error)
  testDialog.title = title
  testDialog.message = message
}

function closeTestDialog() {
  testDialog.open = false
}

const ragForm = reactive({
  top_k: 10,
  min_relevance_score: 0.25,
  hybrid_vector_weight: 0.6,
  rerank_pool_multiplier: 2,
  history_turns: 12,
  temperature: 0.3,
})
const ragBusy = ref(false)
const ragMsg = ref('')
const ragErr = ref(false)
const ragTestQuery = ref('医药新闻')
const rerankModel = ref('')
const rerankList = ref([])
const fetchingRerank = ref(false)

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

const activeProfile = computed(() => profiles.value.find((item) => item.is_active) || null)
const selectedProfile = computed(() =>
  profiles.value.find((item) => item.id === selectedId.value) || null,
)
const modelReady = computed(() => {
  const row = activeProfile.value
  if (!row) return false
  return Boolean(row.has_chat_key && row.has_embedding_key && row.has_reranker_key)
})
const selectedDimMismatch = computed(() => {
  if (vectorDim.value == null || editBuf.embedding_dim == null) return false
  if (editingId.value === 'new') return false
  return Number(editBuf.embedding_dim) !== Number(vectorDim.value)
})
const keyPlaceholder = computed(() => (keepFlags.chat ? '已保存，留空不改' : 'sk-...'))
const embedKeyPlaceholder = computed(() => (keepFlags.embedding ? '已保存，留空不改' : 'sk-...'))
const rerankKeyPlaceholder = computed(() => (keepFlags.rerank ? '已保存，留空不改' : 'sk-...'))
const visionKeyPlaceholder = computed(() => (keepFlags.vision ? '已保存，留空不改' : '可选'))
const ragBm25Weight = computed(() => {
  const w = Number(ragForm.hybrid_vector_weight)
  if (!Number.isFinite(w)) return '—'
  return Math.max(0, Math.min(1, 1 - w)).toFixed(2)
})
const canTestSmtp = computed(() => {
  if (!smtpForm.enabled) return false
  if (!smtpForm.host.trim()) return false
  if (!smtpForm.user.trim() && !smtpForm.from_addr.trim()) return false
  if (!smtpForm.password.trim() && !smtpForm.password_set) return false
  return true
})
const rerankOptions = computed(() => {
  const cur = rerankModel.value
  const ids = [...rerankList.value]
  if (cur && !ids.includes(cur)) ids.unshift(cur)
  if (!ids.length && cur) return [{ value: cur, label: cur }]
  return ids.map((id) => ({ value: id, label: id }))
})
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

const defaultsSnap = ref(null)

function applyDefaults(defaults) {
  if (!defaults) return
  defaultsSnap.value = defaults
}

function fillEditBufFrom(source, { isNew = false } = {}) {
  editBuf.name = source.name || ''
  editBuf.api_key = ''
  editBuf.base_url = source.base_url || ''
  editBuf.chat_model = source.chat_model || ''
  editBuf.embedding_api_key = ''
  editBuf.embedding_base_url = source.embedding_base_url || ''
  editBuf.embedding_model = source.embedding_model || ''
  editBuf.embedding_dim = Number(source.embedding_dim) || 1024
  editBuf.reranker_api_key = ''
  editBuf.reranker_base_url = source.reranker_base_url || ''
  editBuf.reranker_model = source.reranker_model || ''
  editBuf.vision_api_key = ''
  editBuf.vision_base_url = source.vision_base_url || ''
  editBuf.vision_model = source.vision_model || ''
  keepFlags.chat = !isNew && Boolean(source.has_chat_key)
  keepFlags.embedding = !isNew && Boolean(source.has_embedding_key)
  keepFlags.rerank = !isNew && Boolean(source.has_reranker_key)
  keepFlags.vision = !isNew && Boolean(source.has_vision_key)
  rerankModel.value = editBuf.reranker_model || ''
}

function onRerankChange(v) {
  rerankModel.value = String(v || '')
  editBuf.reranker_model = rerankModel.value
}

function buildPayload() {
  return {
    name: editBuf.name.trim() || '当前配置',
    api_key: editBuf.api_key,
    base_url: editBuf.base_url.trim(),
    chat_model: editBuf.chat_model.trim(),
    embedding_base_url: editBuf.embedding_base_url.trim(),
    embedding_model: editBuf.embedding_model.trim(),
    embedding_dim: Number(editBuf.embedding_dim),
    reranker_base_url: editBuf.reranker_base_url.trim(),
    reranker_model: (rerankModel.value || editBuf.reranker_model || '').trim(),
    vision_base_url: editBuf.vision_base_url.trim(),
    vision_model: editBuf.vision_model.trim(),
    embedding_api_key: editBuf.embedding_api_key,
    reranker_api_key: editBuf.reranker_api_key,
    vision_api_key: editBuf.vision_api_key,
  }
}

function onPortChange(v) {
  const n = Number(v)
  smtpForm.port = Number.isFinite(n) ? n : 587
  if (smtpForm.port === 587) smtpForm.use_tls = true
  if (smtpForm.port === 465) smtpForm.use_tls = false
}

function isDimMismatch(err) {
  return err?.status === 409 && err.detail?.code === 'dimension_mismatch'
}

function syncSelection() {
  if (editingId.value === 'new') return
  const active = profiles.value.find((p) => p.is_active)
  selectedId.value = active?.id ?? profiles.value[0]?.id ?? null
}

const SLOT_FIELD = {
  chat: { url: 'base_url', key: 'api_key' },
  embedding: { url: 'embedding_base_url', key: 'embedding_api_key' },
  rerank: { url: 'reranker_base_url', key: 'reranker_api_key' },
  vision: { url: 'vision_base_url', key: 'vision_api_key' },
}

function copyChatInto(slot) {
  const spec = SLOT_FIELD[slot]
  if (!spec) return
  editBuf[spec.url] = editBuf.base_url
  if (editBuf.api_key) editBuf[spec.key] = editBuf.api_key
}

function startCreate() {
  modelError.value = ''
  editingId.value = 'new'
  selectedId.value = null
  const seed = { ...blank(), ...(defaultsSnap.value || {}) }
  fillEditBufFrom(seed, { isNew: true })
}

async function loadProfiles() {
  const data = await run(() => api.llmProfiles())
  if (!data) return
  profiles.value = (data.profiles || []).map((item) => ({
    ...item,
    api_key: '',
    embedding_api_key: '',
    reranker_api_key: '',
    vision_api_key: '',
    error: '',
  }))
  vectorDim.value = data.vector_dim
  applyDefaults(data.defaults)
  revision.value += 1
  syncSelection()
  if (!profiles.value.length) {
    startCreate()
  } else if (editingId.value !== 'new') {
    const row = profiles.value.find((p) => p.id === selectedId.value) || profiles.value[0]
    if (row) {
      selectedId.value = row.id
      fillEditBufFrom(row)
    }
  }
}

function applyRagForm(data) {
  if (!data) return
  ragForm.top_k = data.top_k ?? 10
  ragForm.min_relevance_score = data.min_relevance_score ?? 0.25
  ragForm.hybrid_vector_weight = data.hybrid_vector_weight ?? 0.6
  ragForm.rerank_pool_multiplier = data.rerank_pool_multiplier ?? 2
  ragForm.history_turns = data.history_turns ?? 12
  ragForm.temperature = data.temperature ?? 0.3
}

async function loadRag() {
  ragMsg.value = ''
  ragErr.value = false
  try {
    applyRagForm(await api.ragConfig())
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '加载失败'
  }
}

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
  const p = String(smtpForm.port)
  if (!portOptions.value.some((o) => o.value === p)) {
    portOptions.value = [...portOptions.value, { value: p, label: `${p}（当前）` }]
  }
}

async function loadSmtp() {
  smtpMsg.value = ''
  smtpErr.value = false
  try {
    applySmtp(await api.smtpConfig())
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '加载失败'
  }
}

async function activate(item, rebuild = false) {
  item.error = ''
  modelError.value = ''
  busy.value = true
  try {
    await api.activateLlmProfile(item.id, rebuild)
    await loadProfiles()
  } catch (e) {
    if (!rebuild && isDimMismatch(e) && window.confirm(e.message)) {
      try {
        await api.activateLlmProfile(item.id, true)
        await loadProfiles()
      } catch (err) {
        modelError.value = err.message || '启用失败'
      }
      return
    }
    modelError.value = e.message || '启用失败'
  } finally {
    busy.value = false
  }
}

async function testSlot(slot) {
  const spec = SLOT_FIELD[slot]
  if (!spec) return
  const label = SLOT_LABEL[slot] || '接口'
  const baseUrl = String(editBuf[spec.url] || '').trim()
  if (!baseUrl) {
    openTestDialog({
      error: true,
      title: `${label}测试失败`,
      message: '请先填写 API 地址再测试。',
    })
    return
  }
  testBusy.value = slot
  busy.value = true
  try {
    await api.testLlmProfile({
      base_url: baseUrl,
      api_key: editBuf[spec.key],
      profile_id: editingId.value === 'new' ? undefined : selectedProfile.value?.id,
      slot,
    })
    openTestDialog({
      title: `${label}连接成功`,
      message: `已成功连上${label}接口，可以继续保存配置。`,
    })
  } catch (e) {
    openTestDialog({
      error: true,
      title: `${label}测试失败`,
      message: e.message || '连接失败，请检查地址与密钥。',
    })
  } finally {
    busy.value = false
    testBusy.value = ''
  }
}

async function fetchRerankModels() {
  fetchingRerank.value = true
  try {
    const payload = buildPayload()
    const data = await api.listLlmModels({
      base_url: payload.reranker_base_url || payload.base_url,
      api_key: payload.reranker_api_key || payload.api_key,
      slot: 'rerank',
      profile_id: editingId.value === 'new' ? undefined : selectedProfile.value?.id,
    })
    const models = data?.models || []
    const preferred = models.filter((m) => m.kind === 'rerank').map((m) => m.id)
    const all = models.map((m) => m.id).filter(Boolean)
    rerankList.value = preferred.length
      ? [...preferred, ...all.filter((id) => !preferred.includes(id))]
      : all
    if (!rerankModel.value && rerankList.value.length) {
      onRerankChange(rerankList.value[0])
    }
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '拉取重排模型失败'
  } finally {
    fetchingRerank.value = false
  }
}

async function testRag() {
  ragMsg.value = ''
  ragErr.value = false
  testBusy.value = 'rag'
  try {
    const data = await api.testRagConfig({
      query: (ragTestQuery.value || '医药新闻').trim(),
    })
    const titles = (data.items || []).map((it, i) => `${i + 1}. ${it.title}`).join('；')
    ragMsg.value = titles
      ? `命中 ${data.hit_count} 条（候选池 ${data.pool_count}）：${titles}`
      : `命中 ${data.hit_count || 0} 条`
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '测试失败'
  } finally {
    testBusy.value = ''
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
  testBusy.value = 'mail'
  const saved = await saveSmtp({ quiet: true })
  if (!saved) {
    testBusy.value = ''
    return
  }
  if (!smtpForm.ready) {
    smtpErr.value = true
    smtpMsg.value = smtpForm.message || '配置仍未就绪，无法发送测试邮件'
    testBusy.value = ''
    return
  }
  smtpBusy.value = true
  try {
    await api.testSmtpConfig({ to_email: to })
    smtpMsg.value = `测试邮件已发出，请到 ${to} 查收`
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '测试失败'
  } finally {
    smtpBusy.value = false
    testBusy.value = ''
  }
}

async function saveModel() {
  modelError.value = ''
  modelTestMsg.value = ''
  modelTestErr.value = false
  busy.value = true
  try {
    const payload = buildPayload()
    if (!payload.base_url || !payload.chat_model) throw new Error('请填写对话的模型与 API 地址')
    if (!payload.embedding_base_url || !payload.embedding_model) throw new Error('请填写嵌入的模型与 API 地址')
    if (!payload.reranker_base_url || !payload.reranker_model) throw new Error('请填写重排的模型与 API 地址')
    let targetId
    if (editingId.value === 'new' || !selectedProfile.value) {
      const created = await api.createLlmProfile(payload)
      targetId = created?.id
      editingId.value = null
    } else {
      targetId = selectedProfile.value.id
      try {
        await api.updateLlmProfile(targetId, payload)
      } catch (e) {
        if (isDimMismatch(e) && window.confirm(e.message)) {
          await api.updateLlmProfile(targetId, { ...payload, rebuild: true })
        } else {
          throw e
        }
      }
    }
    await loadProfiles()
    const row = profiles.value.find((p) => p.id === targetId)
    if (row && !row.is_active) await activate(row)
    if (!modelError.value) {
      openTestDialog({
        title: '模型配置已保存',
        message: '对话、嵌入、重排已写入；视觉可留空。当前组合已生效（若原先未启用会自动启用）。',
      })
    } else {
      openTestDialog({
        error: true,
        title: '保存后启用失败',
        message: modelError.value,
      })
    }
  } catch (e) {
    const msg = e.message || '保存失败'
    modelError.value = msg
    openTestDialog({
      error: true,
      title: '模型配置保存失败',
      message: msg,
    })
  } finally {
    busy.value = false
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
      hybrid_vector_weight: ragForm.hybrid_vector_weight,
      rerank_pool_multiplier: ragForm.rerank_pool_multiplier,
      history_turns: ragForm.history_turns,
      temperature: ragForm.temperature,
    })
    applyRagForm(data)
    // 重排模型与上方「重排」是同一项
    const item = selectedProfile.value
    const model = (rerankModel.value || '').trim()
    if (item && model && model !== item.reranker_model) {
      editBuf.reranker_model = model
      await api.updateLlmProfile(item.id, { ...buildPayload(), reranker_model: model })
      await loadProfiles()
    }
    ragMsg.value = 'RAG 配置已保存'
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '保存失败'
  } finally {
    ragBusy.value = false
  }
}

async function saveMail() {
  await saveSmtp({ quiet: false })
}

watch(
  () => editBuf.reranker_model,
  (v) => { rerankModel.value = v || '' },
)

function onEsc(e) {
  if (e.key === 'Escape' && testDialog.open) closeTestDialog()
}

onMounted(async () => {
  window.addEventListener('keydown', onEsc)
  await Promise.all([loadProfiles(), loadRag(), loadSmtp()])
})
onUnmounted(() => window.removeEventListener('keydown', onEsc))
</script>

<style scoped>
.sys-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}
.test-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(28, 36, 32, 0.42);
}
.test-dialog {
  width: min(360px, 100%);
  padding: 20px 22px;
  border: 1px solid var(--rule);
  border-radius: 10px;
  background: var(--paper);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.test-dialog h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  color: var(--pine);
}
.test-dialog h3.bad { color: var(--clay); }
.test-dialog p {
  margin: 0;
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--ink-soft);
}
.test-dialog-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}
.test-dialog-actions button {
  padding: 6px 14px;
  font-size: 13px;
}
.sys-hero { margin: 0 0 4px; }
.sys-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h1);
  color: var(--pine);
  font-weight: 700;
}
.sys-desc { margin: 6px 0 0; color: var(--ink-mute); font-size: var(--fs-sm); }

.cfg-card {
  background: color-mix(in srgb, var(--paper-deep) 55%, transparent);
  border: 1px solid var(--rule);
  border-radius: var(--r-lg, 12px);
  box-shadow: none;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.cfg-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-bottom: 1px solid var(--rule);
  background: transparent;
  flex: none;
}
.cfg-card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.cfg-card-title h3 {
  margin: 0;
  font-size: var(--fs-h2);
  font-weight: 700;
  color: var(--ink);
}
.cfg-ico {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--moss) 16%, transparent);
  color: var(--pine);
  font-size: 14px;
  flex: none;
}
.cfg-status {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 999px;
}
.cfg-status.ok {
  color: var(--pine);
  background: color-mix(in srgb, var(--moss) 18%, transparent);
}
.cfg-status.ok::before,
.cfg-status.bad::before {
  content: "●";
  margin-right: 4px;
  font-size: 8px;
  vertical-align: middle;
}
.cfg-status.bad {
  color: var(--clay);
  background: color-mix(in srgb, var(--clay) 12%, transparent);
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}
.cfg-test {
  flex: none;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  min-height: 0;
  height: auto;
}
.cfg-card-pad { padding: 14px 16px 16px; min-width: 0; }

.model-split { padding: 0; }
.studio-head { align-items: flex-start; }
.studio-head-copy { min-width: 0; flex: 1; }
.studio-lead {
  margin: 6px 0 0;
  color: var(--ink-mute);
  font-size: var(--fs-sm);
  line-height: 1.45;
}
.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 14px;
}
.slot-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--rule);
  border-radius: 10px;
  background: color-mix(in srgb, var(--paper) 72%, var(--wash));
}
.slot-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.slot-head h4 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 16px;
  color: var(--pine);
}
.slot-head p {
  margin: 2px 0 0;
  font-size: var(--fs-xs);
  color: var(--ink-mute);
}
.slot-pair {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(88px, 0.6fr);
  gap: 10px;
}
.field .mono {
  font-family: var(--font-mono);
  font-size: 12.5px;
}
.field-note {
  margin-left: 6px;
  font-weight: 600;
  color: var(--ink-mute);
}
.key-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.key-row input { flex: 1; min-width: 0; }
.model-split button.key-toggle {
  flex: none;
  margin: 0;
  padding: 7px 8px;
  letter-spacing: 0;
  font-size: 12px;
  font-weight: 650;
  color: var(--pine);
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 6px;
  box-shadow: none;
}
.model-split button.key-toggle:hover:not(:disabled) {
  background: var(--wash);
  border-color: var(--pine);
  transform: none;
  box-shadow: none;
}
.model-split button.linkish {
  margin: 0;
  letter-spacing: 0;
}
.model-split button.linkish:hover:not(:disabled) {
  background: transparent;
  color: var(--moss);
  transform: none;
  box-shadow: none;
}
.studio-foot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 18px 14px;
}
.studio-foot p { margin: 0; }

.tri-row {
  display: grid;
  grid-template-columns: 1fr 1fr minmax(200px, 0.85fr);
  gap: 14px;
  align-items: stretch;
}
.tri-card { height: 100%; }
.stack-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.field label {
  font-size: var(--fs-xs);
  font-weight: 700;
  color: var(--ink-soft);
}
.field input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: color-mix(in srgb, var(--paper) 70%, #fff);
  font-size: var(--fs-sm);
}
.field input:disabled {
  background: color-mix(in srgb, var(--paper-deep) 72%, var(--wash));
  color: var(--ink-mute);
  border-color: color-mix(in srgb, var(--rule) 80%, transparent);
}
.field :deep(.ui-select-trigger) {
  background: color-mix(in srgb, var(--paper) 70%, #fff);
}
.field :deep(.ui-select.disabled .ui-select-trigger) {
  background: color-mix(in srgb, var(--paper-deep) 72%, var(--wash));
  color: var(--ink-mute);
  border-color: color-mix(in srgb, var(--rule) 80%, transparent);
  cursor: not-allowed;
  opacity: 1;
}
.linkish {
  align-self: flex-start;
  border: none;
  background: transparent;
  color: var(--pine);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}
.linkish:disabled { opacity: 0.5; cursor: not-allowed; }

.adv {
  border: 1px dashed var(--rule);
  border-radius: 8px;
  padding: 8px 10px;
}
.adv summary {
  cursor: pointer;
  font-size: var(--fs-xs);
  font-weight: 700;
  color: var(--ink-mute);
  user-select: none;
}
.adv-body { margin-top: 10px; }

.smtp-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sm);
  color: var(--ink-soft);
  cursor: pointer;
}

.help-card .cfg-card-head {
  background: transparent;
}
.help-body h4 {
  margin: 0 0 6px;
  font-size: var(--fs-sm);
  color: var(--pine);
}
.help-body h4 + p { margin: 0 0 14px; }
.help-body p {
  font-size: var(--fs-xs);
  line-height: 1.55;
  color: var(--ink-soft);
}
.help-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}
.help-links a {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--pine);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.form-error { color: var(--clay); margin: 8px 0 0; }
.status-warn { margin: 8px 0 0; color: var(--clay); font-size: var(--fs-sm); line-height: 1.45; }

@media (max-width: 1024px) {
  .tri-row { grid-template-columns: 1fr; }
}
@media (max-width: 860px) {
  .split-grid,
  .slot-pair { grid-template-columns: 1fr; }
}
</style>
