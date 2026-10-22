<template>
  <form class="grid" @submit.prevent="submit">
    <label class="wide">
      名称
      <input v-model="local.name" required placeholder="例如：硅基流动" />
    </label>

    <label v-if="allowSync" class="wide sync">
      <input type="checkbox" v-model="syncFromChat" />
      <span>嵌入 / 重排 / 视觉沿用对话的 Key 与地址</span>
    </label>

    <fieldset class="block">
      <legend>对话 · 摘要与过滤</legend>
      <label>
        API Key
        <input
          v-model="local.api_key"
          type="password"
          autocomplete="off"
          :placeholder="keepChat ? '已保存，留空则不修改' : 'sk-...'"
          :required="!keepChat"
        />
      </label>
      <label class="wide">
        Base URL
        <input v-model="local.base_url" required placeholder="https://api.siliconflow.cn/v1" />
      </label>
      <label class="wide">
        对话模型
        <UiSelect
          v-if="modelLists.chat.length"
          v-model="local.chat_model"
          :options="modelOptions(modelLists.chat, local.chat_model)"
          :allow-empty="false"
          size="md"
          placeholder="请选择模型"
        />
        <input
          v-else
          v-model="local.chat_model"
          required
          placeholder="先点下方「拉取模型」，或直接手填模型 ID"
        />
        <span class="field-hint">
          {{ modelLists.chat.length ? `已载入 ${modelLists.chat.length} 个，可下拉选择` : '请先拉取模型列表' }}
        </span>
      </label>
      <div class="row wide">
        <button type="button" class="secondary" :disabled="busy" @click="fetchModels('chat')">拉取模型</button>
        <button type="button" class="secondary" :disabled="busy" @click="testSlot('chat')">测试连接</button>
      </div>
      <p v-if="notices.chat" class="wide result" :class="noticeClass(notices.chat)">{{ notices.chat.text }}</p>
    </fieldset>

    <fieldset class="block">
      <legend>嵌入 · 向量检索</legend>
      <label>
        API Key
        <input
          v-model="local.embedding_api_key"
          type="password"
          autocomplete="off"
          :placeholder="embeddingKeyPlaceholder"
          :required="!keepEmbedding && !syncFromChat"
          :disabled="syncFromChat"
        />
      </label>
      <label>
        向量维度
        <input v-model.number="local.embedding_dim" type="number" min="1" max="4096" required />
        <span class="field-hint">须与模型实际维度一致；与库中不一致时启用前会确认重建。</span>
      </label>
      <label class="wide">
        Base URL
        <input
          v-model="local.embedding_base_url"
          required
          placeholder="https://api.siliconflow.cn/v1"
          :disabled="syncFromChat"
        />
      </label>
      <label class="wide">
        嵌入模型
        <UiSelect
          v-if="modelLists.embedding.length"
          v-model="local.embedding_model"
          :options="modelOptions(modelLists.embedding, local.embedding_model)"
          :allow-empty="false"
          size="md"
          placeholder="请选择模型"
        />
        <input
          v-else
          v-model="local.embedding_model"
          required
          placeholder="先点下方「拉取模型」，或直接手填模型 ID"
        />
        <span class="field-hint">
          {{ modelLists.embedding.length ? `已载入 ${modelLists.embedding.length} 个，可下拉选择` : '请先拉取模型列表' }}
        </span>
      </label>
      <div class="row wide">
        <button type="button" class="secondary" :disabled="busy || syncFromChat" @click="fetchModels('embedding')">拉取模型</button>
        <button type="button" class="secondary" :disabled="busy" @click="testSlot('embedding')">测试连接</button>
      </div>
      <p v-if="notices.embedding" class="wide result" :class="noticeClass(notices.embedding)">{{ notices.embedding.text }}</p>
    </fieldset>

    <fieldset class="block">
      <legend>重排 · RAG 问答</legend>
      <label>
        API Key
        <input
          v-model="local.reranker_api_key"
          type="password"
          autocomplete="off"
          :placeholder="rerankKeyPlaceholder"
          :required="!keepRerank && !syncFromChat"
          :disabled="syncFromChat"
        />
      </label>
      <label class="wide">
        Base URL
        <input
          v-model="local.reranker_base_url"
          required
          placeholder="https://api.siliconflow.cn/v1"
          :disabled="syncFromChat"
        />
      </label>
      <label class="wide">
        重排模型
        <UiSelect
          v-if="modelLists.rerank.length"
          v-model="local.reranker_model"
          :options="modelOptions(modelLists.rerank, local.reranker_model)"
          :allow-empty="false"
          size="md"
          placeholder="请选择模型"
        />
        <input
          v-else
          v-model="local.reranker_model"
          required
          placeholder="先点下方「拉取模型」，或直接手填模型 ID"
        />
        <span class="field-hint">
          {{ modelLists.rerank.length ? `已载入 ${modelLists.rerank.length} 个，可下拉选择` : '请先拉取模型列表' }}
        </span>
      </label>
      <div class="row wide">
        <button type="button" class="secondary" :disabled="busy || syncFromChat" @click="fetchModels('rerank')">拉取模型</button>
        <button type="button" class="secondary" :disabled="busy" @click="testSlot('rerank')">测试连接</button>
      </div>
      <p v-if="notices.rerank" class="wide result" :class="noticeClass(notices.rerank)">{{ notices.rerank.text }}</p>
    </fieldset>

    <fieldset class="block">
      <legend>视觉 · 管线图片抽取</legend>
      <label>
        API Key
        <input
          v-model="local.vision_api_key"
          type="password"
          autocomplete="off"
          :placeholder="visionKeyPlaceholder"
          :disabled="syncFromChat"
        />
      </label>
      <label class="wide">
        Base URL
        <input
          v-model="local.vision_base_url"
          placeholder="可与对话相同；管线同步前必须配置"
          :disabled="syncFromChat"
        />
      </label>
      <label class="wide">
        视觉模型
        <UiSelect
          v-if="modelLists.vision.length"
          v-model="local.vision_model"
          :options="modelOptions(modelLists.vision, local.vision_model)"
          allow-empty
          size="md"
          placeholder="未选择"
        />
        <input
          v-else
          v-model="local.vision_model"
          placeholder="先点下方「拉取模型」，或直接手填视觉模型 ID"
        />
        <span class="field-hint">
          {{ modelLists.vision.length ? `已载入 ${modelLists.vision.length} 个，可下拉选择` : '请先拉取模型列表（优先展示视觉类）' }}
        </span>
      </label>
      <div class="row wide">
        <button type="button" class="secondary" :disabled="busy || syncFromChat" @click="fetchModels('vision')">拉取模型</button>
        <button type="button" class="secondary" :disabled="busy" @click="testSlot('vision')">测试连接</button>
      </div>
      <p class="wide field-hint">视觉模型可留空后仍启用配置（新闻不受影响）；同步管线前必须选好视觉模型。</p>
      <p v-if="notices.vision" class="wide result" :class="noticeClass(notices.vision)">{{ notices.vision.text }}</p>
    </fieldset>

    <div class="row wide actions">
      <button type="submit" :disabled="busy">{{ submitLabel }}</button>
      <button v-if="showCancel" type="button" class="secondary" :disabled="busy" @click="emit('cancel')">取消</button>
    </div>
  </form>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../api'
import UiSelect from '../components/UiSelect.vue'

const props = defineProps({
  model: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  keepChat: { type: Boolean, default: false },
  keepEmbedding: { type: Boolean, default: false },
  keepRerank: { type: Boolean, default: false },
  keepVision: { type: Boolean, default: false },
  submitLabel: { type: String, default: '保存' },
  stamp: { type: Number, default: 0 },
  notices: { type: Object, default: () => ({}) },
  allowSync: { type: Boolean, default: false },
  showCancel: { type: Boolean, default: false },
  profileId: { type: [Number, String], default: null },
})
const emit = defineEmits(['submit', 'test', 'cancel'])

const local = reactive(emptyLocal())
const syncFromChat = ref(false)
const modelLists = reactive({ chat: [], embedding: [], rerank: [], vision: [] })

const embeddingKeyPlaceholder = computed(() => {
  if (syncFromChat.value) return '沿用对话 Key'
  if (props.keepEmbedding) return '已保存，留空则不修改'
  return 'sk-...'
})
const rerankKeyPlaceholder = computed(() => {
  if (syncFromChat.value) return '沿用对话 Key'
  if (props.keepRerank) return '已保存，留空则不修改'
  return 'sk-...'
})
const visionKeyPlaceholder = computed(() => {
  if (syncFromChat.value) return '沿用对话 Key'
  if (props.keepVision) return '已保存，留空则不修改'
  return '可选 sk-...'
})

function modelOptions(list, current) {
  const opts = (list || []).map((id) => ({ value: id, label: id }))
  if (current && !(list || []).includes(current)) {
    opts.push({ value: current, label: `${current}（当前）` })
  }
  return opts
}

function emptyLocal() {
  return {
    name: '',
    api_key: '',
    base_url: '',
    chat_model: '',
    embedding_api_key: '',
    embedding_base_url: '',
    embedding_model: '',
    embedding_dim: 1024,
    reranker_api_key: '',
    reranker_base_url: '',
    reranker_model: '',
    vision_api_key: '',
    vision_base_url: '',
    vision_model: '',
  }
}

function copyFrom(source) {
  local.name = source.name || ''
  local.api_key = ''
  local.base_url = source.base_url || ''
  local.chat_model = source.chat_model || ''
  local.embedding_api_key = ''
  local.embedding_base_url = source.embedding_base_url || ''
  local.embedding_model = source.embedding_model || ''
  local.embedding_dim = Number(source.embedding_dim) || 1024
  local.reranker_api_key = ''
  local.reranker_base_url = source.reranker_base_url || ''
  local.reranker_model = source.reranker_model || ''
  local.vision_api_key = ''
  local.vision_base_url = source.vision_base_url || source.base_url || ''
  local.vision_model = source.vision_model || ''
  syncFromChat.value = false
}

watch(
  () => [
    props.stamp,
    props.model?.id,
    props.model?.name,
    props.model?.base_url,
    props.model?.chat_model,
    props.model?.embedding_base_url,
    props.model?.embedding_model,
    props.model?.embedding_dim,
    props.model?.reranker_base_url,
    props.model?.reranker_model,
    props.model?.vision_base_url,
    props.model?.vision_model,
  ],
  () => copyFrom(props.model || {}),
  { immediate: true },
)

watch(syncFromChat, (on) => {
  if (!on) return
  local.embedding_base_url = local.base_url
  local.reranker_base_url = local.base_url
  local.vision_base_url = local.base_url
  if (local.api_key) {
    local.embedding_api_key = local.api_key
    local.reranker_api_key = local.api_key
    local.vision_api_key = local.api_key
  }
})

watch(
  () => [local.base_url, local.api_key],
  () => {
    if (!syncFromChat.value) return
    local.embedding_base_url = local.base_url
    local.reranker_base_url = local.base_url
    local.vision_base_url = local.base_url
    if (local.api_key) {
      local.embedding_api_key = local.api_key
      local.reranker_api_key = local.api_key
      local.vision_api_key = local.api_key
    }
  },
)

function payload() {
  const base = {
    name: local.name.trim(),
    api_key: local.api_key,
    base_url: local.base_url.trim(),
    chat_model: local.chat_model.trim(),
    embedding_base_url: local.embedding_base_url.trim(),
    embedding_model: local.embedding_model.trim(),
    embedding_dim: Number(local.embedding_dim),
    reranker_base_url: local.reranker_base_url.trim(),
    reranker_model: local.reranker_model.trim(),
    vision_base_url: (local.vision_base_url || local.base_url).trim(),
    vision_model: local.vision_model.trim(),
  }
  if (syncFromChat.value) {
    return {
      ...base,
      embedding_api_key: local.api_key || local.embedding_api_key,
      embedding_base_url: local.base_url.trim(),
      reranker_api_key: local.api_key || local.reranker_api_key,
      reranker_base_url: local.base_url.trim(),
      vision_api_key: local.api_key || local.vision_api_key,
      vision_base_url: local.base_url.trim(),
    }
  }
  return {
    ...base,
    embedding_api_key: local.embedding_api_key,
    reranker_api_key: local.reranker_api_key,
    vision_api_key: local.vision_api_key,
  }
}

function noticeClass(notice) {
  if (notice.ok === true) return 'ok'
  if (notice.ok === false) return 'bad'
  return 'pending'
}

function slotCreds(slot) {
  const form = payload()
  return {
    chat: { base_url: form.base_url, api_key: form.api_key },
    embedding: { base_url: form.embedding_base_url, api_key: form.embedding_api_key },
    rerank: { base_url: form.reranker_base_url, api_key: form.reranker_api_key },
    vision: { base_url: form.vision_base_url || form.base_url, api_key: form.vision_api_key || form.api_key },
  }[slot]
}

function testSlot(slot) {
  emit('test', { slot, ...slotCreds(slot) })
}

function pickIds(models, slot) {
  const all = models.map((m) => m.id).filter(Boolean)
  const preferred = models
    .filter((m) => m.kind === slot || (slot === 'chat' && (m.kind === 'chat' || m.kind === 'vision')))
    .map((m) => m.id)
  // 有分类命中时：命中项置顶，其余仍保留，方便手选
  if (!preferred.length) return all
  const rest = all.filter((id) => !preferred.includes(id))
  return [...preferred, ...rest]
}

async function fetchModels(slot) {
  const creds = slotCreds(slot)
  try {
    const data = await api.listLlmModels({
      ...creds,
      slot,
      profile_id: props.profileId || undefined,
    })
    const models = data?.models || []
    modelLists[slot] = pickIds(models, slot)
    const current = {
      chat: local.chat_model,
      embedding: local.embedding_model,
      rerank: local.reranker_model,
      vision: local.vision_model,
    }[slot]
    // 若当前为空且列表有值，自动选第一项（视觉槽位不强制）
    if (!current && modelLists[slot].length && slot !== 'vision') {
      if (slot === 'chat') local.chat_model = modelLists[slot][0]
      if (slot === 'embedding') local.embedding_model = modelLists[slot][0]
      if (slot === 'rerank') local.reranker_model = modelLists[slot][0]
    }
    emit('test', {
      slot,
      ...creds,
      ok: true,
      text: `已拉取 ${modelLists[slot].length} 个模型，请在上方下拉框中选择`,
    })
  } catch (err) {
    emit('test', { slot, ...creds, ok: false, text: err.message || '拉取失败' })
  }
}

function submit() {
  if (modelLists.chat.length && !local.chat_model.trim()) return
  if (modelLists.embedding.length && !local.embedding_model.trim()) return
  if (modelLists.rerank.length && !local.reranker_model.trim()) return
  emit('submit', payload())
}
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px 16px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--fs-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
}
.wide { grid-column: 1 / -1; }
.sync {
  flex-direction: row;
  align-items: center;
  gap: 10px;
  text-transform: none;
  letter-spacing: 0;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--ink-soft);
}
.sync input { width: auto; margin: 0; }
.field-hint {
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
  color: var(--ink-soft);
  font-size: var(--fs-sm);
  line-height: 1.4;
}
.block {
  grid-column: 1 / -1;
  margin: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px 14px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px 16px;
}
legend {
  padding: 0 6px;
  font-size: var(--fs-sm);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink);
}
.actions { gap: 10px; }
select {
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--paper, #fff);
  color: var(--ink);
  font: inherit;
  text-transform: none;
  letter-spacing: 0;
}
.result {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: var(--fs-sm);
  font-weight: 650;
  letter-spacing: 0;
  text-transform: none;
}
.result.ok { color: var(--moss); background: color-mix(in srgb, var(--moss) 14%, transparent); }
.result.bad { color: var(--clay); background: color-mix(in srgb, var(--clay) 12%, transparent); }
.result.pending { color: var(--ink-soft); background: var(--paper-2, transparent); }
</style>
