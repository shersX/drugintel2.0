<template>
  <div class="card stat card-hover reveal" :style="{ '--reveal-delay': delay + 'ms' }">
    <div class="label">{{ label }}</div>
    <div class="value">{{ display }}</div>
    <span class="hairline"></span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useCountUp } from '../composables'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  delay: { type: Number, default: 0 },
})

const source = computed(() => props.value)
const display = useCountUp(source)
</script>

<style scoped>
.hairline {
  position: absolute;
  left: clamp(18px, 2.4vw, 28px);
  bottom: clamp(12px, 1.6vw, 18px);
  width: 40px;
  height: 2px;
  background: linear-gradient(90deg, var(--pine), var(--lime));
  transform: scaleX(0.4);
  transform-origin: left;
  transition: transform var(--dur-base) var(--ease-spring), width var(--dur-base) var(--ease-spring);
}
.card-hover:hover .hairline { transform: scaleX(1); width: 64px; }
</style>
