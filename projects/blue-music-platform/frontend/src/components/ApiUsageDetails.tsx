import { Alert, Descriptions, Empty, Table, Tag, Typography, type TableProps } from 'antd'

import { providerName, totalTaskTokens } from '../lib/apiUsage'
import type { ApiUsageRecord } from '../types/api'

const OPERATION_LABELS: Record<string, string> = {
  'analysis.generate': '榜单分析',
  'lyrics.generate': '歌词生成',
  'music.generate': '音乐生成',
  'music.extend': '音乐续写',
}

export function ApiUsageCell({
  records,
  provider,
  model,
}: {
  records: ApiUsageRecord[]
  provider: string
  model: string | null
}) {
  const latest = records.at(-1)
  return (
    <div className="account-cell api-usage-cell">
      <strong>{providerName(latest, provider)}{model ? ` · ${model}` : ''}</strong>
      <small>{latest ? `${latest.method} ${latest.endpoint}` : '历史任务未记录接口'}</small>
    </div>
  )
}

export function ApiUsageDetails({ records }: { records: ApiUsageRecord[] }) {
  if (!records.length) {
    return (
      <section className="api-usage-details">
        <Typography.Title level={3}>接口用量</Typography.Title>
        <Alert type="info" showIcon title="该历史任务创建时尚未启用接口用量记录" />
      </section>
    )
  }

  const latest = records.at(-1)
  const columns: TableProps<ApiUsageRecord>['columns'] = [
    {
      title: '操作',
      dataIndex: 'operation',
      width: 100,
      render: (value: string) => OPERATION_LABELS[value] ?? value,
    },
    {
      title: '接口',
      key: 'endpoint',
      width: 280,
      render: (_, record) => (
        <div className="api-endpoint-cell">
          <code>{record.method}</code>
          <span>{record.endpoint}</span>
          {record.external_request_id && <small>请求编号：{record.external_request_id}</small>}
        </div>
      ),
    },
    {
      title: 'Token',
      key: 'tokens',
      width: 130,
      render: (_, record) => (
        <div className="token-breakdown">
          <strong>{record.total_tokens.toLocaleString()}</strong>
          <small>
            输入 {record.input_tokens.toLocaleString()} · 输出 {record.output_tokens.toLocaleString()}
            {record.cached_tokens > 0 ? ` · 缓存 ${record.cached_tokens.toLocaleString()}` : ''}
          </small>
        </div>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      width: 80,
      render: (value: number | null) => value === null ? '-' : `${(value / 1000).toFixed(2)} 秒`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 70,
      render: (value: ApiUsageRecord['status']) => (
        <Tag color={value === 'completed' ? 'success' : 'error'}>
          {value === 'completed' ? '成功' : '失败'}
        </Tag>
      ),
    },
  ]

  return (
    <section className="api-usage-details">
      <Typography.Title level={3}>接口用量</Typography.Title>
      <Descriptions
        size="small"
        column={2}
        items={[
          { key: 'provider', label: '供应商', children: providerName(latest, latest?.provider ?? '-') },
          { key: 'model', label: '模型', children: latest?.model ?? '本地规则' },
          { key: 'calls', label: '执行次数', children: String(records.length) },
          { key: 'tokens', label: '累计 Token', children: totalTaskTokens(records).toLocaleString() },
        ]}
      />
      <Table<ApiUsageRecord>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={records}
        pagination={false}
        scroll={{ x: 660 }}
        locale={{ emptyText: <Empty description="暂无接口记录" /> }}
        className="data-table api-usage-table"
      />
    </section>
  )
}
