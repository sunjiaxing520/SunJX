import type { ApiUsageRecord, DailyApiUsage } from '../types/api'

const API_USAGE_TASK_TYPE_ORDER = ['analysis', 'lyrics', 'music', 'provider_test']

export interface ApiUsageTaskGroup {
  taskType: string
  records: ApiUsageRecord[]
}


export function totalTaskTokens(records: ApiUsageRecord[]) {
  return records.reduce((total, record) => total + record.total_tokens, 0)
}


export function sortDailyUsageNewestFirst(records: DailyApiUsage[]) {
  return [...records].sort((left, right) => right.day.localeCompare(left.day))
}


export function groupApiUsageByTaskType(records: ApiUsageRecord[]): ApiUsageTaskGroup[] {
  const grouped = new Map<string, ApiUsageRecord[]>()
  records.forEach((record) => {
    const taskRecords = grouped.get(record.task_type) ?? []
    taskRecords.push(record)
    grouped.set(record.task_type, taskRecords)
  })

  return Array.from(grouped, ([taskType, taskRecords]) => ({
    taskType,
    records: taskRecords,
  })).sort((left, right) => {
    const leftIndex = API_USAGE_TASK_TYPE_ORDER.indexOf(left.taskType)
    const rightIndex = API_USAGE_TASK_TYPE_ORDER.indexOf(right.taskType)
    const leftOrder = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex
    const rightOrder = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex
    return leftOrder - rightOrder || left.taskType.localeCompare(right.taskType)
  })
}


export function providerName(record: ApiUsageRecord | undefined, fallback: string) {
  if (fallback === 'local') return '本地规则基线'
  if (fallback === 'bigmodel') return '智谱 BigModel'
  if (fallback === 'deepseek') return 'DeepSeek'
  if (fallback === 'qwen') return '阿里百炼 Qwen'
  if (fallback === 'minimax') return 'MiniMax'
  if (record?.endpoint.includes('bigmodel.cn')) return '智谱 BigModel'
  if (record?.endpoint.includes('deepseek.com')) return 'DeepSeek'
  if (record?.endpoint.includes('aliyuncs.com')) return '阿里百炼 Qwen'
  if (record?.endpoint.includes('mureka.ai')) return 'Mureka'
  if (record?.endpoint.includes('minimaxi.com')) return 'MiniMax'
  return fallback
}
