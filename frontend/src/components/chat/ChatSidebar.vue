<template>
  <aside class="sidebar" :class="{ drawer: drawerOpen }">
    <div class="side-head">
      <div class="side-title-row">
        <h2>历史会话</h2>
        <button
          type="button"
          class="icon-btn mobile-close"
          title="关闭"
          @click="$emit('close-drawer')"
        >×</button>
      </div>
      <button type="button" class="new-btn" :disabled="busy" @click="$emit('new')">
        <span class="plus">＋</span> 新对话
      </button>
    </div>

    <div v-if="!loggedIn" class="side-empty">
      <p>登录后可查看与管理历史会话。</p>
      <button type="button" class="secondary" @click="$emit('login')">去登录</button>
    </div>

    <div v-else-if="!groups.length" class="side-empty">
      <p>还没有会话。发送第一条消息后，记录会出现在这里。</p>
    </div>

    <nav v-else class="side-list">
      <section v-for="g in groups" :key="g.label" class="side-group">
        <div class="group-label">{{ g.label }}</div>
        <button
          v-for="item in g.items"
          :key="item.id"
          type="button"
          class="side-item"
          :class="{ active: item.id === activeId }"
          :disabled="busy"
          @click="$emit('select', item.id)"
        >
          <span class="side-item-title">{{ item.title || '新对话' }}</span>
          <span class="side-actions" @click.stop>
            <button type="button" class="mini" title="重命名" @click="$emit('rename', item)">✎</button>
            <button type="button" class="mini danger" title="删除" @click="$emit('remove', item)">×</button>
          </span>
        </button>
      </section>
    </nav>
  </aside>
</template>

<script setup>
defineProps({
  groups: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
  drawerOpen: { type: Boolean, default: false },
  loggedIn: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})

defineEmits(['new', 'select', 'rename', 'remove', 'close-drawer', 'login'])
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: color-mix(in srgb, var(--wash) 88%, var(--surface));
  border: 1px solid var(--rule);
  border-radius: var(--r-lg);
  overflow: hidden;
}
.side-head {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 14px 12px;
  border-bottom: 1px solid var(--rule);
  flex: none;
}
.side-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.side-title-row h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.02em;
}
.icon-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-mute);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.mobile-close { display: none; }
.new-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-weight: 700;
}
.plus { font-size: 16px; line-height: 1; }
.side-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 8px 14px;
}
.side-group { margin-bottom: 14px; }
.group-label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
  padding: 4px 10px 8px;
}
.side-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  background: transparent;
  color: var(--ink);
  border: none;
  border-left: 3px solid transparent;
  border-radius: var(--r-sm);
  padding: 10px 10px;
  font-weight: 500;
  cursor: pointer;
}
.side-item:hover { background: var(--surface); }
.side-item.active {
  background: var(--surface);
  border-left-color: var(--pine);
  color: var(--pine);
}
.side-item-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-sm);
}
.side-actions {
  display: none;
  gap: 2px;
  flex: none;
}
.side-item:hover .side-actions,
.side-item.active .side-actions { display: flex; }
.mini {
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-mute);
  font-size: 14px;
  cursor: pointer;
}
.mini:hover { background: var(--wash); color: var(--ink); }
.mini.danger:hover { color: var(--clay); }
.side-empty {
  padding: 20px 16px;
  color: var(--ink-mute);
  font-size: var(--fs-sm);
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
  line-height: 1.55;
}
.side-empty p { margin: 0; }

@media (max-width: 900px) {
  .sidebar {
    position: fixed;
    z-index: 35;
    left: 12px;
    top: 90px;
    bottom: 16px;
    width: min(300px, calc(100vw - 24px));
    transform: translateX(-120%);
    opacity: 0;
    pointer-events: none;
    box-shadow: var(--shadow-sm);
    transition: transform 0.2s ease, opacity 0.2s ease;
  }
  .sidebar.drawer {
    transform: translateX(0);
    opacity: 1;
    pointer-events: auto;
  }
  .mobile-close { display: inline-grid; place-items: center; }
}
</style>
