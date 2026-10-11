<template>
  <div>
    <header class="ed-head reveal">
      <div class="ed-kicker">Models · 接口</div>
      <h1 class="ed-title">模型配置</h1>
      <p class="ed-lede">保存多套 OpenAI 兼容接口，启用一套后，摘要、向量、重排和问答都会使用它。</p>
    </header>

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
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { useAsync } from '../composables'
import ProfileForm from './ProfileForm.vue'

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

async function finishTest(target, slot, run) {
  beginTest(target, slot)
  const label = slotLabel[slot] || '接口'
  busy.value = true
  try {
    await run()
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

onMounted(load)
</script>

<style scoped>
.note { margin-bottom: 20px; color: var(--ink-soft); }
.profile { margin-bottom: 16px; }
.profile-head { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.form-error { color: var(--clay); margin: 8px 0 0; }
</style>
