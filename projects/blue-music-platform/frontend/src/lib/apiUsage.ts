import type { ApiUsageRecord } from '../types/api'


export function totalTaskTokens(records: ApiUsageRecord[]) {
  return records.reduce((total, record) => total + record.total_tokens, 0)
}


export function providerName(record: ApiUsageRecord | undefined, fallback: string) {
  if (fallback === 'local') return '本地规则基线'
  if (record?.endpoint.includes('bigmodel.cn')) return '智谱 BigModel'
  if (record?.endpoint.includes('mureka.ai')) return 'Mureka'
  if (record?.endpoint.includes('minimaxi.com')) return 'MiniMax'
  return fallback
}
