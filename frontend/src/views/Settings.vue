<template>
  <div class="settings-root">
    <SystemConfigPanel v-if="activeTab === 'system'" />
    <EntityLexiconPanel v-if="activeTab === 'entities'" />
    <CrawlerRegistryPanel v-if="activeTab === 'crawlers'" />

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
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import SystemConfigPanel from '../components/settings/SystemConfigPanel.vue'
import EntityLexiconPanel from '../components/settings/EntityLexiconPanel.vue'
import CrawlerRegistryPanel from '../components/settings/CrawlerRegistryPanel.vue'

const route = useRoute()
const router = useRouter()

const LEGACY_SYSTEM_TABS = new Set(['models', 'rag', 'mail'])
const tabIds = new Set(['system', 'crawlers', 'keywords', 'entities', ...LEGACY_SYSTEM_TABS])

function normalizeTab(raw) {
  if (!raw || typeof raw !== 'string') return 'system'
  if (LEGACY_SYSTEM_TABS.has(raw)) return 'system'
  if (tabIds.has(raw)) return raw
  return 'system'
}

const activeTab = ref(normalizeTab(route.query.tab))

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
const loaded = reactive({ keywords: false })

function parseAliases(text) {
  return String(text || '')
    .split(/[,，;；\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function ensureTabLoaded(tab) {
  if (tab === 'keywords' && !loaded.keywords) loadKeywords(1)
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
  const next = normalizeTab(tab)
  if (next !== tab) {
    activeTab.value = next
    return
  }
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab } })
  }
  ensureTabLoaded(tab)
})

watch(
  () => route.query.tab,
  (tab) => {
    const next = normalizeTab(typeof tab === 'string' ? tab : '')
    if (activeTab.value !== next) activeTab.value = next
  },
)

onMounted(() => {
  if (normalizeTab(route.query.tab) !== route.query.tab) {
    router.replace({ query: { ...route.query, tab: activeTab.value } })
  }
  ensureTabLoaded(activeTab.value)
})
</script>

<style scoped>
.settings-root {
  width: 0;
  min-width: 100%;
  max-width: 100%;
}
.form-error { color: var(--clay); margin: 8px 0 0; }
.cfg-table { width: 100%; border-collapse: collapse; }
.cfg-table th, .cfg-table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line, #e6e0d6); vertical-align: middle; }
.cfg-table .wide { width: 100%; min-width: 140px; }
.actions { white-space: nowrap; display: flex; gap: 8px; }
.kw-toolbar, .kw-new, .kw-pager { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
.kw-toolbar .search { flex: 1; min-width: 160px; }
.kw-new input { flex: 1; min-width: 140px; }
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: transparent;
  color: var(--pine);
  padding: 8px 14px;
}
.seg-btn.on { background: var(--pine); color: var(--paper); }
</style>
