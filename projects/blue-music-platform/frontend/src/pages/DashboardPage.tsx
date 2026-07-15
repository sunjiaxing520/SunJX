import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Empty,
  Skeleton,
  Space,
  Steps,
  Table,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import {
  BarChart3,
  Bot,
  ChartNoAxesCombined,
  ExternalLink,
  FileMusic,
  Music2,
  RefreshCw,
} from 'lucide-react'

import { getDashboard } from '../api/dashboard'
import { AgentStatusTag } from '../components/AgentStatusTag'
import { CollapsibleList } from '../components/CollapsibleList'
import { providerName, sortDailyUsageNewestFirst } from '../lib/apiUsage'
import { errorMessage } from '../lib/errors'
import type {
  ApiUsageRecord,
  DailyApiUsage,
  DashboardResponse,
  ProviderAccountUsage,
} from '../types/api'

const METRICS = [
  { key: 'crawled_today', label: '今日采集', icon: BarChart3, tone: 'coral' },
  { key: 'analyzed_today', label: '今日分析', icon: ChartNoAxesCombined, tone: 'blue' },
  { key: 'lyrics_tasks_today', label: '歌词任务', icon: FileMusic, tone: 'yellow' },
  { key: 'music_tasks_today', label: '创作任务', icon: Music2, tone: 'green' },
] as const

const TASK_TYPE_LABELS: Record<string, string> = {
  analysis: '榜单分析',
  lyrics: '歌词创作',
  music: '音乐创作',
  provider_test: '接口测试',
}

const BALANCE_LABELS = {
  available: { text: '已同步', color: 'success' },
  manual: { text: '控制台查询', color: 'warning' },
  not_applicable: { text: '无需余额', color: 'default' },
  hidden: { text: '无查看权限', color: 'default' },
  error: { text: '查询失败', color: 'error' },
} as const

const DAILY_USAGE_PREVIEW_LIMIT = 3

function formatNumber(value: number) {
  return value.toLocaleString('zh-CN')
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const dailyUsage = useMemo(
    () => sortDailyUsageNewestFirst(data?.api_usage.daily ?? []),
    [data?.api_usage.daily],
  )

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

  const providerColumns: TableProps<ProviderAccountUsage>['columns'] = [
    {
      title: '供应商账户',
      dataIndex: 'display_name',
      render: (name: string, provider) => (
        <div className="account-cell">
          <strong>{name}</strong>
          <small>{provider.models.join(' · ') || '未配置模型'}</small>
        </div>
      ),
    },
    {
      title: '余额',
      key: 'balance',
      width: 180,
      render: (_, provider) => {
        const label = BALANCE_LABELS[provider.balance_status]
        return (
          <Space size={6}>
            <Tooltip title={provider.balance_message}>
              <Tag color={label.color}>{provider.balance_amount === null ? label.text : `${provider.balance_amount} ${provider.balance_unit ?? ''}`}</Tag>
            </Tooltip>
            {provider.console_url && (
              <Tooltip title="打开供应商控制台">
                <Button
                  type="text"
                  size="small"
                  icon={<ExternalLink size={15} />}
                  href={provider.console_url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`打开 ${nameForProvider(provider)} 控制台`}
                />
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    { title: '今日执行', dataIndex: 'executions_today', width: 100 },
    {
      title: '今日 Token',
      dataIndex: 'tokens_today',
      width: 130,
      render: formatNumber,
    },
    {
      title: '近 7 日 Token',
      dataIndex: 'tokens_7d',
      width: 140,
      render: formatNumber,
    },
  ]

  const dailyColumns: TableProps<DailyApiUsage>['columns'] = [
    { title: '日期', dataIndex: 'day', width: 130 },
    { title: '任务执行', dataIndex: 'executions', width: 100 },
    { title: '外部调用', dataIndex: 'external_calls', width: 100 },
    { title: '输入 Token', dataIndex: 'input_tokens', width: 130, render: formatNumber },
    { title: '输出 Token', dataIndex: 'output_tokens', width: 130, render: formatNumber },
    { title: '总 Token', dataIndex: 'total_tokens', width: 130, render: formatNumber },
  ]

  const recentCallColumns: TableProps<ApiUsageRecord>['columns'] = [
    {
      title: '任务',
      key: 'task',
      width: 130,
      render: (_, record) => `${TASK_TYPE_LABELS[record.task_type] ?? record.task_type} #${record.task_id}`,
    },
    {
      title: '模型 / 接口',
      key: 'endpoint',
      render: (_, record) => (
        <div className="account-cell api-usage-cell">
          <strong>{providerName(record, record.provider)}{record.model ? ` · ${record.model}` : ''}</strong>
          <small>{record.method} {record.endpoint}</small>
        </div>
      ),
    },
    { title: '输入', dataIndex: 'input_tokens', width: 100, render: formatNumber },
    { title: '输出', dataIndex: 'output_tokens', width: 100, render: formatNumber },
    { title: '总 Token', dataIndex: 'total_tokens', width: 110, render: formatNumber },
    {
      title: '状态',
      dataIndex: 'status',
      width: 84,
      render: (status: ApiUsageRecord['status']) => <Tag color={status === 'completed' ? 'success' : 'error'}>{status === 'completed' ? '成功' : '失败'}</Tag>,
    },
  ]

  if (loading && !data) return <Skeleton active paragraph={{ rows: 8 }} />

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>工作概览</Typography.Title>
          <Typography.Text type="secondary">今日任务、Agent 状态与接口用量</Typography.Text>
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

      <section className="content-section usage-board-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>API 用量与余额</Typography.Title>
            <Typography.Text type="secondary">今日数据与近 7 日账户消耗</Typography.Text>
          </div>
        </div>
        <div className="usage-stat-strip">
          <div><span>今日执行</span><strong>{formatNumber(data?.api_usage.metrics.executions_today ?? 0)}</strong></div>
          <div><span>今日外部调用</span><strong>{formatNumber(data?.api_usage.metrics.external_calls_today ?? 0)}</strong></div>
          <div><span>今日 Token</span><strong>{formatNumber(data?.api_usage.metrics.tokens_today ?? 0)}</strong></div>
          <div><span>近 7 日 Token</span><strong>{formatNumber(data?.api_usage.metrics.tokens_7d ?? 0)}</strong></div>
        </div>
        <Table<ProviderAccountUsage>
          rowKey="provider"
          columns={providerColumns}
          dataSource={data?.api_usage.providers ?? []}
          pagination={false}
          scroll={{ x: 760 }}
          className="data-table"
        />
        <div className="usage-subheading-row">
          <Typography.Title level={3} className="usage-subheading">每日用量</Typography.Title>
          <Typography.Text type="secondary">最新日期优先，默认显示最近 3 天</Typography.Text>
        </div>
        <CollapsibleList
          items={dailyUsage}
          previewCount={DAILY_USAGE_PREVIEW_LIMIT}
          expandText={(hiddenCount) => `展开较早 ${hiddenCount} 天`}
          collapseText="收起较早记录"
        >
          {(visibleDailyUsage) => (
            <Table<DailyApiUsage>
              rowKey="day"
              size="small"
              columns={dailyColumns}
              dataSource={visibleDailyUsage}
              pagination={false}
              scroll={{ x: 760 }}
              className="data-table"
            />
          )}
        </CollapsibleList>
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
          <div>
            <Typography.Title level={2}>最近接口调用</Typography.Title>
            <Typography.Text type="secondary">接口、模型与实际返回用量，默认显示最新 5 条</Typography.Text>
          </div>
        </div>
        <CollapsibleList items={data?.api_usage.recent_calls ?? []}>
          {(visibleCalls) => (
            <Table<ApiUsageRecord>
              rowKey="id"
              columns={recentCallColumns}
              dataSource={visibleCalls}
              pagination={false}
              scroll={{ x: 900 }}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无接口调用" /> }}
              className="data-table"
            />
          )}
        </CollapsibleList>
      </section>
    </div>
  )
}

function nameForProvider(provider: ProviderAccountUsage) {
  return provider.display_name || provider.provider
}
