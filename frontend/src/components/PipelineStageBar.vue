<template>
  <div class="stage-bar" :class="{ special: isSpecial }" :title="label">
    <template v-if="isSpecial">
      <span class="special-pill">{{ label || '未知' }}</span>
    </template>
    <template v-else>
      <div
        v-for="(node, i) in nodes"
        :key="node.key"
        class="node-wrap"
      >
        <span
          class="node"
          :class="{ done: i < fillTo, current: i === fillTo, upcoming: i > fillTo }"
        />
        <span v-if="i < nodes.length - 1" class="seg" :class="{ filled: i < fillTo }" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: { type: String, default: 'unknown' },
  label: { type: String, default: '' },
})

const nodes = [
  { key: 'preclinical' },
  { key: 'phase1' },
  { key: 'phase2' },
  { key: 'phase3' },
  { key: 'nda' },
  { key: 'approved' },
]

const ORDER = nodes.map((n) => n.key)

const isSpecial = computed(() => {
  const s = props.stage || 'unknown'
  return s === 'partner' || s === 'unknown' || !ORDER.includes(s)
})

const fillTo = computed(() => {
  const s = props.stage || 'unknown'
  const idx = ORDER.indexOf(s)
  return idx >= 0 ? idx : -1
})
</script>

<style scoped>
.stage-bar {
  display: flex;
  align-items: center;
  min-width: 168px;
  width: 100%;
  max-width: 280px;
  gap: 0;
}
.node-wrap {
  display: flex;
  align-items: center;
  flex: 1;
}
.node-wrap:last-child { flex: 0; }
.node {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 2px solid color-mix(in srgb, var(--pine) 22%, var(--line));
  background: transparent;
  flex-shrink: 0;
  z-index: 1;
}
.node.done {
  background: var(--moss);
  border-color: var(--moss);
}
.node.current {
  background: var(--pine);
  border-color: var(--pine);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--moss) 28%, transparent);
}
.node.upcoming {
  background: transparent;
}
.seg {
  flex: 1;
  height: 2px;
  margin: 0 -1px;
  background: color-mix(in srgb, var(--pine) 12%, var(--line));
  min-width: 8px;
}
.seg.filled {
  background: color-mix(in srgb, var(--moss) 75%, var(--pine));
}
.special-pill {
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-mute);
  padding: 2px 8px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--pine) 8%, transparent);
}
</style>
