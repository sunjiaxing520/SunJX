import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  type TableProps,
} from 'antd'
import { Eye, Play, RefreshCw } from 'lucide-react'

import { listAnalysisTasks, runAnalysis } from '../api/analysis'
import { listRankingEntries } from '../api/rankings'
import { ApiUsageCell, ApiUsageDetails } from '../components/ApiUsageDetails'
import { totalTaskTokens } from '../lib/apiUsage'
import { errorMessage } from '../lib/errors'
import type { AnalysisTask, CreationDirection, RankingEntry } from '../types/api'

const TEMPO_LABELS = { slow: '慢速', medium: '适中', fast: '快速' }
const GENDER_LABELS = { male: '男声', female: '女声', unspecified: '不限' }

export function AnalysisPage() {
  const { message } = App.useApp()
  const [entries, setEntries] = useState<RankingEntry[]>([])
  const [tasks, setTasks] = useState<AnalysisTask[]>([])
  const [selectedIds, setSelectedIds] = useState<React.Key[]>([])
  const [windowDays, setWindowDays] = useState(7)
  const [activeTask, setActiveTask] = useState<AnalysisTask | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ranking, history] = await Promise.all([
        listRankingEntries({ pageSize: 100 }),
        listAnalysisTasks(),
      ])
      setEntries(ranking.items)
      setTasks(history.items)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const submit = async () => {
    setRunning(true)
    try {
      const task = await runAnalysis(selectedIds.map(Number), windowDays)
      message.success('分析完成，已生成创作方向')
      setActiveTask(task)
      setSelectedIds([])
      await load()
    } catch (runError) {
      message.error(errorMessage(runError))
      await load()
    } finally {
      setRunning(false)
    }
  }

  const entryColumns: TableProps<RankingEntry>['columns'] = [
    { title: '排名', dataIndex: 'rank', width: 72 },
    {
      title: '歌曲',
      dataIndex: 'title',
      render: (title: string, entry) => (
        <div className="account-cell"><strong>{title}</strong><small>{entry.artist}</small></div>
      ),
    },
  ]

  const taskColumns: TableProps<AnalysisTask>['columns'] = [
    { title: '任务', dataIndex: 'id', width: 78, render: (id: number) => `#${id}` },
    {
      title: '日期范围',
      key: 'range',
      width: 220,
      render: (_, task) => `${task.window_start} 至 ${task.window_end}`,
    },
    { title: '歌曲数', dataIndex: 'selected_entry_count', width: 90 },
    {
      title: '模型 / 接口',
      key: 'provider',
      width: 280,
      render: (_, task) => <ApiUsageCell records={task.api_usage} provider={task.provider} model={task.model} />,
    },
    {
      title: 'Token',
      key: 'tokens',
      width: 100,
      render: (_, task) => totalTaskTokens(task.api_usage).toLocaleString(),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: AnalysisTask['status']) => (
        <Tag color={status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'processing'}>
          {status === 'completed' ? '已完成' : status === 'failed' ? '失败' : '运行中'}
        </Tag>
      ),
    },
    {
      title: '',
      key: 'detail',
      width: 60,
      render: (_, task) => (
        <Button type="text" icon={<Eye size={16} />} aria-label="查看分析报告" onClick={() => setActiveTask(task)} />
      ),
    },
  ]

  const metrics = activeTask?.report?.trend_metrics
  const directions = activeTask?.report?.creation_directions ?? []
  const availableDays = Number(metrics?.available_days ?? 0)
  const confidence = String(activeTask?.report?.evidence.confidence ?? 'low')
  const confidenceLabel = { low: '较低', medium: '中等', high: '较高' }[confidence] ?? confidence

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>内容分析</Typography.Title>
          <Typography.Text type="secondary">从连续榜单中整理可供作词和音乐生成使用的创作方向</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>刷新</Button>
      </div>

      {error && <Alert type="error" showIcon title={error} />}

      <section className="content-section analysis-source-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>选择分析范围</Typography.Title>
            <Typography.Text type="secondary">
              未勾选时默认分析最新榜单前 30 首；有几天数据就按几天计算
            </Typography.Text>
          </div>
          <Space wrap>
            <Segmented
              value={windowDays}
              options={[{ label: '7 天', value: 7 }, { label: '15 天', value: 15 }, { label: '30 天', value: 30 }]}
              onChange={(value) => setWindowDays(Number(value))}
            />
            <Button type="primary" icon={<Play size={16} />} loading={running} disabled={!entries.length} onClick={submit}>
              {selectedIds.length ? `分析所选 ${selectedIds.length} 首` : '分析最新前 30 首'}
            </Button>
          </Space>
        </div>
        <Table<RankingEntry>
          rowKey="id"
          columns={entryColumns}
          dataSource={entries}
          loading={loading}
          rowSelection={{ selectedRowKeys: selectedIds, onChange: setSelectedIds }}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          className="data-table"
        />
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>分析记录</Typography.Title>
            <Typography.Text type="secondary">最近 15 次分析及结构化报告</Typography.Text>
          </div>
        </div>
        <Table<AnalysisTask>
          rowKey="id"
          columns={taskColumns}
          dataSource={tasks}
          loading={loading}
          pagination={false}
          scroll={{ x: 760 }}
          className="data-table"
        />
      </section>

      <Drawer
        title={`分析报告${activeTask ? ` #${activeTask.id}` : ''}`}
        open={Boolean(activeTask)}
        onClose={() => setActiveTask(null)}
        size="large"
      >
        {activeTask ? (
          <div className="report-stack">
            <ApiUsageDetails records={activeTask.api_usage} />
            {activeTask.error_message && <Alert type="error" showIcon title={activeTask.error_message} />}
            {activeTask.report ? (
              <>
                <Alert
                  type={availableDays >= 7 ? 'success' : 'warning'}
                  showIcon
                  title={`有效数据 ${availableDays} 天 · 证据可信度${confidenceLabel}`}
                  description={activeTask.report.trend_summary}
                />
                <Descriptions
                  size="small"
                  column={2}
                  items={[
                    { key: 'rising', label: '上升', children: String(metrics?.rising_count ?? 0) },
                    { key: 'new', label: '新出现', children: String(metrics?.new_count ?? 0) },
                    { key: 'stable', label: '稳定', children: String(metrics?.stable_count ?? 0) },
                    { key: 'falling', label: '下降', children: String(metrics?.falling_count ?? 0) },
                  ]}
                />
                <div className="direction-list">
                  {directions.map((direction, index) => (
                    <DirectionView direction={direction} index={index} key={`${direction.name}-${index}`} />
                  ))}
                </div>
              </>
            ) : <Empty description="该任务没有生成分析报告" />}
          </div>
        ) : <Empty description="暂无报告" />}
      </Drawer>
    </div>
  )
}

function DirectionView({ direction, index }: { direction: CreationDirection; index: number }) {
  const tagGroups = useMemo(() => [
    { label: '曲风', values: direction.genre_tags },
    { label: '情绪', values: direction.mood_tags },
    { label: '主题', values: direction.theme_keywords },
    { label: '场景', values: direction.scene_tags },
    { label: '乐器', values: direction.instrument_tags },
  ], [direction])

  return (
    <section className="direction-item">
      <div className="direction-heading">
        <span>{index + 1}</span>
        <div><Typography.Title level={3}>{direction.name}</Typography.Title><Typography.Text type="secondary">{TEMPO_LABELS[direction.tempo]} · {GENDER_LABELS[direction.vocal_gender]}</Typography.Text></div>
      </div>
      {tagGroups.map((group) => (
        <div className="tag-line" key={group.label}>
          <strong>{group.label}</strong>
          <Space size={[4, 4]} wrap>{group.values.map((value) => <Tag key={value}>{value}</Tag>)}</Space>
        </div>
      ))}
      <Typography.Paragraph><strong>人声：</strong>{direction.vocal_style}</Typography.Paragraph>
      <Typography.Paragraph><strong>结构：</strong>{direction.structure.join(' → ')}</Typography.Paragraph>
      <Typography.Paragraph><strong>Hook：</strong>{direction.hook_direction}</Typography.Paragraph>
    </section>
  )
}
