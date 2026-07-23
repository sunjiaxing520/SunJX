import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Popconfirm,
  Segmented,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import { Eye, Play, RefreshCw, Star, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import {
  deleteAnalysisTask,
  deleteAnalysisTasks,
  getAnalysisTask,
  listAnalysisTasks,
  runAnalysis,
} from '../api/analysis'
import { createFavorite, deleteFavorite, listFavorites } from '../api/favorites'
import { listRankingEntries } from '../api/rankings'
import { ApiUsageCell, ApiUsageDetails } from '../components/ApiUsageDetails'
import { CollapsibleList } from '../components/CollapsibleList'
import { totalTaskTokens } from '../lib/apiUsage'
import { errorMessage } from '../lib/errors'
import type { AnalysisTask, CreationDirection, FavoriteItem, RankingEntry } from '../types/api'

const TEMPO_LABELS = { slow: '慢速', medium: '适中', fast: '快速' }
const GENDER_LABELS = { male: '男声', female: '女声', unspecified: '不限' }

export function AnalysisPage() {
  const { message } = App.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const openedSourceTaskRef = useRef<number | null>(null)
  const [entries, setEntries] = useState<RankingEntry[]>([])
  const [tasks, setTasks] = useState<AnalysisTask[]>([])
  const [selectedIds, setSelectedIds] = useState<React.Key[]>([])
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([])
  const [deletingTaskIds, setDeletingTaskIds] = useState<number[]>([])
  const [windowDays, setWindowDays] = useState(7)
  const [activeTask, setActiveTask] = useState<AnalysisTask | null>(null)
  const [favorites, setFavorites] = useState<FavoriteItem[]>([])
  const [favoriteTargetId, setFavoriteTargetId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updateTaskHistory = useCallback((items: AnalysisTask[]) => {
    setTasks(items)
    setActiveTask((current) => current
      ? items.find((item) => item.id === current.id) ?? current
      : null)
  }, [])

  const load = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true)
      setError(null)
    }
    try {
      const [ranking, history, favoriteHistory] = await Promise.all([
        listRankingEntries({ pageSize: 100 }),
        listAnalysisTasks(),
        listFavorites('analysis'),
      ])
      setEntries(ranking.items)
      updateTaskHistory(history.items)
      setFavorites(favoriteHistory.items)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      if (!silent) setLoading(false)
    }
  }, [updateTaskHistory])

  useEffect(() => {
    void load()
  }, [load])

  const hasActiveTask = tasks.some(
    (task) => task.status === 'pending' || task.status === 'running',
  )

  useEffect(() => {
    if (!hasActiveTask) return
    const timer = window.setInterval(async () => {
      try {
        const history = await listAnalysisTasks()
        updateTaskHistory(history.items)
      } catch (pollError) {
        setError(errorMessage(pollError))
      }
    }, 2500)
    return () => window.clearInterval(timer)
  }, [hasActiveTask, updateTaskHistory])

  useEffect(() => {
    const requestedTaskId = Number(searchParams.get('task_id'))
    if (!requestedTaskId) {
      openedSourceTaskRef.current = null
      return
    }
    if (loading || openedSourceTaskRef.current === requestedTaskId) return
    openedSourceTaskRef.current = requestedTaskId
    const requestedTask = tasks.find((task) => task.id === requestedTaskId)
    if (requestedTask) {
      setActiveTask(requestedTask)
      return
    }
    void getAnalysisTask(requestedTaskId)
      .then(setActiveTask)
      .catch((sourceError) => message.error(errorMessage(sourceError)))
  }, [loading, message, searchParams, tasks])

  const favoritesByTarget = useMemo(
    () => new Map(favorites.map((favorite) => [favorite.target_id, favorite])),
    [favorites],
  )

  const toggleFavorite = async (task: AnalysisTask) => {
    if (!task.report) return
    const existing = favoritesByTarget.get(task.report.id)
    setFavoriteTargetId(task.report.id)
    try {
      if (existing) {
        await deleteFavorite(existing.id)
        setFavorites((items) => items.filter((item) => item.id !== existing.id))
        message.success('已从收藏夹移除')
      } else {
        const created = await createFavorite('analysis', task.report.id)
        setFavorites((items) => [created, ...items.filter((item) => item.id !== created.id)])
        message.success('分析报告已加入收藏夹')
      }
    } catch (favoriteError) {
      message.error(errorMessage(favoriteError))
    } finally {
      setFavoriteTargetId(null)
    }
  }

  const closeDrawer = () => {
    setActiveTask(null)
    openedSourceTaskRef.current = null
    if (searchParams.has('task_id')) {
      const next = new URLSearchParams(searchParams)
      next.delete('task_id')
      setSearchParams(next, { replace: true })
    }
  }

  const removeTasks = async (taskIds: number[]) => {
    const uniqueIds = [...new Set(taskIds)]
    if (!uniqueIds.length) return
    setDeletingTaskIds(uniqueIds)
    try {
      if (uniqueIds.length === 1) {
        await deleteAnalysisTask(uniqueIds[0])
      } else {
        await deleteAnalysisTasks(uniqueIds)
      }
      if (activeTask && uniqueIds.includes(activeTask.id)) closeDrawer()
      setSelectedTaskIds((current) => current.filter((id) => !uniqueIds.includes(id)))
      message.success(uniqueIds.length === 1 ? '分析记录已删除' : `已删除 ${uniqueIds.length} 条分析记录`)
      await load()
    } catch (deleteError) {
      message.error(errorMessage(deleteError))
    } finally {
      setDeletingTaskIds([])
    }
  }

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
      width: 132,
      render: (_, task) => {
        const isActive = task.status === 'pending' || task.status === 'running'
        return (
          <Space size={0}>
            {task.report && (
              <Tooltip title={favoritesByTarget.has(task.report.id) ? '取消收藏' : '收藏报告'}>
                <Button
                  type="text"
                  className={favoritesByTarget.has(task.report.id) ? 'favorite-button-active' : undefined}
                  icon={<Star size={16} fill={favoritesByTarget.has(task.report.id) ? 'currentColor' : 'none'} />}
                  loading={favoriteTargetId === task.report.id}
                  aria-label={favoritesByTarget.has(task.report.id) ? '取消收藏分析报告' : '收藏分析报告'}
                  onClick={() => void toggleFavorite(task)}
                />
              </Tooltip>
            )}
            <Button type="text" icon={<Eye size={16} />} aria-label="查看分析报告" onClick={() => setActiveTask(task)} />
            <Popconfirm
              title="删除这条分析记录？"
              description="分析报告和对应收藏会一并删除，且无法恢复。"
              okText="删除"
              cancelText="取消"
              disabled={isActive}
              onConfirm={() => void removeTasks([task.id])}
            >
              <Tooltip title={isActive ? '运行中的任务不能删除' : '删除产出'}>
                <Button
                  type="text"
                  danger
                  icon={<Trash2 size={16} />}
                  loading={deletingTaskIds.includes(task.id)}
                  disabled={isActive}
                  aria-label={`删除分析任务 ${task.id}`}
                />
              </Tooltip>
            </Popconfirm>
          </Space>
        )
      },
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
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void load()}>刷新</Button>
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
            <Button
              type="primary"
              icon={<Play size={16} />}
              loading={running || hasActiveTask}
              disabled={!entries.length || hasActiveTask}
              onClick={submit}
            >
              {hasActiveTask
                ? '分析任务运行中'
                : selectedIds.length
                  ? `分析所选 ${selectedIds.length} 首`
                  : '分析最新前 30 首'}
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
            <Typography.Text type="secondary">最近 15 次分析及结构化报告，默认显示最新 5 条</Typography.Text>
          </div>
          {selectedTaskIds.length > 0 && (
            <Popconfirm
              title={`删除所选 ${selectedTaskIds.length} 条记录？`}
              description="所选分析报告和对应收藏会一并删除，且无法恢复。"
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
            <Table<AnalysisTask>
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
              scroll={{ x: 800 }}
              className="data-table"
            />
          )}
        </CollapsibleList>
      </section>

      <Drawer
        title={`分析报告${activeTask ? ` #${activeTask.id}` : ''}`}
        open={Boolean(activeTask)}
        onClose={closeDrawer}
        size="large"
        extra={activeTask?.report ? (
          <Button
            icon={<Star size={16} fill={favoritesByTarget.has(activeTask.report.id) ? 'currentColor' : 'none'} />}
            className={favoritesByTarget.has(activeTask.report.id) ? 'favorite-button-active' : undefined}
            loading={favoriteTargetId === activeTask.report.id}
            onClick={() => void toggleFavorite(activeTask)}
          >
            {favoritesByTarget.has(activeTask.report.id) ? '已收藏' : '收藏报告'}
          </Button>
        ) : null}
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
