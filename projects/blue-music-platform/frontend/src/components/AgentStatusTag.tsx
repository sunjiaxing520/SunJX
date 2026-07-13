import { Tag } from 'antd'

import type { AgentRuntimeStatus } from '../types/api'

const STATUS_MAP: Record<
  AgentRuntimeStatus,
  { color: string; label: string }
> = {
  not_configured: { color: 'default', label: '未配置' },
  idle: { color: 'blue', label: '空闲' },
  running: { color: 'processing', label: '运行中' },
  failed: { color: 'error', label: '异常' },
}

export function AgentStatusTag({ status }: { status: AgentRuntimeStatus }) {
  const item = STATUS_MAP[status]
  return <Tag color={item.color}>{item.label}</Tag>
}
