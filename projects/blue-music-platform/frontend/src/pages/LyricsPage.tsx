import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import { BookmarkCheck, Copy, Eye, RefreshCw, RotateCw, Sparkles, Star, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { listAnalysisTasks } from '../api/analysis'
import { createFavorite, deleteFavorite, listFavorites } from '../api/favorites'
import { ApiUsageCell, ApiUsageDetails } from '../components/ApiUsageDetails'
import { CollapsibleList } from '../components/CollapsibleList'
import { totalTaskTokens } from '../lib/apiUsage'
import {
  deleteLyricsTask,
  deleteLyricsTasks,
  generateLyrics,
  getLyricsTask,
  listLyricsTasks,
  regenerateLyrics,
  saveLyricsVersion,
} from '../api/lyrics'
import { errorMessage } from '../lib/errors'
import type {
  AnalysisTask,
  FavoriteItem,
  LyricsCreatePayload,
  LyricsTask,
  LyricsVersion,
} from '../types/api'

interface LyricsFormValues {
  analysis_direction?: string
  title_hint?: string
  theme: string
  genre_tags?: string[]
  mood_tags?: string[]
  scene_tags?: string[]
  keywords?: string[]
  tempo?: 'slow' | 'medium' | 'fast'
  vocal_gender?: 'male' | 'female' | 'unspecified'
  vocal_style?: string
  requirements?: string
}

export function LyricsPage() {
  const { message } = App.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const openedSourceKeyRef = useRef<string | null>(null)
  const [form] = Form.useForm<LyricsFormValues>()
  const [analysisTasks, setAnalysisTasks] = useState<AnalysisTask[]>([])
  const [tasks, setTasks] = useState<LyricsTask[]>([])
  const [activeTask, setActiveTask] = useState<LyricsTask | null>(null)
  const [activeVersionId, setActiveVersionId] = useState<number | null>(null)
  const [favorites, setFavorites] = useState<FavoriteItem[]>([])
  const [favoriteTargetId, setFavoriteTargetId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([])
  const [deletingTaskIds, setDeletingTaskIds] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [analyses, lyrics, favoriteHistory] = await Promise.all([
        listAnalysisTasks(),
        listLyricsTasks(),
        listFavorites('lyrics'),
      ])
      setAnalysisTasks(analyses.items)
      setTasks(lyrics.items)
      setFavorites(favoriteHistory.items)
      setActiveTask((current) => current ? lyrics.items.find((item) => item.id === current.id) ?? current : null)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const requestedTaskId = Number(searchParams.get('task_id'))
    if (!requestedTaskId) {
      openedSourceKeyRef.current = null
      return
    }
    const requestedVersionValue = searchParams.get('version_id')
    const sourceKey = `${requestedTaskId}:${requestedVersionValue ?? ''}`
    if (loading || openedSourceKeyRef.current === sourceKey) return
    openedSourceKeyRef.current = sourceKey
    const openRequestedTask = (requestedTask: LyricsTask) => {
      const requestedVersionId = Number(requestedVersionValue)
      const requestedVersion = requestedTask.versions.find((version) => version.id === requestedVersionId)
      setActiveTask(requestedTask)
      setActiveVersionId(requestedVersion?.id ?? requestedTask.versions.at(-1)?.id ?? null)
    }
    const requestedTask = tasks.find((task) => task.id === requestedTaskId)
    if (requestedTask) {
      openRequestedTask(requestedTask)
      return
    }
    void getLyricsTask(requestedTaskId)
      .then(openRequestedTask)
      .catch((sourceError) => message.error(errorMessage(sourceError)))
  }, [loading, message, searchParams, tasks])

  const favoritesByTarget = useMemo(
    () => new Map(favorites.map((favorite) => [favorite.target_id, favorite])),
    [favorites],
  )

  const toggleFavorite = async (version: LyricsVersion) => {
    const existing = favoritesByTarget.get(version.id)
    setFavoriteTargetId(version.id)
    try {
      if (existing) {
        await deleteFavorite(existing.id)
        setFavorites((items) => items.filter((item) => item.id !== existing.id))
        message.success('已从收藏夹移除')
      } else {
        const created = await createFavorite('lyrics', version.id)
        setFavorites((items) => [created, ...items.filter((item) => item.id !== created.id)])
        message.success(`第 ${version.version_number} 版歌词已加入收藏夹`)
      }
    } catch (favoriteError) {
      message.error(errorMessage(favoriteError))
    } finally {
      setFavoriteTargetId(null)
    }
  }

  const openTask = (task: LyricsTask) => {
    setActiveTask(task)
    setActiveVersionId(task.versions.at(-1)?.id ?? null)
  }

  const closeDrawer = () => {
    setActiveTask(null)
    setActiveVersionId(null)
    openedSourceKeyRef.current = null
    if (searchParams.has('task_id') || searchParams.has('version_id')) {
      const next = new URLSearchParams(searchParams)
      next.delete('task_id')
      next.delete('version_id')
      setSearchParams(next, { replace: true })
    }
  }

  const removeTasks = async (taskIds: number[]) => {
    const uniqueIds = [...new Set(taskIds)]
    if (!uniqueIds.length) return
    setDeletingTaskIds(uniqueIds)
    try {
      if (uniqueIds.length === 1) {
        await deleteLyricsTask(uniqueIds[0])
      } else {
        await deleteLyricsTasks(uniqueIds)
      }
      if (activeTask && uniqueIds.includes(activeTask.id)) closeDrawer()
      setSelectedTaskIds((current) => current.filter((id) => !uniqueIds.includes(id)))
      message.success(uniqueIds.length === 1 ? '作词记录已删除' : `已删除 ${uniqueIds.length} 条作词记录`)
      await load()
    } catch (deleteError) {
      message.error(errorMessage(deleteError))
    } finally {
      setDeletingTaskIds([])
    }
  }

  const directions = useMemo(() => analysisTasks.flatMap((task) =>
    (task.report?.creation_directions ?? []).map((direction, index) => ({
      task,
      direction,
      index,
      value: `${task.report?.id}:${index}`,
    }))), [analysisTasks])

  const chooseDirection = (value?: string) => {
    if (!value) return
    const selected = directions.find((item) => item.value === value)
    if (!selected) return
    const direction = selected.direction
    form.setFieldsValue({
      genre_tags: direction.genre_tags,
      mood_tags: direction.mood_tags,
      scene_tags: direction.scene_tags,
      keywords: direction.theme_keywords,
      tempo: direction.tempo,
      vocal_gender: direction.vocal_gender,
      vocal_style: direction.vocal_style,
    })
  }

  const submit = async () => {
    const values = await form.validateFields()
    const [reportId, directionIndex] = values.analysis_direction?.split(':').map(Number) ?? []
    const payload: LyricsCreatePayload = {
      ...values,
      analysis_report_id: Number.isFinite(reportId) ? reportId : undefined,
      direction_index: Number.isFinite(directionIndex) ? directionIndex : undefined,
    }
    delete (payload as LyricsCreatePayload & { analysis_direction?: string }).analysis_direction
    setGenerating(true)
    try {
      const task = await generateLyrics(payload)
      message.success('歌词已经生成')
      form.resetFields()
      setActiveTask(task)
      setActiveVersionId(task.versions.at(-1)?.id ?? null)
      await load()
    } catch (generateError) {
      message.error(errorMessage(generateError))
      await load()
    } finally {
      setGenerating(false)
    }
  }

  const regenerate = async () => {
    if (!activeTask) return
    setRegenerating(true)
    try {
      const updated = await regenerateLyrics(activeTask.id)
      setActiveTask(updated)
      setActiveVersionId(updated.versions.at(-1)?.id ?? null)
      message.success(`已生成第 ${updated.versions.length} 版歌词`)
      await load()
    } catch (regenerateError) {
      message.error(errorMessage(regenerateError))
    } finally {
      setRegenerating(false)
    }
  }

  const save = async (version: LyricsVersion) => {
    setSavingId(version.id)
    try {
      await saveLyricsVersion(version.id)
      message.success('该歌词版本已保存')
      await load()
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSavingId(null)
    }
  }

  const columns: TableProps<LyricsTask>['columns'] = [
    { title: '任务', dataIndex: 'id', width: 78, render: (id: number) => `#${id}` },
    {
      title: '主题',
      dataIndex: 'theme',
      render: (theme: string, task) => (
        <div className="account-cell"><strong>{theme}</strong><small>{task.genre_tags.join(' · ') || '未指定曲风'}</small></div>
      ),
    },
    { title: '版本', key: 'versions', width: 90, render: (_, task) => task.versions.length },
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
      render: (status: LyricsTask['status']) => <Tag color={status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'processing'}>{status === 'completed' ? '已完成' : status === 'failed' ? '失败' : '运行中'}</Tag>,
    },
    {
      title: '',
      key: 'detail',
      width: 132,
      render: (_, task) => {
        const latestVersion = task.versions.at(-1)
        const isFavorite = latestVersion ? favoritesByTarget.has(latestVersion.id) : false
        const isActive = task.status === 'pending' || task.status === 'running'
        return (
          <Space size={0}>
            {latestVersion && (
              <Tooltip title={isFavorite ? '取消收藏最新版本' : '收藏最新版本'}>
                <Button
                  type="text"
                  className={isFavorite ? 'favorite-button-active' : undefined}
                  icon={<Star size={16} fill={isFavorite ? 'currentColor' : 'none'} />}
                  loading={favoriteTargetId === latestVersion.id}
                  aria-label={isFavorite ? '取消收藏最新歌词版本' : '收藏最新歌词版本'}
                  onClick={() => void toggleFavorite(latestVersion)}
                />
              </Tooltip>
            )}
            <Button type="text" icon={<Eye size={16} />} aria-label="查看歌词" onClick={() => openTask(task)} />
            <Popconfirm
              title="删除这条作词记录？"
              description="任务下的全部歌词版本和收藏会一并删除，且无法恢复。"
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
                  aria-label={`删除作词任务 ${task.id}`}
                />
              </Tooltip>
            </Popconfirm>
          </Space>
        )
      },
    },
  ]

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>歌词创作</Typography.Title>
          <Typography.Text type="secondary">从分析方向或自定义要求生成结构化原创歌词</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>刷新</Button>
      </div>

      {error && <Alert type="error" showIcon title={error} />}

      <section className="content-section lyrics-form-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>新建作词任务</Typography.Title>
            <Typography.Text type="secondary">选择分析方向后会自动带入曲风、情绪和人声建议</Typography.Text>
          </div>
        </div>
        <Form form={form} layout="vertical" requiredMark={false} initialValues={{ tempo: 'medium', vocal_gender: 'unspecified' }}>
          <div className="form-grid">
            <Form.Item name="analysis_direction" label="引用分析方向">
              <Select
                allowClear
                placeholder="可选"
                options={directions.map((item) => ({
                  value: item.value,
                  label: `报告 #${item.task.report?.id} · ${item.direction.name}`,
                }))}
                onChange={chooseDirection}
              />
            </Form.Item>
            <Form.Item name="title_hint" label="歌名方向">
              <Input placeholder="可留空自动生成" maxLength={200} />
            </Form.Item>
            <Form.Item name="theme" label="歌曲主题" rules={[{ required: true, message: '请输入歌曲主题' }]}>
              <Input placeholder="例如：在成长中学会告别" maxLength={500} />
            </Form.Item>
            <Form.Item name="keywords" label="关键词">
              <Select mode="tags" tokenSeparators={[',', '，']} placeholder="输入后回车" />
            </Form.Item>
            <Form.Item name="genre_tags" label="曲风">
              <Select mode="tags" tokenSeparators={[',', '，']} placeholder="例如 流行、R&B" />
            </Form.Item>
            <Form.Item name="mood_tags" label="情绪">
              <Select mode="tags" tokenSeparators={[',', '，']} placeholder="例如 克制、治愈" />
            </Form.Item>
            <Form.Item name="scene_tags" label="场景">
              <Select mode="tags" tokenSeparators={[',', '，']} placeholder="例如 深夜、通勤" />
            </Form.Item>
            <Form.Item name="vocal_style" label="人声表达">
              <Input placeholder="例如 自然叙事，副歌情绪抬升" />
            </Form.Item>
            <Form.Item name="tempo" label="速度">
              <Segmented block options={[{ label: '慢速', value: 'slow' }, { label: '适中', value: 'medium' }, { label: '快速', value: 'fast' }]} />
            </Form.Item>
            <Form.Item name="vocal_gender" label="人声">
              <Segmented block options={[{ label: '不限', value: 'unspecified' }, { label: '男声', value: 'male' }, { label: '女声', value: 'female' }]} />
            </Form.Item>
          </div>
          <Form.Item name="requirements" label="补充要求">
            <Input.TextArea rows={3} maxLength={2000} placeholder="叙事视角、避免内容、押韵偏好等" />
          </Form.Item>
          <Button type="primary" icon={<Sparkles size={16} />} loading={generating} onClick={submit}>生成歌词</Button>
        </Form>
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div><Typography.Title level={2}>作词记录</Typography.Title><Typography.Text type="secondary">最近 15 个任务，默认显示最新 3 条</Typography.Text></div>
          {selectedTaskIds.length > 0 && (
            <Popconfirm
              title={`删除所选 ${selectedTaskIds.length} 条记录？`}
              description="所选任务下的全部歌词版本和收藏会一并删除，且无法恢复。"
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
        <CollapsibleList items={tasks} previewCount={3}>
          {(visibleTasks) => (
            <Table<LyricsTask>
              rowKey="id"
              columns={columns}
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
              scroll={{ x: 760 }}
              className="data-table"
            />
          )}
        </CollapsibleList>
      </section>

      <Drawer
        title={activeTask ? `歌词任务 #${activeTask.id}` : '歌词任务'}
        open={Boolean(activeTask)}
        onClose={closeDrawer}
        size="large"
        extra={<Button icon={<RotateCw size={16} />} loading={regenerating} onClick={regenerate}>重新生成</Button>}
      >
        {activeTask ? (
          <div className="report-stack">
            <ApiUsageDetails records={activeTask.api_usage} />
            {activeTask.error_message && <Alert type="error" showIcon title={activeTask.error_message} />}
            {activeTask.versions.length ? (
              <Tabs
                key={`${activeTask.id}-${activeTask.versions.length}`}
                activeKey={String(activeVersionId ?? activeTask.versions.at(-1)?.id)}
                onChange={(key) => setActiveVersionId(Number(key))}
                items={activeTask.versions.map((version) => ({
                  key: String(version.id),
                  label: `第 ${version.version_number} 版${version.is_saved ? ' · 已保存' : ''}`,
                  children: (
                    <LyricsVersionView
                      version={version}
                      saving={savingId === version.id}
                      favoriting={favoriteTargetId === version.id}
                      isFavorite={favoritesByTarget.has(version.id)}
                      onSave={() => save(version)}
                      onFavorite={() => void toggleFavorite(version)}
                    />
                  ),
                }))}
              />
            ) : <Empty description="该任务没有生成歌词版本" />}
          </div>
        ) : <Empty description="暂无歌词版本" />}
      </Drawer>
    </div>
  )
}

function LyricsVersionView({
  version,
  saving,
  favoriting,
  isFavorite,
  onSave,
  onFavorite,
}: {
  version: LyricsVersion
  saving: boolean
  favoriting: boolean
  isFavorite: boolean
  onSave: () => void
  onFavorite: () => void
}) {
  const { message } = App.useApp()
  const copy = async () => {
    await navigator.clipboard.writeText(`${version.title}\n\n${version.content}`)
    message.success('歌词已复制')
  }
  return (
    <div className="lyrics-output">
      <div className="lyrics-output-heading">
        <div><Typography.Title level={2}>{version.title}</Typography.Title><Typography.Text type="secondary">{version.style_prompt}</Typography.Text></div>
        <Space>
          <Tooltip title={isFavorite ? '取消收藏' : '加入收藏夹'}>
            <Button
              icon={<Star size={16} fill={isFavorite ? 'currentColor' : 'none'} />}
              className={isFavorite ? 'favorite-button-active' : undefined}
              loading={favoriting}
              aria-label={isFavorite ? '取消收藏歌词版本' : '收藏歌词版本'}
              onClick={onFavorite}
            />
          </Tooltip>
          <Tooltip title="复制歌词"><Button icon={<Copy size={16} />} aria-label="复制歌词" onClick={copy} /></Tooltip>
          <Button type={version.is_saved ? 'default' : 'primary'} icon={<BookmarkCheck size={16} />} loading={saving} onClick={onSave}>{version.is_saved ? '已保存' : '保存版本'}</Button>
        </Space>
      </div>
      <pre>{version.content}</pre>
    </div>
  )
}
