import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Empty, Skeleton, Steps, Typography } from 'antd'
import {
  BarChart3,
  Bot,
  ChartNoAxesCombined,
  FileMusic,
  Music2,
  RefreshCw,
} from 'lucide-react'

import { getDashboard } from '../api/dashboard'
import { AgentStatusTag } from '../components/AgentStatusTag'
import { errorMessage } from '../lib/errors'
import type { DashboardResponse } from '../types/api'

const METRICS = [
  { key: 'crawled_today', label: '今日采集', icon: BarChart3, tone: 'coral' },
  { key: 'analyzed_today', label: '今日分析', icon: ChartNoAxesCombined, tone: 'blue' },
  { key: 'lyrics_tasks_today', label: '歌词任务', icon: FileMusic, tone: 'yellow' },
  { key: 'music_tasks_today', label: '创作任务', icon: Music2, tone: 'green' },
] as const

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await getDashboard())
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading && !data) return <Skeleton active paragraph={{ rows: 8 }} />

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>工作概览</Typography.Title>
          <Typography.Text type="secondary">今日任务与 Agent 运行情况</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon title={error} closable />}

      <section className="metrics-grid" aria-label="今日数据">
        {METRICS.map(({ key, label, icon: Icon, tone }) => (
          <div className="metric-card" key={key}>
            <span className={`metric-icon metric-icon-${tone}`}><Icon size={19} /></span>
            <div>
              <span>{label}</span>
              <strong>{data?.metrics[key] ?? 0}</strong>
            </div>
          </div>
        ))}
      </section>

      <section className="content-section workflow-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>标准创作流程</Typography.Title>
            <Typography.Text type="secondary">按固定顺序衔接各 Agent</Typography.Text>
          </div>
          <span className="workflow-state">等待任务</span>
        </div>
        <Steps
          responsive
          items={[
            { title: '榜单采集' },
            { title: '内容分析' },
            { title: '歌词创作' },
            { title: '音乐创作' },
          ]}
        />
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>Agent 状态</Typography.Title>
            <Typography.Text type="secondary">当前账号可使用的执行节点</Typography.Text>
          </div>
          <Bot size={20} />
        </div>
        <div className="agent-status-list">
          {data?.agents.map((agent) => (
            <div className="agent-status-row" key={agent.agent}>
              <span className="agent-status-icon"><Bot size={17} /></span>
              <span className="agent-status-name">
                <strong>{agent.name}</strong>
                <small>{agent.message}</small>
              </span>
              <AgentStatusTag status={agent.status} />
            </div>
          ))}
          {!data?.agents.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可用 Agent" />}
        </div>
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <Typography.Title level={2}>最近任务</Typography.Title>
        </div>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无执行记录" />
      </section>
    </div>
  )
}
