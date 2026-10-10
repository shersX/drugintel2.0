<template>
  <div class="trend">
    <svg
      v-if="points.length"
      class="trend-svg"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
      role="img"
      aria-label="新闻趋势折线图"
    >
      <defs>
        <linearGradient id="trend-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#1C4B33" />
          <stop offset="100%" stop-color="#8CC63F" />
        </linearGradient>
        <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(140,198,63,0.30)" />
          <stop offset="100%" stop-color="rgba(140,198,63,0)" />
        </linearGradient>
      </defs>

      <!-- 网格基线 -->
      <line
        v-for="i in 3"
        :key="i"
        :y1="(H / 4) * i" :y2="(H / 4) * i"
        x1="0" :x2="W"
        stroke="rgba(23,42,30,0.09)"
        stroke-width="1"
        vector-effect="non-scaling-stroke"
      />

      <!-- 面积 -->
      <path :d="areaPath" fill="url(#trend-fill)" class="trend-area" />

      <!-- 折线：描边生长动画 -->
      <path
        ref="linePath"
        :d="linePath"
        fill="none"
        stroke="url(#trend-line)"
        stroke-width="2.5"
        vector-effect="non-scaling-stroke"
        class="trend-stroke"
      />

      <!-- 悬停锚点 -->
      <g v-for="(p, i) in points" :key="`d${i}`">
        <circle
          :cx="p.x" :cy="p.y" r="3.5"
          class="trend-dot"
          vector-effect="non-scaling-stroke"
        />
        <rect
          :x="p.x - stepX / 2" y="0"
          :width="stepX" :height="H"
          fill="transparent"
          @mouseenter="active = i"
          @mouseleave="active = -1"
        />
      </g>

      <!-- 提示框（SVG 内绘制，避免坐标换算） -->
      <g v-if="active >= 0" class="trend-tip">
        <line
          :x1="points[active].x" :x2="points[active].x"
          y1="0" :y2="H"
          stroke="rgba(28,75,51,0.45)"
          stroke-dasharray="3 4"
          vector-effect="non-scaling-stroke"
        />
        <g :transform="tipTransform(active)">
          <rect x="-46" y="-34" width="92" height="26" rx="7"
                fill="#FDFCF8" stroke="rgba(23,42,30,0.25)"
                vector-effect="non-scaling-stroke" />
          <text x="0" y="-16" text-anchor="middle" class="tip-text">
            {{ items[active].date.slice(5) }} · {{ items[active].count }} 条
          </text>
        </g>
      </g>
    </svg>

    <div class="trend-axis" v-if="items.length">
      <span>{{ items[0].date.slice(5) }}</span>
      <span>{{ items[Math.floor(items.length / 2)].date.slice(5) }}</span>
      <span>{{ items[items.length - 1].date.slice(5) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
})

const W = 1000
const H = 260
const PAD = 14
const active = ref(-1)

const stepX = computed(() =>
  props.items.length > 1 ? W / (props.items.length - 1) : W
)

const points = computed(() => {
  const counts = props.items.map((d) => Number(d.count) || 0)
  const max = Math.max(...counts, 1)
  return props.items.map((d, i) => ({
    x: i * stepX.value,
    y: H - PAD - (counts[i] / max) * (H - PAD * 2),
  }))
})

/** Catmull-Rom → 三次贝塞尔，得到平滑曲线 */
const smoothPath = computed(() => {
  if (points.value.length < 2) return ''
  const p = points.value
  let d = `M ${p[0].x},${p[0].y}`
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[Math.max(i - 1, 0)]
    const p1 = p[i]
    const p2 = p[i + 1]
    const p3 = p[Math.min(i + 2, p.length - 1)]
    const c1x = p1.x + (p2.x - p0.x) / 6
    const c1y = p1.y + (p2.y - p0.y) / 6
    const c2x = p2.x - (p3.x - p1.x) / 6
    const c2y = p2.y - (p3.y - p1.y) / 6
    d += ` C ${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`
  }
  return d
})

const linePath = computed(() => smoothPath.value)
const areaPath = computed(() =>
  smoothPath.value ? `${smoothPath.value} L ${W},${H} L 0,${H} Z` : ''
)

function tipTransform(i) {
  const p = points.value[i]
  return `translate(${p.x},${p.y})`
}
</script>

<style scoped>
.trend { display: flex; flex-direction: column; gap: var(--sp-2); }
.trend-svg { width: 100%; height: clamp(180px, 26vh, 260px); display: block; }
.trend-area {
  animation: area-in var(--dur-slow) var(--ease-out) 300ms backwards;
  transform-origin: bottom;
}
@keyframes area-in { from { opacity: 0; } }
.trend-stroke {
  stroke-dasharray: 3000;
  stroke-dashoffset: 3000;
  animation: draw 1.6s var(--ease-out) forwards;
}
@keyframes draw { to { stroke-dashoffset: 0; } }
.trend-dot {
  fill: var(--surface);
  stroke: var(--pine);
  stroke-width: 2;
  opacity: 0;
  transition: opacity var(--dur-fast);
}
.trend-svg:hover .trend-dot { opacity: 1; }
.tip-text {
  fill: var(--ink);
  font-size: 22px;
  font-family: var(--font-mono);
}
.trend-tip { pointer-events: none; }
.trend-axis {
  display: flex;
  justify-content: space-between;
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  font-family: var(--font-mono);
}
</style>
