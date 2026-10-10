import { ref, watch, onBeforeUnmount } from 'vue'

/**
 * 数字滚动（odometer）：从 0 平滑递增到目标值。
 * easeOutExpo 曲线，时长随数值大小自适应（400–900ms）。
 */
export function useCountUp(source, { duration = 700 } = {}) {
  const display = ref(0)
  let raf = 0

  function animateTo(target) {
    cancelAnimationFrame(raf)
    const end = Number(target) || 0
    const start = display.value
    const span = Math.abs(end - start)
    if (span < 1) { display.value = end; return }
    const dur = Math.min(Math.max(duration, 400), 900)
    const t0 = performance.now()
    const step = (now) => {
      const p = Math.min((now - t0) / dur, 1)
      const eased = 1 - Math.pow(2, -10 * p)
      display.value = Math.round(start + (end - start) * eased)
      if (p < 1) raf = requestAnimationFrame(step)
      else display.value = end
    }
    raf = requestAnimationFrame(step)
  }

  watch(source, (v) => animateTo(v), { immediate: true })
  onBeforeUnmount(() => cancelAnimationFrame(raf))
  return display
}

/** 包裹 API 调用，统一给出 loading / error 状态 */
export function useAsync() {
  const loading = ref(false)
  const error = ref('')

  async function run(fn) {
    loading.value = true
    error.value = ''
    try {
      return await fn()
    } catch (e) {
      error.value = e.message || '请求失败'
      return null
    } finally {
      loading.value = false
    }
  }
  return { loading, error, run }
}
