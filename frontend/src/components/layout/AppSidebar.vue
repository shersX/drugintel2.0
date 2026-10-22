<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <div class="side-head">
      <span v-if="!isCollapsed" class="side-title">{{ title }}</span>
      <button
        v-if="!forceExpanded"
        type="button"
        class="collapse-btn"
        :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
        :title="collapsed ? '展开侧栏' : '收起侧栏'"
        @click="toggle"
      >
        <svg
          v-if="collapsed"
          width="14"
          height="14"
          viewBox="0 0 14 14"
          aria-hidden="true"
        >
          <path d="M5 3 L9 7 L5 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M8 3 L12 7 L8 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.45" />
        </svg>
        <svg
          v-else
          width="14"
          height="14"
          viewBox="0 0 14 14"
          aria-hidden="true"
        >
          <path d="M9 3 L5 7 L9 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M6 3 L2 7 L6 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.45" />
        </svg>
      </button>
    </div>
    <div class="side-scroll">
      <nav class="side-nav" aria-label="模块导航">
        <router-link
          v-for="item in items"
          :key="item.key"
          :to="parseTo(item.to)"
          class="side-link"
          :class="{ on: item.match(route) }"
          :title="item.label"
        >
          <span class="ico" aria-hidden="true">{{ iconChar(item.icon) }}</span>
          <span v-if="!isCollapsed" class="lbl">{{ item.label }}</span>
        </router-link>
      </nav>
      <PipelineSidebarFilters
        v-if="showPipelineFilters && !isCollapsed"
      />
      <ChatSidebar
        v-if="showChatHistory && !isCollapsed"
        :groups="groupedConversations"
        :active-id="conversationId"
        :logged-in="Boolean(session.user)"
        :busy="asking"
        @new="onChatNew"
        @select="onChatSelect"
        @rename="renameConversation"
        @remove="onChatRemove"
        @login="openLoginPrompt('/chat')"
      />
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { openLoginPrompt } from '../../authPrompt'
import { useChatSessions } from '../../composables/useChatSessions'
import { session } from '../../session'
import ChatSidebar from '../chat/ChatSidebar.vue'
import PipelineSidebarFilters from '../pipeline/PipelineSidebarFilters.vue'

const props = defineProps({
  moduleKey: { type: String, required: true },
  moduleLabel: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  forceExpanded: { type: Boolean, default: false },
})

const route = useRoute()
const router = useRouter()
const STORAGE_KEY = 'drugintel.sidebar.collapsed'
const collapsed = ref(localStorage.getItem(STORAGE_KEY) === '1')
const isCollapsed = computed(() => (props.forceExpanded ? false : collapsed.value))

const {
  conversationId,
  asking,
  groupedConversations,
  loadList,
  startNew,
  selectConversation,
  renameConversation,
  removeConversation,
} = useChatSessions()

const title = computed(() => props.moduleLabel || '导航')
const showPipelineFilters = computed(
  () => props.moduleKey === 'pipeline' && route.path === '/pipeline',
)
const showChatHistory = computed(
  () => props.moduleKey === 'chat' && route.path === '/chat',
)

function onChatNew() {
  startNew(router, route)
}
function onChatSelect(id) {
  selectConversation(router, route, id)
}
function onChatRemove(item) {
  removeConversation(router, route, item)
}

onMounted(() => {
  if (showChatHistory.value) loadList()
})
watch(showChatHistory, (on) => {
  if (on) loadList()
})
watch(
  () => session.user?.id,
  () => {
    if (showChatHistory.value) loadList()
  },
)

function toggle() {
  collapsed.value = !collapsed.value
  localStorage.setItem(STORAGE_KEY, collapsed.value ? '1' : '0')
}

function parseTo(to) {
  if (typeof to !== 'string') return to
  const [path, qs] = to.split('?')
  if (!qs) return path
  const query = Object.fromEntries(new URLSearchParams(qs))
  return { path, query }
}

function iconChar(icon) {
  const map = {
    list: '≡',
    grid: '▦',
    bell: '◉',
    cpu: '◎',
    search: '⌕',
    mail: '✉',
    bot: '⚙',
    tag: '#',
    activity: '◈',
    users: '☺',
    plus: '＋',
  }
  return map[icon] || '·'
}
</script>

<style scoped>
.app-sidebar {
  width: var(--sidebar-w, 220px);
  flex: none;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--rule);
  background: color-mix(in srgb, var(--paper-deep) 55%, var(--paper));
  transition: width 200ms var(--ease-out);
}
.app-sidebar.collapsed {
  width: var(--sidebar-collapsed-w, 68px);
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 12px 10px;
  min-height: 48px;
  flex: none;
}
.side-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--moss);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.collapse-btn {
  display: inline-grid;
  place-items: center;
  line-height: 1;
  padding: 0;
  border: 1px solid var(--rule);
  background: var(--surface);
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--ink-mute);
  flex: none;
}
.collapse-btn svg { display: block; }
.collapse-btn:hover { color: var(--pine); border-color: var(--pine); }
.side-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.side-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 8px 8px;
  flex: none;
}
.side-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 8px;
  color: var(--ink-soft);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: background 160ms, color 160ms;
}
.side-link:hover {
  background: color-mix(in srgb, var(--moss) 10%, transparent);
  color: var(--ink);
}
.side-link.on {
  background: color-mix(in srgb, var(--moss) 18%, transparent);
  color: var(--pine);
}
.ico {
  width: 22px;
  text-align: center;
  flex: none;
  font-size: 14px;
  opacity: 0.85;
}
.lbl { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.collapsed .side-link { justify-content: center; padding: 10px 8px; }
.collapsed .side-head { justify-content: center; }
</style>
