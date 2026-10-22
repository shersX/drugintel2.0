<template>
  <div class="chat-hist">
    <div class="hist-head">
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
  </div>
</template>

<script setup>
defineProps({
  groups: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
  loggedIn: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})

defineEmits(['new', 'select', 'rename', 'remove', 'login'])
</script>

<style scoped>
.chat-hist {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  border-top: 1px solid var(--rule);
  margin-top: 4px;
}
.hist-head {
  padding: 10px 10px 8px;
  flex: none;
}
.new-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-weight: 700;
  font-size: 12px;
  padding: 8px 10px;
  min-height: 0;
}
.plus { font-size: 14px; line-height: 1; }
.side-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 14px;
  min-height: 0;
}
.side-group { margin-bottom: 12px; }
.group-label {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
  padding: 4px 10px 6px;
}
.side-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  text-align: left;
  background: transparent;
  color: var(--ink-soft);
  border: none;
  border-left: 3px solid transparent;
  border-radius: 8px;
  padding: 8px 8px;
  font-weight: 500;
  cursor: pointer;
}
.side-item:hover {
  background: color-mix(in srgb, var(--moss) 10%, transparent);
  color: var(--ink);
}
.side-item.active {
  background: color-mix(in srgb, var(--moss) 18%, transparent);
  border-left-color: var(--pine);
  color: var(--pine);
}
.side-item-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.side-actions {
  display: none;
  gap: 2px;
  flex: none;
}
.side-item:hover .side-actions,
.side-item.active .side-actions { display: flex; }
.mini {
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-mute);
  font-size: 13px;
  cursor: pointer;
}
.mini:hover { background: var(--wash); color: var(--ink); }
.mini.danger:hover { color: var(--clay); }
.side-empty {
  padding: 14px 12px;
  color: var(--ink-mute);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
  line-height: 1.55;
}
.side-empty p { margin: 0; }
</style>
