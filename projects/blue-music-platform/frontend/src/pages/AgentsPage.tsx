import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Empty, Skeleton, Typography } from 'antd'
import { Bot, RefreshCw } from 'lucide-react'

import { getDashboard } from '../api/dashboard'
import { AgentStatusTag } from '../components/AgentStatusTag'
import { errorMessage } from '../lib/errors'
import type { DashboardAgentStatus } from '../types/api'

export function AgentsPage() {
  const [agents, setAgents] = useState<DashboardAgentStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setAgents((await getDashboard()).agents)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>Agent 状态</Typography.Title>
          <Typography.Text type="secondary">执行节点可用性</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>
          刷新
        </Button>
      </div>
      {error && <Alert type="error" showIcon title={error} />}
      {loading && !agents.length ? (
        <Skeleton active paragraph={{ rows: 5 }} />
      ) : agents.length ? (
        <div className="agent-grid">
          {agents.map((agent) => (
            <article className="agent-card" key={agent.agent}>
              <span className="agent-card-icon"><Bot size={21} /></span>
              <div className="agent-card-title">
                <Typography.Title level={2}>{agent.name}</Typography.Title>
                <AgentStatusTag status={agent.status} />
              </div>
              <Typography.Text type="secondary">{agent.message}</Typography.Text>
            </article>
          ))}
        </div>
      ) : (
        <Empty description="暂无可用 Agent" />
      )}
    </div>
  )
}
