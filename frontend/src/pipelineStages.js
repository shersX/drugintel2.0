/**
 * 管线研发阶段文案 — 与 backend.src.pipeline_intel.normalize.STAGE_LABELS 保持一致。
 * 仪表盘 / 列表 / 筛选 / 详情 一律从此处取中文，禁止再散落硬编码。
 */

export const STAGE_LABELS = {
  preclinical: '临床前',
  phase1: 'I 期',
  phase2: 'II 期',
  phase3: 'III 期',
  nda: '申报上市',
  approved: '已获批',
  partner: '合作方推进',
  unknown: '未知',
}

/** 进度条节点顺序（与后端 STAGE_BAR_ORDER 一致） */
export const STAGE_BAR_ORDER = [
  'preclinical',
  'phase1',
  'phase2',
  'phase3',
  'nda',
  'approved',
]

/** 筛选 / 下拉用选项（不含 partner，与侧栏历史一致；详情编辑可用全部） */
export const STAGE_FILTER_OPTIONS = STAGE_BAR_ORDER.map((value) => ({
  value,
  label: STAGE_LABELS[value],
}))

export const STAGE_EDIT_OPTIONS = [
  ...STAGE_FILTER_OPTIONS,
  { value: 'partner', label: STAGE_LABELS.partner },
  { value: 'unknown', label: STAGE_LABELS.unknown },
]

export function stageLabel(code) {
  const key = code || 'unknown'
  return STAGE_LABELS[key] || key || STAGE_LABELS.unknown
}
