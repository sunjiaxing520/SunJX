import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Dropdown,
  Empty,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  type MenuProps,
  type TableProps,
} from 'antd'
import { ChevronDown, ExternalLink, Play, RefreshCw } from 'lucide-react'

import {
  listCollectionTasks,
  listRankingEntries,
  listRankingSnapshots,
  runRankingCollection,
} from '../api/rankings'
import { errorMessage } from '../lib/errors'
import type {
  CollectionTask,
  RankingEntry,
  RankingSnapshot,
  WorkflowTaskStatus,
} from '../types/api'

const STATUS_LABELS: Record<WorkflowTaskStatus, { label: string; color?: string }> = {
  pending: { label: '等待中' },
  running: { label: '运行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return '-'
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function RankingsPage() {
  const { message } = App.useApp()
  const [tasks, setTasks] = useState<CollectionTask[]>([])
  const [snapshots, setSnapshots] = useState<RankingSnapshot[]>([])
  const [entries, setEntries] = useState<RankingEntry[]>([])
  const [total, setTotal] = useState(0)
  const [snapshotId, setSnapshotId] = useState<number>()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [taskItems, snapshotItems] = await Promise.all([
        listCollectionTasks(),
        listRankingSnapshots(),
      ])
      setTasks(taskItems)
      setSnapshots(snapshotItems)
      setSnapshotId((current) =>
        current && snapshotItems.some((item) => item.id === current)
          ? current
          : snapshotItems[0]?.id,
      )
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadEntries = useCallback(async () => {
    if (!snapshotId) {
      setEntries([])
      setTotal(0)
      return
    }
    try {
      const result = await listRankingEntries({
        snapshotId,
        page,
        pageSize: 50,
        search,
      })
      setEntries(result.items)
      setTotal(result.total)
    } catch (loadError) {
      setError(errorMessage(loadError))
    }
  }, [page, search, snapshotId])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  useEffect(() => {
    void loadEntries()
  }, [loadEntries])

  const run = async (sourceMode: 'live' | 'sample') => {
    setRunning(true)
    try {
      const task = await runRankingCollection(sourceMode)
      message.success(`采集完成，共保存 ${task.item_count} 首`)
      setPage(1)
      await loadOverview()
    } catch (runError) {
      message.error(errorMessage(runError))
      await loadOverview()
    } finally {
      setRunning(false)
    }
  }

  const fallbackMenu: MenuProps = {
    items: [{ key: 'sample', label: '载入固定样例' }],
    onClick: () => void run('sample'),
  }

  const entryColumns: TableProps<RankingEntry>['columns'] = [
    { title: '排名', dataIndex: 'rank', width: 74, fixed: 'left' },
    {
      title: '歌曲',
      dataIndex: 'title',
      render: (title: string, entry) => (
        <div className="account-cell">
          <strong>{title}</strong>
          <small>{entry.artist}</small>
        </div>
      ),
    },
    {
      title: '时长',
      dataIndex: 'duration_seconds',
      width: 90,
      render: formatDuration,
    },
    {
      title: '热度',
      dataIndex: 'popularity',
      width: 100,
      render: (value: number | null) => value?.toLocaleString() ?? '-',
    },
    {
      title: '',
      key: 'source',
      width: 58,
      fixed: 'right',
      render: (_, entry) => entry.source_url && (
        <Tooltip title="打开酷狗歌曲页">
          <Button
            type="text"
            icon={<ExternalLink size={16} />}
            aria-label="打开酷狗歌曲页"
            href={entry.source_url}
            target="_blank"
          />
        </Tooltip>
      ),
    },
  ]

  const taskColumns: TableProps<CollectionTask>['columns'] = [
    { title: '任务', dataIndex: 'id', width: 78, render: (id: number) => `#${id}` },
    { title: '榜单日期', dataIndex: 'snapshot_date', width: 120 },
    {
      title: '来源',
      dataIndex: 'source_mode',
      width: 110,
      render: (mode: CollectionTask['source_mode']) =>
        mode === 'live' ? '实时榜单' : '固定样例',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: WorkflowTaskStatus) => (
        <Tag color={STATUS_LABELS[status].color}>{STATUS_LABELS[status].label}</Tag>
      ),
    },
    { title: '歌曲数', dataIndex: 'item_count', width: 90 },
    {
      title: '运行时间',
      dataIndex: 'created_at',
      width: 190,
      render: formatTime,
    },
    {
      title: '结果',
      key: 'result',
      render: (_, task) => task.error_message ?? (task.status === 'completed' ? '快照已保存' : '-'),
    },
  ]

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>榜单采集</Typography.Title>
          <Typography.Text type="secondary">酷狗 TOP500 每日快照与运行记录</Typography.Text>
        </div>
        <Space.Compact>
          <Button
            type="primary"
            icon={<Play size={16} />}
            loading={running}
            onClick={() => void run('live')}
          >
            采集实时榜单
          </Button>
          <Dropdown menu={fallbackMenu} disabled={running}>
            <Button icon={<ChevronDown size={16} />} aria-label="采集选项" />
          </Dropdown>
        </Space.Compact>
      </div>

      {error && <Alert type="error" showIcon title={error} closable />}

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>榜单数据</Typography.Title>
            <Typography.Text type="secondary">数据库保留 30 天，当前显示所选日期</Typography.Text>
          </div>
          <Space wrap>
            <Select
              value={snapshotId}
              placeholder="暂无榜单日期"
              style={{ width: 178 }}
              options={snapshots.map((snapshot) => ({
                value: snapshot.id,
                label: `${snapshot.snapshot_date} · ${snapshot.item_count} 首`,
              }))}
              onChange={(value) => {
                setSnapshotId(value)
                setPage(1)
              }}
            />
            <Input.Search
              allowClear
              placeholder="搜索歌曲或歌手"
              style={{ width: 220 }}
              onSearch={(value) => {
                setSearch(value.trim())
                setPage(1)
              }}
            />
          </Space>
        </div>
        <Table<RankingEntry>
          rowKey="id"
          columns={entryColumns}
          dataSource={entries}
          loading={loading}
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无榜单数据" /> }}
          pagination={{ current: page, pageSize: 50, total, showSizeChanger: false, onChange: setPage }}
          scroll={{ x: 720 }}
          className="data-table"
        />
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>最近运行</Typography.Title>
            <Typography.Text type="secondary">最多展示 15 条，失败原因保留在记录中</Typography.Text>
          </div>
          <Tooltip title="刷新运行记录">
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={loadOverview} />
          </Tooltip>
        </div>
        <Table<CollectionTask>
          rowKey="id"
          columns={taskColumns}
          dataSource={tasks}
          loading={loading}
          pagination={false}
          scroll={{ x: 850 }}
          className="data-table"
        />
      </section>
    </div>
  )
}
