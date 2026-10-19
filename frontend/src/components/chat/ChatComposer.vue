<template>
  <form class="composer" @submit.prevent="$emit('submit')">
    <input
      :value="modelValue"
      :disabled="disabled"
      placeholder="例如：最近有哪些 GLP-1 相关的临床进展？"
      aria-label="输入问题"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <button type="submit" :disabled="disabled || !modelValue.trim()">发送</button>
  </form>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
defineEmits(['update:modelValue', 'submit'])
</script>

<style scoped>
.composer {
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-3) 0 0;
  margin-top: auto;
  flex: none;
}
.composer input { flex: 1; }
</style>
