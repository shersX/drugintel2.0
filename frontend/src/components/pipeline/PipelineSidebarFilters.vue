<template>
  <div class="pipe-filters">
    <div class="filter-head">
      <span>筛选</span>
      <label class="watched">
        <input v-model="state.watchedOnly" type="checkbox" @change="applyFilters" />
        已关注
      </label>
    </div>

    <label class="f-label">靶点</label>
    <UiSelect
      v-model="state.target"
      :options="targetOptions"
      placeholder="全部靶点"
      size="sm"
      @change="applyFilters"
    />

    <label class="f-label">适应症</label>
    <UiSelect
      v-model="state.indication"
      :options="indicationOptions"
      placeholder="全部适应症"
      size="sm"
      @change="applyFilters"
    />

    <label class="f-label">研发公司</label>
    <UiSelect
      v-model="state.company"
      :options="companyOptions"
      placeholder="全部公司"
      size="sm"
      @change="applyFilters"
    />

    <label class="f-label">临床阶段</label>
    <div class="stage-checks">
      <label v-for="s in STAGE_OPTIONS" :key="s.value" class="chk">
        <input
          v-model="state.stages"
          type="checkbox"
          :value="s.value"
          @change="onStageChange"
        />
        {{ s.label }}
      </label>
      <label class="chk">
        <input v-model="state.marketedOnly" type="checkbox" @change="onMarketedToggle" />
        仅已获批
      </label>
    </div>

    <button type="button" class="ghost clear-btn" @click="clearFilters">清空筛选</button>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import UiSelect from '../UiSelect.vue'
import { usePipelineFilters } from '../../composables/usePipelineFilters'

const {
  state,
  STAGE_OPTIONS,
  targetOptions,
  indicationOptions,
  companyOptions,
  applyFilters,
  clearFilters,
  onMarketedToggle,
  loadFacets,
} = usePipelineFilters()

function onStageChange() {
  if (!state.stages.includes('approved')) state.marketedOnly = false
  else if (state.stages.includes('approved') && !state.marketedOnly) {
    /* 勾选已上市阶段不必强制 marketedOnly */
  }
  applyFilters()
}

onMounted(loadFacets)
</script>

<style scoped>
.pipe-filters {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px 14px;
  border-top: 1px solid var(--rule);
  margin-top: 4px;
}
.filter-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--moss);
  margin-bottom: 4px;
}
.watched {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--ink-mute);
}
.f-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-mute);
  margin-top: 6px;
}
.stage-checks { display: grid; gap: 4px; margin-top: 2px; }
.chk {
  font-size: 12px;
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--ink-soft);
  font-weight: 500;
}
.clear-btn {
  margin-top: 10px;
  align-self: flex-start;
  font-size: 12px;
  padding: 4px 10px;
  min-height: 0;
}
</style>
