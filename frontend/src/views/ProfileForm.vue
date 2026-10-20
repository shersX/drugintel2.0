<template>
  <form class="grid" @submit.prevent="submit">
    <label class="wide">
      名称
      <input v-model="local.name" required placeholder="例如：硅基流动" />
    </label>

    <label v-if="allowSync" class="wide sync">
      <input type="checkbox" v-model="syncFromChat" />
      <span>嵌入 / 重排沿用对话的 Key 与地址</span>
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
        模型
        <input v-model="local.chat_model" required />
      </label>
      <div class="row wide">
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
        模型
        <input v-model="local.embedding_model" required />
      </label>
      <div class="row wide">
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
        模型
        <input v-model="local.reranker_model" required />
      </label>
      <div class="row wide">
        <button type="button" class="secondary" :disabled="busy" @click="testSlot('rerank')">测试连接</button>
      </div>
      <p v-if="notices.rerank" class="wide result" :class="noticeClass(notices.rerank)">{{ notices.rerank.text }}</p>
    </fieldset>

    <div class="row wide actions">
      <button type="submit" :disabled="busy">{{ submitLabel }}</button>
      <button v-if="showCancel" type="button" class="secondary" :disabled="busy" @click="emit('cancel')">取消</button>
    </div>
  </form>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  model: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  keepChat: { type: Boolean, default: false },
  keepEmbedding: { type: Boolean, default: false },
  keepRerank: { type: Boolean, default: false },
  submitLabel: { type: String, default: '保存' },
  stamp: { type: Number, default: 0 },
  notices: { type: Object, default: () => ({}) },
  allowSync: { type: Boolean, default: false },
  showCancel: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'test', 'cancel'])

const local = reactive(emptyLocal())
const syncFromChat = ref(false)

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
  ],
  () => copyFrom(props.model || {}),
  { immediate: true },
)

watch(syncFromChat, (on) => {
  if (!on) return
  local.embedding_base_url = local.base_url
  local.reranker_base_url = local.base_url
  if (local.api_key) {
    local.embedding_api_key = local.api_key
    local.reranker_api_key = local.api_key
  }
})

watch(
  () => [local.base_url, local.api_key],
  () => {
    if (!syncFromChat.value) return
    local.embedding_base_url = local.base_url
    local.reranker_base_url = local.base_url
    if (local.api_key) {
      local.embedding_api_key = local.api_key
      local.reranker_api_key = local.api_key
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
  }
  if (syncFromChat.value) {
    return {
      ...base,
      embedding_api_key: local.api_key || local.embedding_api_key,
      embedding_base_url: local.base_url.trim(),
      reranker_api_key: local.api_key || local.reranker_api_key,
      reranker_base_url: local.base_url.trim(),
    }
  }
  return {
    ...base,
    embedding_api_key: local.embedding_api_key,
    reranker_api_key: local.reranker_api_key,
  }
}

function noticeClass(notice) {
  if (notice.ok === true) return 'ok'
  if (notice.ok === false) return 'bad'
  return 'pending'
}

function testSlot(slot) {
  const form = payload()
  const picked = {
    chat: { base_url: form.base_url, api_key: form.api_key },
    embedding: { base_url: form.embedding_base_url, api_key: form.embedding_api_key },
    rerank: { base_url: form.reranker_base_url, api_key: form.reranker_api_key },
  }[slot]
  emit('test', { slot, ...picked })
}

function submit() {
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
