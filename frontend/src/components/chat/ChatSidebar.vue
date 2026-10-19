<template>
  <aside class="sidebar" :class="{ collapsed, drawer: drawerOpen }">
    <div class="side-top">
      <button type="button" class="new-btn" :disabled="busy" @click="$emit('new')">
        <span class="plus">＋</span> 新对话
      </button>
      <button type="button" class="icon-btn desktop-only" :title="collapsed ? '展开' : '折叠'" @click="$emit('toggle-collapse')">
        {{ collapsed ? '»' : '«' }}
      </button>
    </div>

    <div v-if="!loggedIn" class="side-empty">
      <p>登录后可查看历史会话</p>
      <button type="button" class="secondary" @click="$emit('login')">去登录</button>
    </div>

    <div v-else-if="!groups.length" class="side-empty">
      <p>暂无历史。发送第一条消息后会出现在这里。</p>
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
          <span class="side-title">{{ item.title || '新对话' }}</span>
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
  collapsed: { type: Boolean, default: false },
  drawerOpen: { type: Boolean, default: false },
  loggedIn: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})

defineEmits(['new', 'select', 'rename', 'remove', 'toggle-collapse', 'login'])
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 260px;
  min-width: 260px;
  height: 100%;
  background: var(--wash);
  border: 1px solid var(--rule);
  border-radius: var(--r-lg);
  overflow: hidden;
  transition: width 0.2s ease, min-width 0.2s ease, opacity 0.2s ease;
}
.sidebar.collapsed {
  width: 0;
  min-width: 0;
  opacity: 0;
  border: none;
  pointer-events: none;
}
.side-top {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--rule);
  flex: none;
}
.new-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-weight: 700;
}
.plus { font-size: 16px; line-height: 1; }
.icon-btn {
  width: 40px;
  flex: none;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--rule);
}
.side-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.side-group { margin-bottom: 12px; }
.group-label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
  padding: 6px 10px;
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
.side-title {
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
  padding: 24px 16px;
  color: var(--ink-mute);
  font-size: var(--fs-sm);
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
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
    min-width: 0;
    transform: translateX(-120%);
    opacity: 0;
    pointer-events: none;
    box-shadow: var(--shadow-sm);
  }
  .sidebar.drawer {
    transform: translateX(0);
    opacity: 1;
    pointer-events: auto;
  }
  .sidebar.collapsed { width: min(300px, calc(100vw - 24px)); }
  .desktop-only { display: none; }
}
</style>
