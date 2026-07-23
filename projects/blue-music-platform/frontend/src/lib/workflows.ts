import type { WorkflowStepType } from '../types/api'


export const WORKFLOW_STEP_ORDER: WorkflowStepType[] = [
  'collection',
  'analysis',
  'lyrics',
  'music',
]

export const WORKFLOW_STEP_LABELS: Record<WorkflowStepType, string> = {
  collection: '榜单采集',
  analysis: '内容分析',
  lyrics: '歌词创作',
  music: '音乐创作',
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
    if (step === 'music') {
      selected.add('analysis')
      selected.add('lyrics')
    }
  } else {
    selected.delete(step)
    if (step === 'analysis') {
      selected.delete('lyrics')
      selected.delete('music')
    }
    if (step === 'lyrics') selected.delete('music')
  }
  return WORKFLOW_STEP_ORDER.filter((value) => selected.has(value))
}
