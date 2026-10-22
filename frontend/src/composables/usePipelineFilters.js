import { computed, reactive, ref } from 'vue'
import { api } from '../api'

const state = reactive({
  q: '',
  target: '',
  indication: '',
  company: '',
  stages: [],
  modality: '',
  watchedOnly: false,
  marketedOnly: false,
  page: 1,
  pageSize: 30,
})

const facets = ref({
  targets: [],
  indications: [],
  companies: [],
  modalities: [],
  stages: [],
})

/** 筛选变更计数，列表页 watch 后 reload */
const revision = ref(0)

const STAGE_OPTIONS = [
  { value: 'preclinical', label: '临床前' },
  { value: 'phase1', label: 'I 期' },
  { value: 'phase2', label: 'II 期' },
  { value: 'phase3', label: 'III 期' },
  { value: 'nda', label: '申报' },
  { value: 'approved', label: '已上市' },
]

function bump() {
  revision.value += 1
}

function filterParams() {
  return {
    q: state.q,
    target: state.target,
    indication: state.indication,
    company: state.company,
    stages: state.stages.join(','),
    modality: state.modality,
    status: 'active',
    watched_only: state.watchedOnly || undefined,
    page: state.page,
    page_size: state.pageSize,
  }
}

const hasActiveFilters = computed(() =>
  Boolean(
    state.q
    || state.target
    || state.indication
    || state.company
    || state.stages.length
    || state.modality
    || state.watchedOnly
    || state.marketedOnly,
  ),
)

function clearFilters() {
  state.q = ''
  state.target = ''
  state.indication = ''
  state.company = ''
  state.stages = []
  state.modality = ''
  state.watchedOnly = false
  state.marketedOnly = false
  state.page = 1
  bump()
}

function setModality(v) {
  state.modality = v
  state.page = 1
  bump()
}

function setPage(p) {
  state.page = p
  bump()
}

function onMarketedToggle() {
  if (state.marketedOnly) {
    if (!state.stages.includes('approved')) state.stages = [...state.stages, 'approved']
  } else {
    state.stages = state.stages.filter((s) => s !== 'approved')
  }
  state.page = 1
  bump()
}

function applyFilters() {
  state.page = 1
  bump()
}

async function loadFacets() {
  try {
    const data = await api.pipelineFacets('active')
    if (data) facets.value = data
  } catch {
    /* ignore */
  }
}

const targetOptions = computed(() =>
  (facets.value.targets || []).map((t) => ({
    value: t.value,
    label: `${t.value} (${t.count})`,
  })),
)
const indicationOptions = computed(() =>
  (facets.value.indications || []).map((t) => ({
    value: t.value,
    label: `${t.value} (${t.count})`,
  })),
)
const companyOptions = computed(() =>
  (facets.value.companies || []).map((t) => ({
    value: t.value,
    label: `${t.value} (${t.count})`,
  })),
)

export function usePipelineFilters() {
  return {
    state,
    facets,
    revision,
    STAGE_OPTIONS,
    hasActiveFilters,
    targetOptions,
    indicationOptions,
    companyOptions,
    filterParams,
    clearFilters,
    setModality,
    setPage,
    onMarketedToggle,
    applyFilters,
    loadFacets,
    bump,
  }
}
