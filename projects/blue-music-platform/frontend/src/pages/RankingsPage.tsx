import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Collapse,
  Dropdown,
  Empty,
  Input,
  Skeleton,
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
  const [activeSnapshotId, setActiveSnapshotId] = useState<number | null>(null)
  const [entries, setEntries] = useState<RankingEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const detailRequestId = useRef(0)

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
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadEntries = useCallback(async () => {
    if (!activeSnapshotId) return

    const requestId = ++detailRequestId.current
    setDetailLoading(true)
    setDetailError(null)
    try {
      const result = await listRankingEntries({
        snapshotId: activeSnapshotId,
        page,
        pageSize: 20,
        search,
      })
      if (requestId !== detailRequestId.current) return
      setEntries(result.items)
      setTotal(result.total)
    } catch (loadError) {
      if (requestId !== detailRequestId.current) return
      setDetailError(errorMessage(loadError))
      setEntries([])
      setTotal(0)
    } finally {
      if (requestId === detailRequestId.current) setDetailLoading(false)
    }
  }, [activeSnapshotId, page, search])

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
      await loadOverview()
    } catch (runError) {
      message.error(errorMessage(runError))
      await loadOverview()
    } finally {
      setRunning(false)
    }
  }

  const changeSnapshot = (snapshotId: number | null) => {
    if (snapshotId === activeSnapshotId) return

    detailRequestId.current += 1
    setActiveSnapshotId(snapshotId)
    setDetailLoading(false)
    setEntries([])
    setTotal(0)
    setPage(1)
    setSearch('')
    setDetailError(null)
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
            <Typography.Title level={2}>采集结果</Typography.Title>
            <Typography.Text type="secondary">数据库保留 30 天，列表展示最近 15 个每日快照</Typography.Text>
          </div>
          <Tooltip title="刷新采集结果">
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={loadOverview} />
          </Tooltip>
        </div>
        {loading ? (
          <div className="ranking-snapshot-loading">
            <Skeleton active title={false} paragraph={{ rows: 3 }} />
          </div>
        ) : snapshots.length === 0 ? (
          <div className="ranking-snapshot-empty">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无采集结果" />
          </div>
        ) : (
          <Collapse
            accordion
            destroyOnHidden
            activeKey={activeSnapshotId === null ? [] : [String(activeSnapshotId)]}
            expandIconPlacement="end"
            className="ranking-snapshot-list"
            onChange={(keys) => changeSnapshot(keys[0] ? Number(keys[0]) : null)}
            items={snapshots.map((snapshot) => ({
              key: String(snapshot.id),
              label: (
                <div className="ranking-snapshot-summary">
                  <div className="ranking-snapshot-primary">
                    <strong>{snapshot.snapshot_date}</strong>
                    <span>{snapshot.chart_name}</span>
                  </div>
                  <div className="ranking-snapshot-facts">
                    <span>
                      <small>歌曲</small>
                      <strong>{snapshot.item_count} 首</strong>
                    </span>
                    <span>
                      <small>来源更新</small>
                      <strong>{snapshot.source_updated_date ?? '未提供'}</strong>
                    </span>
                    <span>
                      <small>采集完成</small>
                      <strong>{formatTime(snapshot.collected_at)}</strong>
                    </span>
                  </div>
                </div>
              ),
              children: (
                <div className="ranking-detail-stack">
                  <div className="ranking-detail-toolbar">
                    <Typography.Text type="secondary">
                      当前快照共 {snapshot.item_count} 首，展开时加载歌曲详情
                    </Typography.Text>
                    <Input.Search
                      allowClear
                      className="ranking-detail-search"
                      placeholder="搜索歌曲或歌手"
                      onSearch={(value) => {
                        setSearch(value.trim())
                        setPage(1)
                      }}
                    />
                  </div>
                  {detailError && (
                    <Alert
                      type="error"
                      showIcon
                      title={detailError}
                      action={<Button size="small" onClick={() => void loadEntries()}>重新加载</Button>}
                    />
                  )}
                  <Table<RankingEntry>
                    rowKey="id"
                    columns={entryColumns}
                    dataSource={entries}
                    loading={detailLoading}
                    locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无榜单数据" /> }}
                    pagination={{
                      current: page,
                      pageSize: 20,
                      total,
                      showSizeChanger: false,
                      showTotal: (value) => `共 ${value} 首`,
                      onChange: setPage,
                    }}
                    scroll={{ x: 640 }}
                    className="data-table ranking-entry-table"
                  />
                </div>
              ),
            }))}
          />
        )}
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>运行记录</Typography.Title>
            <Typography.Text type="secondary">最近 15 次执行状态，失败原因会保留在记录中</Typography.Text>
          </div>
        </div>
        <Table<CollectionTask>
          rowKey="id"
          columns={taskColumns}
          dataSource={tasks}
          loading={loading}
          pagination={false}
          scroll={{ x: 790 }}
          className="data-table"
        />
      </section>

    </div>
  )
}
