import type { WorkflowStepType } from '../types/api'


export const WORKFLOW_STEP_ORDER: WorkflowStepType[] = [
  'collection',
  'analysis',
  'lyrics',
]

export const WORKFLOW_STEP_LABELS: Record<WorkflowStepType, string> = {
  collection: '榜单采集',
  analysis: '内容分析',
  lyrics: '歌词创作',
}

export function toggleWorkflowStep(
  current: WorkflowStepType[],
  step: WorkflowStepType,
  checked: boolean,
): WorkflowStepType[] {
  const selected = new Set(current)
  if (checked) {
    selected.add(step)
    if (step === 'lyrics') selected.add('analysis')
  } else {
    selected.delete(step)
    if (step === 'analysis') selected.delete('lyrics')
  }
  return WORKFLOW_STEP_ORDER.filter((value) => selected.has(value))
}
