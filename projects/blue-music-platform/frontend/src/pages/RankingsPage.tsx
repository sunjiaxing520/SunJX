import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Collapse,
  Dropdown,
  Empty,
  Input,
  Popconfirm,
  Skeleton,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  type MenuProps,
  type TableProps,
} from 'antd'
import { ChevronDown, ExternalLink, Play, RefreshCw, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import {
  deleteCollectionTask,
  deleteCollectionTasks,
  listCollectionTasks,
  listRankingEntries,
  listRankingSnapshots,
  runRankingCollection,
} from '../api/rankings'
import { useAuth } from '../auth/useAuth'
import { CollapsibleList } from '../components/CollapsibleList'
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
  paused: { label: '已暂停', color: 'warning' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
}

const MEMBER_CHART_CODES = ['8888', '6666'] as const

function latestChartSnapshots(snapshots: RankingSnapshot[]) {
  return MEMBER_CHART_CODES
    .map((chartCode) => snapshots.find((snapshot) => snapshot.chart_code === chartCode))
    .filter((snapshot): snapshot is RankingSnapshot => Boolean(snapshot))
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
  const { user } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'super_admin'
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
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([])
  const [deletingTaskIds, setDeletingTaskIds] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [overviewRevision, setOverviewRevision] = useState(0)
  const detailRequestId = useRef(0)

  const loadOverview = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const [taskItems, snapshotItems] = isAdmin
        ? await Promise.all([listCollectionTasks(), listRankingSnapshots(15)])
        : [[], await listRankingSnapshots(30)]
      const latestSnapshots = latestChartSnapshots(snapshotItems)

      setTasks(taskItems)
      setSnapshots(snapshotItems)
      if (!isAdmin) {
        setActiveSnapshotId((current) => (
          latestSnapshots.some((snapshot) => snapshot.id === current)
            ? current
            : latestSnapshots[0]?.id ?? null
        ))
      }
      setOverviewRevision((current) => current + 1)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [isAdmin])

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
  }, [loadEntries, overviewRevision])

  useEffect(() => {
    if (isAdmin) return undefined
    const refreshTimer = window.setInterval(() => {
      void loadOverview(false)
    }, 15_000)
    return () => window.clearInterval(refreshTimer)
  }, [isAdmin, loadOverview])

  const run = async (
    sourceMode: 'live' | 'sample',
    chart: 'top500' | 'rising' = 'top500',
  ) => {
    setRunning(true)
    try {
      const task = await runRankingCollection(
        sourceMode,
        chart === 'rising' ? 20 : 100,
        chart,
      )
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

  const removeTasks = async (taskIds: number[]) => {
    const uniqueIds = [...new Set(taskIds)]
    if (!uniqueIds.length) return
    setDeletingTaskIds(uniqueIds)
    try {
      if (uniqueIds.length === 1) {
        await deleteCollectionTask(uniqueIds[0])
      } else {
        await deleteCollectionTasks(uniqueIds)
      }
      setSelectedTaskIds((current) => current.filter((id) => !uniqueIds.includes(id)))
      message.success(uniqueIds.length === 1 ? '采集运行记录已删除' : `已删除 ${uniqueIds.length} 条采集运行记录`)
      await loadOverview()
    } catch (deleteError) {
      message.error(errorMessage(deleteError))
    } finally {
      setDeletingTaskIds([])
    }
  }

  const fallbackMenu: MenuProps = {
    items: [
      { key: 'sample-top500', label: '载入 TOP500 固定样例' },
      { key: 'sample-rising', label: '载入飙升榜固定样例' },
    ],
    onClick: ({ key }) => void run('sample', key === 'sample-rising' ? 'rising' : 'top500'),
  }

  const visibleSnapshots = useMemo(
    () => (isAdmin ? snapshots : latestChartSnapshots(snapshots)),
    [isAdmin, snapshots],
  )
  const activeSnapshot = snapshots.find((snapshot) => snapshot.id === activeSnapshotId) ?? null
  const canAnalyzeIndividualSong = activeSnapshot?.chart_code === '6666'

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
    ...(canAnalyzeIndividualSong ? [{
      title: '',
      key: 'analysis',
      width: 108,
      fixed: 'right' as const,
      render: (_: unknown, entry: RankingEntry) => (
        <Button
          type="link"
          size="small"
          onClick={() => navigate(`/analysis?snapshot_id=${entry.snapshot_id}&entry_id=${entry.id}&chart=rising`)}
        >
          分析单曲
        </Button>
      ),
    }] : []),
  ]

  const taskColumns: TableProps<CollectionTask>['columns'] = [
    { title: '任务', dataIndex: 'id', width: 78, render: (id: number) => `#${id}` },
    { title: '榜单', dataIndex: 'chart_name', width: 130 },
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
    {
      title: '',
      key: 'actions',
      width: 58,
      fixed: 'right',
      render: (_, task) => {
        const isActive = task.status === 'pending' || task.status === 'running'
        return (
          <Popconfirm
            title="删除这条运行记录？"
            description="只删除本次执行记录，每日榜单快照仍会保留。"
            okText="删除"
            cancelText="取消"
            disabled={isActive}
            onConfirm={() => void removeTasks([task.id])}
          >
            <Tooltip title={isActive ? '运行中的任务不能删除' : '删除运行记录'}>
              <Button
                type="text"
                danger
                icon={<Trash2 size={16} />}
                loading={deletingTaskIds.includes(task.id)}
                disabled={isActive}
                aria-label={`删除采集任务 ${task.id}`}
              />
            </Tooltip>
          </Popconfirm>
        )
      },
    },
  ]

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>{isAdmin ? '榜单管理' : '榜单数据'}</Typography.Title>
          <Typography.Text type="secondary">
            {isAdmin
              ? '酷狗 TOP500 趋势数据与飙升榜单曲分析'
              : '查看管理员更新的酷狗 TOP500 与飙升榜最新结果'}
          </Typography.Text>
        </div>
        {isAdmin && (
          <Space.Compact>
            <Button
              type="primary"
              icon={<Play size={16} />}
              loading={running}
              onClick={() => void run('live', 'top500')}
            >
              采集 TOP500
            </Button>
            <Button
              icon={<Play size={16} />}
              loading={running}
              onClick={() => void run('live', 'rising')}
            >
              采集飙升榜前 20
            </Button>
            <Dropdown menu={fallbackMenu} disabled={running}>
              <Button icon={<ChevronDown size={16} />} aria-label="采集选项" />
            </Dropdown>
          </Space.Compact>
        )}
      </div>

      {error && <Alert type="error" showIcon title={error} closable />}

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>{isAdmin ? '采集结果' : '最新榜单'}</Typography.Title>
            <Typography.Text type="secondary">
              {isAdmin
                ? '每个榜单每天保留一份；当天再次采集会覆盖同榜单快照并更新采集完成时间'
                : '页面每 15 秒同步一次；最后更新时间以管理员最近一次采集完成时间为准'}
            </Typography.Text>
          </div>
          <Tooltip title="刷新采集结果">
            <Button
              icon={<RefreshCw size={16} />}
              loading={loading}
              onClick={() => void loadOverview()}
            />
          </Tooltip>
        </div>
        {loading ? (
          <div className="ranking-snapshot-loading">
            <Skeleton active title={false} paragraph={{ rows: 3 }} />
          </div>
        ) : visibleSnapshots.length === 0 ? (
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
            items={visibleSnapshots.map((snapshot) => ({
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
                      {snapshot.chart_code === '6666'
                        ? '飙升榜可直接选择任意歌曲进入内容分析'
                        : `当前快照共 ${snapshot.item_count} 首，展开时加载歌曲详情`}
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

      {isAdmin && (
        <section className="content-section">
          <div className="section-title-row">
            <div>
              <Typography.Title level={2}>运行记录</Typography.Title>
              <Typography.Text type="secondary">最近 15 次执行状态，默认显示最新 5 条</Typography.Text>
            </div>
            {selectedTaskIds.length > 0 && (
              <Popconfirm
                title={`删除所选 ${selectedTaskIds.length} 条运行记录？`}
                description="只删除执行记录，每日榜单快照仍会保留。"
                okText="批量删除"
                cancelText="取消"
                onConfirm={() => void removeTasks(selectedTaskIds)}
              >
                <Button
                  danger
                  icon={<Trash2 size={16} />}
                  loading={selectedTaskIds.every((id) => deletingTaskIds.includes(id))}
                >
                  删除所选 ({selectedTaskIds.length})
                </Button>
              </Popconfirm>
            )}
          </div>
          <CollapsibleList items={tasks}>
            {(visibleTasks) => (
              <Table<CollectionTask>
                rowKey="id"
                columns={taskColumns}
                dataSource={visibleTasks}
                loading={loading}
                pagination={false}
                rowSelection={{
                  selectedRowKeys: selectedTaskIds,
                  onChange: (keys) => setSelectedTaskIds(keys.map(Number)),
                  getCheckboxProps: (task) => ({
                    disabled: task.status === 'pending' || task.status === 'running',
                  }),
                }}
                scroll={{ x: 850 }}
                className="data-table"
              />
            )}
          </CollapsibleList>
        </section>
      )}

    </div>
  )
}
