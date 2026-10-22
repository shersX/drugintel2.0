<template>
  <div class="app-layout" :class="{ 'no-side': !showSidebar, 'drawer-open': drawerOpen }">
    <AppHeader :current-key="moduleKey" />
    <div class="app-body">
      <AppSidebar
        v-if="showSidebar"
        class="side-desktop"
        :module-key="moduleKey"
        :module-label="moduleLabel"
        :items="sideItems"
      />
      <!-- 窄屏抽屉：遮罩与面板同挂 body，避免遮罩盖住抽屉导致无法点击 -->
      <Teleport to="body">
        <div
          v-if="showSidebar && drawerOpen"
          class="drawer-mask"
          @click="closeDrawer"
        />
        <aside
          v-if="showSidebar"
          class="side-drawer"
          :class="{ open: drawerOpen }"
        >
          <AppSidebar
            :module-key="moduleKey"
            :module-label="moduleLabel"
            :items="sideItems"
            force-expanded
          />
        </aside>
      </Teleport>
      <main class="app-main" :class="{ compact: isChat }">
        <slot />
      </main>
    </div>
    <footer class="app-foot">
      <div class="foot-inner">
        <span><b>DrugIntel.ai</b> — 医药情报 · 聚类 · RAG 问答</span>
        <span>pgvector × FastAPI × Vue 3 · 毕业设计版</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  moduleShowsSidebar,
  resolveModule,
  sideItemsFor,
} from '../../nav.config'
import { useSidebarDrawer } from '../../composables/useSidebarDrawer'
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'

const route = useRoute()
const { drawerOpen, closeDrawer } = useSidebarDrawer()

const mod = computed(() => resolveModule(route))
const moduleKey = computed(() => mod.value?.key || '')
const moduleLabel = computed(() => mod.value?.label || '')
const sideItems = computed(() => (mod.value ? sideItemsFor(mod.value.key) : []))
const showSidebar = computed(() => moduleShowsSidebar(mod.value))
const isChat = computed(() => route.path === '/chat')

watch(
  () => route.fullPath,
  () => { closeDrawer() },
)
</script>

<style scoped>
.app-layout {
  display: grid;
  grid-template-rows: var(--header-h, 64px) minmax(0, 1fr) auto;
  width: 100%;
  min-height: 100dvh;
  min-height: 100vh;
}
.app-body {
  display: flex;
  min-height: 0;
  min-width: 0;
}
.app-body > .side-desktop {
  flex: none;
}
.app-body > .app-main {
  flex: 1;
}
.app-main {
  min-width: 0;
  min-height: 0;
  width: 100%;
  max-width: none;
  overflow: auto;
  padding: clamp(14px, 2vw, 24px) var(--app-pad-x) clamp(32px, 4vw, 48px);
  box-sizing: border-box;
}
.app-main.compact {
  padding-top: 12px;
  padding-bottom: 16px;
}
.app-foot {
  border-top: 1px solid var(--ink);
  background: var(--pine);
  color: rgba(245, 242, 233, 0.85);
}
.foot-inner {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 16px var(--app-pad-x);
  font-size: var(--fs-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.foot-inner b {
  font-family: var(--font-serif);
  font-size: 14px;
  letter-spacing: 0.02em;
  color: var(--paper);
  text-transform: none;
}
.side-drawer,
.drawer-mask { display: none; }

@media (max-width: 1024px) {
  .side-desktop { display: none; }
  .drawer-mask {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 46;
    background: rgba(28, 36, 32, 0.35);
  }
  .side-drawer {
    display: block;
    position: fixed;
    top: var(--header-h, 64px);
    left: 0;
    bottom: 0;
    z-index: 47;
    width: var(--sidebar-w, 220px);
    transform: translateX(-105%);
    transition: transform 220ms var(--ease-out);
    box-shadow: var(--shadow-md);
    pointer-events: none;
  }
  .side-drawer.open {
    transform: translateX(0);
    pointer-events: auto;
  }
  .side-drawer :deep(.app-sidebar) {
    height: 100%;
    width: 100% !important;
    border-right: none;
  }
}
</style>
