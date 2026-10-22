<template>
  <div class="ui-select" :class="[`size-${size}`, { open, disabled }]" ref="root">
    <button
      type="button"
      class="ui-select-trigger"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
    >
      <span class="ui-select-label" :class="{ placeholder: !selected }">
        {{ selected ? selected.label : placeholder }}
      </span>
      <svg class="chev" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
    </button>
    <ul v-if="open" class="ui-select-menu" role="listbox">
      <li
        v-if="allowEmpty"
        role="option"
        class="ui-select-option"
        :class="{ on: modelValue === '' || modelValue == null }"
        @click="pick('')"
      >{{ placeholder }}</li>
      <li
        v-for="opt in options"
        :key="String(opt.value)"
        role="option"
        class="ui-select-option"
        :class="{ on: String(opt.value) === String(modelValue) }"
        @click="pick(opt.value)"
      >{{ opt.label }}</li>
      <li v-if="!options.length" class="ui-select-empty">暂无选项</li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '全部' },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'sm' },
  allowEmpty: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'change'])

const open = ref(false)
const root = ref(null)

const selected = computed(() =>
  props.options.find((o) => String(o.value) === String(props.modelValue)),
)

function toggle() {
  if (props.disabled) return
  open.value = !open.value
}

function pick(value) {
  emit('update:modelValue', value)
  emit('change', value)
  open.value = false
}

function onDoc(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}

onMounted(() => document.addEventListener('click', onDoc))
onUnmounted(() => document.removeEventListener('click', onDoc))
</script>

<style scoped>
.ui-select {
  position: relative;
  width: var(--ui-select-w, 100%);
  max-width: 100%;
  box-sizing: border-box;
}
.ui-select-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid var(--rule-strong);
  background: var(--surface);
  color: var(--ink);
  border-radius: var(--r-md);
  cursor: pointer;
  text-align: left;
  font: inherit;
  font-weight: 500;
  transition: border-color 160ms, box-shadow 160ms;
}
.size-sm .ui-select-trigger { padding: 6px 10px; font-size: 12px; min-height: 32px; }
.size-md .ui-select-trigger { padding: 10px 12px; font-size: 13px; min-height: 40px; }
.ui-select-trigger:hover:not(:disabled) { border-color: var(--ink-mute); }
.ui-select.open .ui-select-trigger,
.ui-select-trigger:focus-visible {
  border-color: var(--pine);
  box-shadow: 0 0 0 3px var(--wash-strong);
  outline: none;
}
.ui-select-trigger:disabled { opacity: 0.55; cursor: not-allowed; }
.ui-select-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ui-select-label.placeholder { color: var(--ink-mute); }
.chev { flex: none; color: var(--ink-mute); transition: transform 160ms; }
.open .chev { transform: rotate(180deg); color: var(--pine); }
.ui-select-menu {
  position: absolute;
  z-index: 40;
  left: 0; right: 0;
  top: calc(100% + 4px);
  margin: 0;
  padding: 4px;
  list-style: none;
  max-height: 220px;
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-md);
}
.ui-select-option {
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink-soft);
}
.ui-select-option:hover {
  background: color-mix(in srgb, var(--moss) 12%, transparent);
  color: var(--ink);
}
.ui-select-option.on {
  background: color-mix(in srgb, var(--moss) 18%, transparent);
  color: var(--pine);
  font-weight: 700;
}
.ui-select-empty {
  padding: 10px;
  font-size: 12px;
  color: var(--ink-mute);
  text-align: center;
}
</style>
