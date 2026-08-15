import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Checkbox,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import {
  Download,
  ExternalLink,
  FileAudio,
  ListMusic,
  Mic2,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
} from 'lucide-react'

import { listLyricsTasks } from '../api/lyrics'
import { useAuth } from '../auth/useAuth'
import { createFavorite, deleteFavorite, listFavorites } from '../api/favorites'
import {
  completeMusicHumanVerification,
  adaptMusicResult,
  createMusicTask,
  deleteMusicResult,
  deleteMusicTask,
  deleteMusicTasks,
  downloadMusicResult,
  extendMusicResult,
  getSunoProviderStatus,
  listMusicResults,
  listMusicTasks,
  loadMusicAudio,
  refreshSunoQuota,
  retryMusicTask,
  regenerateMusicTask,
  updateMusicProviderSettings,
} from '../api/music'
import { ApiUsageDetails } from '../components/ApiUsageDetails'
import { CollapsibleList } from '../components/CollapsibleList'
import { errorMessage } from '../lib/errors'
import type {
  LyricsVersion,
  FavoriteItem,
  MusicAdaptPayload,
  MusicCreatePayload,
  MusicExtendPayload,
  MusicResult,
  MusicTask,
  SunoProviderStatus,
  WorkflowTaskStatus,
} from '../types/api'


interface MusicFormValues {
  lyrics_version_id: number
  title?: string
  style_prompt?: string
  style_tags?: string[]
  instrumental: boolean
  negative_tags?: string[]
  requirements?: string
}

interface AdaptFormValues {
  title?: string
  lyrics?: string
  style_prompt?: string
  style_tags?: string[]
  negative_tags?: string[]
  requirements?: string
  adaptation_mode: 'extend' | 'recreate'
  source_artist?: string
  source_url?: string
  rights_confirmed: boolean
  rights_note?: string
}

interface ExtendFormValues {
  title?: string
  lyrics?: string
  style_prompt?: string
  requirements?: string
}

const STATUS_LABELS: Record<WorkflowTaskStatus, string> = {
  pending: '排队中',
  running: '生成中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
}

const STATUS_COLORS: Record<WorkflowTaskStatus, string> = {
  pending: 'default',
  running: 'processing',
  paused: 'warning',
  completed: 'success',
  failed: 'error',
}

export function MusicPage() {
  const { message } = App.useApp()
  const { user } = useAuth()
  const [form] = Form.useForm<MusicFormValues>()
  const [extendForm] = Form.useForm<ExtendFormValues>()
  const [adaptForm] = Form.useForm<AdaptFormValues>()
  const [providerStatus, setProviderStatus] = useState<SunoProviderStatus | null>(null)
  const [lyricsVersions, setLyricsVersions] = useState<LyricsVersion[]>([])
  const [tasks, setTasks] = useState<MusicTask[]>([])
  const [results, setResults] = useState<MusicResult[]>([])
  const [favorites, setFavorites] = useState<FavoriteItem[]>([])
  const [activeTask, setActiveTask] = useState<MusicTask | null>(null)
  const [extendSource, setExtendSource] = useState<MusicResult | null>(null)
  const [adaptSource, setAdaptSource] = useState<MusicResult | null>(null)
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [extending, setExtending] = useState(false)
  const [adapting, setAdapting] = useState(false)
  const [refreshingQuota, setRefreshingQuota] = useState(false)
  const [retryingTaskId, setRetryingTaskId] = useState<number | null>(null)
  const [confirmingHumanTaskId, setConfirmingHumanTaskId] = useState<number | null>(null)
  const [deletingTaskIds, setDeletingTaskIds] = useState<number[]>([])
  const [deletingResultId, setDeletingResultId] = useState<number | null>(null)
  const [favoriteResultId, setFavoriteResultId] = useState<number | null>(null)
  const [regeneratingTaskId, setRegeneratingTaskId] = useState<number | null>(null)
  const [updatingModel, setUpdatingModel] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      const [provider, lyrics, taskHistory, resultHistory, favoriteHistory] = await Promise.all([
        getSunoProviderStatus(),
        listLyricsTasks(),
        listMusicTasks(),
        listMusicResults(),
        listFavorites('music'),
      ])
      const versions = lyrics.items.flatMap((task) => task.versions).sort((a, b) => b.id - a.id)
      setProviderStatus(provider)
      setLyricsVersions(versions)
      setTasks(taskHistory.items)
      setResults(resultHistory.items)
      setFavorites(favoriteHistory.items)
      setActiveTask((current) =>
        current ? taskHistory.items.find((task) => task.id === current.id) ?? current : null,
      )
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const hasActiveTask = tasks.some((task) => task.status === 'pending' || task.status === 'running')
  const quotaExhausted = Boolean(
    providerStatus
      && !providerStatus.user_quota.is_unlimited
      && (providerStatus.user_quota.remaining_tasks ?? 0) <= 0,
  )
  useEffect(() => {
    if (!hasActiveTask) return
    const timer = window.setInterval(() => void load(true), 5000)
    return () => window.clearInterval(timer)
  }, [hasActiveTask, load])

  const selectLyricsVersion = (versionId: number) => {
    const version = lyricsVersions.find((item) => item.id === versionId)
    if (!version) return
    form.setFieldsValue({
      title: version.title,
      style_prompt: version.style_prompt,
    })
  }

  const removeOverlappingTags = (field: 'style_tags' | 'negative_tags', values: string[]) => {
    const otherField = field === 'style_tags' ? 'negative_tags' : 'style_tags'
    const otherValues = (form.getFieldValue(otherField) ?? []) as string[]
    form.setFieldValue(otherField, otherValues.filter((value) => !values.includes(value)))
  }

  const submit = async () => {
    const values = await form.validateFields()
    setCreating(true)
    try {
      const payload: MusicCreatePayload = {
        ...values,
        style_tags: values.style_tags ?? [],
        negative_tags: values.negative_tags ?? [],
      }
      const task = await createMusicTask(payload)
      message.success(`Suno 任务 #${task.id} 已进入队列`)
      form.resetFields()
      form.setFieldValue('instrumental', false)
      await load()
    } catch (submitError) {
      message.error(errorMessage(submitError))
      await load(true)
    } finally {
      setCreating(false)
    }
  }

  const removeTasks = async (taskIds: number[]) => {
    const uniqueIds = [...new Set(taskIds)]
    if (!uniqueIds.length) return
    setDeletingTaskIds(uniqueIds)
    try {
      if (uniqueIds.length === 1) await deleteMusicTask(uniqueIds[0])
      else await deleteMusicTasks(uniqueIds)
      if (activeTask && uniqueIds.includes(activeTask.id)) setActiveTask(null)
      setSelectedTaskIds((current) => current.filter((id) => !uniqueIds.includes(id)))
      message.success(uniqueIds.length === 1 ? '音乐任务已删除' : `已删除 ${uniqueIds.length} 条音乐任务`)
      await load()
    } catch (deleteError) {
      message.error(errorMessage(deleteError))
    } finally {
      setDeletingTaskIds([])
    }
  }

  const removeResult = async (result: MusicResult) => {
    setDeletingResultId(result.id)
    try {
      await deleteMusicResult(result.id)
      message.success('音乐产出已删除')
      await load()
    } catch (deleteError) {
      message.error(errorMessage(deleteError))
    } finally {
      setDeletingResultId(null)
    }
  }

  const openExtend = (result: MusicResult) => {
    setExtendSource(result)
    extendForm.setFieldsValue({ title: `${result.title} · 续写` })
  }

  const openAdapt = (result: MusicResult) => {
    setAdaptSource(result)
    adaptForm.setFieldsValue({
      title: `${result.title} · 授权改编`,
      style_tags: result.style_tags,
      negative_tags: result.negative_tags,
      adaptation_mode: 'extend',
      rights_confirmed: false,
    })
  }

  const submitExtension = async () => {
    if (!extendSource) return
    const values = await extendForm.validateFields()
    setExtending(true)
    try {
      const payload: MusicExtendPayload = values
      const task = await extendMusicResult(extendSource.id, payload)
      message.success(`续写任务 #${task.id} 已进入队列`)
      setExtendSource(null)
      extendForm.resetFields()
      await load()
    } catch (extendError) {
      message.error(errorMessage(extendError))
      await load(true)
    } finally {
      setExtending(false)
    }
  }

  const submitAdaptation = async () => {
    if (!adaptSource) return
    const values = await adaptForm.validateFields()
    setAdapting(true)
    try {
      const payload: MusicAdaptPayload = {
        ...values,
        style_tags: values.style_tags ?? [],
        negative_tags: values.negative_tags ?? [],
      }
      const task = await adaptMusicResult(adaptSource.id, payload)
      message.success(`授权改编任务 #${task.id} 已进入队列`)
      setAdaptSource(null)
      adaptForm.resetFields()
      await load()
    } catch (adaptError) {
      message.error(errorMessage(adaptError))
      await load(true)
    } finally {
      setAdapting(false)
    }
  }

  const toggleFavorite = async (result: MusicResult) => {
    const existing = favorites.find((favorite) => favorite.target_id === result.id)
    setFavoriteResultId(result.id)
    try {
      if (existing) {
        await deleteFavorite(existing.id)
        setFavorites((current) => current.filter((favorite) => favorite.id !== existing.id))
        message.success('已从收藏夹移除')
      } else {
        const favorite = await createFavorite('music', result.id)
        setFavorites((current) => [favorite, ...current])
        message.success('音乐结果已加入收藏夹，当前为待分类')
      }
    } catch (favoriteError) {
      message.error(errorMessage(favoriteError))
    } finally {
      setFavoriteResultId(null)
    }
  }

  const regenerate = async (taskId: number) => {
    setRegeneratingTaskId(taskId)
    try {
      const task = await regenerateMusicTask(taskId)
      message.success(`音乐任务 #${task.id} 已重新进入队列`)
      await load(true)
    } catch (regenerateError) {
      message.error(errorMessage(regenerateError))
    } finally {
      setRegeneratingTaskId(null)
    }
  }

  const changeActiveModel = async (activeModel: string) => {
    setUpdatingModel(true)
    try {
      await updateMusicProviderSettings(activeModel)
      message.success(`后续音乐任务将使用 ${activeModel}`)
      await load(true)
    } catch (modelError) {
      message.error(errorMessage(modelError))
    } finally {
      setUpdatingModel(false)
    }
  }

  const favoritesByResult = useMemo(
    () => new Map(favorites.map((favorite) => [favorite.target_id, favorite])),
    [favorites],
  )

  const refreshQuota = async () => {
    setRefreshingQuota(true)
    try {
      const quota = await refreshSunoQuota()
      message.success(quota.status === 'available' ? 'Suno 额度已更新' : '额度查询返回错误')
      await load(true)
    } catch (quotaError) {
      message.error(errorMessage(quotaError))
    } finally {
      setRefreshingQuota(false)
    }
  }

  const retryTask = async (taskId: number) => {
    setRetryingTaskId(taskId)
    try {
      const task = await retryMusicTask(taskId)
      message.success(`音乐任务 #${task.id} 已重新进入队列`)
      await load(true)
    } catch (retryError) {
      message.error(errorMessage(retryError))
    } finally {
      setRetryingTaskId(null)
    }
  }

  const confirmHumanVerification = async (taskId: number) => {
    setConfirmingHumanTaskId(taskId)
    try {
      const task = await completeMusicHumanVerification(taskId)
      message.success(`音乐任务 #${task.id} 已在人机验证后重新进入队列`)
      await load(true)
    } catch (confirmError) {
      message.error(errorMessage(confirmError))
    } finally {
      setConfirmingHumanTaskId(null)
    }
  }

  const columns: TableProps<MusicTask>['columns'] = [
    {
      title: '任务',
      key: 'task',
      render: (_, task) => (
        <button type="button" className="table-link-button" onClick={() => setActiveTask(task)}>
          <strong>#{task.id} · {task.title}</strong>
          <small>
            {task.operation === 'extend' ? '续写' : '完整生成'} ·
            {task.provider_implementation === 'official' ? ' 官方接口' : ' 兼容接口'} ·
            尝试 {task.attempt_count}/{task.max_attempts}
          </small>
        </button>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (_value: WorkflowTaskStatus, task) => (
        <Tag color={musicStatusColor(task)}>{musicStatusLabel(task)}</Tag>
      ),
    },
    {
      title: '产出',
      width: 90,
      render: (_, task) => `${task.results.length} 首`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '',
      width: 64,
      render: (_, task) => (
        <Popconfirm
          title="删除音乐任务？"
          description="任务下的音频产出也会永久删除。"
          okText="删除"
          cancelText="取消"
          disabled={task.status === 'pending' || task.status === 'running'}
          onConfirm={() => void removeTasks([task.id])}
        >
          <Tooltip title="删除任务">
            <Button
              danger
              type="text"
              icon={<Trash2 size={16} />}
              aria-label="删除音乐任务"
              disabled={task.status === 'pending' || task.status === 'running'}
              loading={deletingTaskIds.includes(task.id)}
            />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>音乐创作</Typography.Title>
          <Typography.Text type="secondary">把已确认歌词提交给 Suno，并集中管理试听与下载</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void load()}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon title={error} />}
      {providerStatus && (
        <Alert
          className="music-provider-alert"
          type={providerStatus.integration_status === 'ready' ? 'success' : providerStatus.integration_status === 'contract_pending' ? 'info' : 'warning'}
          showIcon
          title={`Suno ${
            providerStatus.implementation === 'official'
              ? '官方实现'
              : providerStatus.implementation === 'compatibility'
                ? '兼容实现'
                : '配置错误'
          }`}
          description={(
            <Space orientation="vertical" size={2}>
              <span>{providerStatus.message}</span>
              {providerStatus.implementation === 'compatibility' && providerStatus.captcha_mode && (
                <Typography.Text type="secondary">
                  验证模式：{providerStatus.captcha_mode === 'human_verification' ? '管理员人工验证' : providerStatus.captcha_mode}
                  {providerStatus.cookie_configured === false ? ' · 等待本机会话' : ''}
                </Typography.Text>
              )}
            </Space>
          )}
          action={
            <Space wrap>
              {user?.role === 'super_admin' && (
                <Button
                  icon={<RefreshCw size={15} />}
                  loading={refreshingQuota}
                  onClick={() => void refreshQuota()}
                >
                  刷新额度
                </Button>
              )}
              <Button
                href={providerStatus.implementation === 'compatibility' ? 'https://suno.com/create' : providerStatus.platform_url}
                target="_blank"
                icon={<ExternalLink size={15} />}
              >
                {providerStatus.implementation === 'compatibility' ? '打开 Suno' : 'Suno Platform'}
              </Button>
            </Space>
          }
        />
      )}
      {providerStatus && (
        <section className="content-section">
          <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 4 }} bordered>
            <Descriptions.Item label="任务队列">{providerStatus.queue_mode === 'redis' ? 'Redis 独立队列' : '进程内执行'}</Descriptions.Item>
            <Descriptions.Item label="最大并发">{providerStatus.max_concurrency}</Descriptions.Item>
            <Descriptions.Item label="请求间隔">{providerStatus.min_request_interval_seconds} 秒</Descriptions.Item>
            <Descriptions.Item label="当前音乐模型">
              {user?.role === 'super_admin' ? (
                <Select
                  size="small"
                  value={providerStatus.active_model}
                  loading={updatingModel}
                  options={['v4.5', 'v4', 'v3.5'].map((model) => ({ value: model, label: model }))}
                  onChange={(model) => void changeActiveModel(model)}
                />
              ) : providerStatus.active_model}
            </Descriptions.Item>
            <Descriptions.Item label="我的任务额度">
              {providerStatus.user_quota.is_unlimited
                ? '不限额'
                : `剩余 ${providerStatus.user_quota.remaining_tasks ?? 0} 次 · 累计使用 ${providerStatus.user_quota.used_tasks} 次`}
            </Descriptions.Item>
            {user?.role === 'super_admin' && (
              <Descriptions.Item label="Suno 剩余额度">
                {providerStatus.quota?.status === 'available'
                  ? providerStatus.quota.credits_remaining ?? '未知'
                  : providerStatus.quota?.error_message ?? '尚未查询'}
              </Descriptions.Item>
            )}
            {user?.role === 'super_admin' && providerStatus.quota?.status === 'available' && (
              <Descriptions.Item label="Suno 本期用量">
                {providerStatus.quota.usage ?? '未知'}
              </Descriptions.Item>
            )}
            {user?.role === 'super_admin' && providerStatus.quota && (
              <Descriptions.Item label="额度更新时间">
                {formatDateTime(providerStatus.quota.checked_at)}
              </Descriptions.Item>
            )}
          </Descriptions>
        </section>
      )}

      <section className="content-section music-create-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>创建 Suno 任务</Typography.Title>
            <Typography.Text type="secondary">选择歌词后设置目标风格与排除风格；后续任务使用当前模型 {providerStatus?.active_model ?? 'v4.5'}</Typography.Text>
          </div>
        </div>
        {lyricsVersions.length ? (
          <Form<MusicFormValues>
            form={form}
            layout="vertical"
            initialValues={{ instrumental: false }}
          >
            <div className="form-grid">
              <Form.Item
                name="lyrics_version_id"
                label="歌词版本"
                rules={[{ required: true, message: '请选择歌词版本' }]}
              >
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择已生成的歌词"
                  options={lyricsVersions.map((version) => ({
                    value: version.id,
                    label: `${version.title} · 第 ${version.version_number} 版 · #${version.id}`,
                  }))}
                  onChange={selectLyricsVersion}
                />
              </Form.Item>
              <Form.Item name="title" label="歌曲标题">
                <Input maxLength={200} placeholder="默认使用歌词标题" />
              </Form.Item>
            </div>
            <Form.Item name="style_prompt" label="Suno 风格要求">
              <Input.TextArea rows={3} maxLength={3000} placeholder="曲风、情绪、速度、人声和乐器要求" />
            </Form.Item>
            <div className="form-grid">
              <Form.Item name="style_tags" label="目标风格">
                <Select
                  mode="tags"
                  tokenSeparators={[',', '，']}
                  placeholder="可多选，例如 流行、R&B、氛围电子"
                  onChange={(values) => removeOverlappingTags('style_tags', values)}
                />
              </Form.Item>
              <Form.Item name="negative_tags" label="排除风格">
                <Select
                  mode="tags"
                  tokenSeparators={[',', '，']}
                  placeholder="可多选，例如 重金属、尖锐高音"
                  onChange={(values) => removeOverlappingTags('negative_tags', values)}
                />
              </Form.Item>
              <Form.Item name="instrumental" label="纯音乐" valuePropName="checked">
                <Switch checkedChildren="开启" unCheckedChildren="带人声" />
              </Form.Item>
            </div>
            <Form.Item name="requirements" label="补充要求">
              <Input.TextArea rows={2} maxLength={2000} placeholder="可选，例如副歌提前、结尾留白" />
            </Form.Item>
            <Button
              type="primary"
              icon={<Sparkles size={16} />}
              loading={creating}
              disabled={quotaExhausted}
              onClick={() => void submit()}
            >
              提交 Suno 生成
            </Button>
          </Form>
        ) : (
          <Empty description="还没有可用歌词，请先在歌词创作中生成歌词" />
        )}
      </section>

      <section className="content-section music-listening-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>试听区</Typography.Title>
            <Typography.Text type="secondary">每首音频独立试听、下载、收藏、再次生成或授权改编</Typography.Text>
          </div>
          <Tag icon={<ListMusic size={13} />}>{results.length} 首</Tag>
        </div>
        {results.length ? (
          <CollapsibleList items={results} previewCount={6}>
            {(visibleResults) => (
              <div className="music-result-list">
                {visibleResults.map((result) => (
                  <MusicResultItem
                    key={result.id}
                    result={result}
                    deleting={deletingResultId === result.id}
                    favorite={favoritesByResult.get(result.id)}
                    favoriting={favoriteResultId === result.id}
                    canCreate={!quotaExhausted}
                    regenerating={regeneratingTaskId === result.task_id}
                    onRegenerate={() => void regenerate(result.task_id)}
                    onExtend={() => openExtend(result)}
                    onAdapt={() => openAdapt(result)}
                    onFavorite={() => void toggleFavorite(result)}
                    onDelete={() => void removeResult(result)}
                  />
                ))}
              </div>
            )}
          </CollapsibleList>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可试听音乐" />
        )}
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>生成记录</Typography.Title>
            <Typography.Text type="secondary">默认展示最新三条，其余按需展开</Typography.Text>
          </div>
          {selectedTaskIds.length > 0 && (
            <Popconfirm
              title={`删除 ${selectedTaskIds.length} 条音乐任务？`}
              description="关联音频会一并永久删除。"
              okText="批量删除"
              cancelText="取消"
              onConfirm={() => void removeTasks(selectedTaskIds)}
            >
              <Button danger icon={<Trash2 size={16} />}>
                删除所选 ({selectedTaskIds.length})
              </Button>
            </Popconfirm>
          )}
        </div>
        <CollapsibleList items={tasks} previewCount={3}>
          {(visibleTasks) => (
            <Table<MusicTask>
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
        title={activeTask ? `音乐任务 #${activeTask.id}` : '音乐任务'}
        open={Boolean(activeTask)}
        onClose={() => setActiveTask(null)}
        size="large"
      >
        {activeTask ? (
          <div className="report-stack">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="状态">
                <Tag color={musicStatusColor(activeTask)}>{musicStatusLabel(activeTask)}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="供应商">Suno{activeTask.model ? ` / ${activeTask.model}` : ''}</Descriptions.Item>
              <Descriptions.Item label="接口实现">
                {activeTask.provider_implementation === 'official' ? '官方 Suno API' : '隔离兼容服务'}
              </Descriptions.Item>
              <Descriptions.Item label="尝试次数">{activeTask.attempt_count} / {activeTask.max_attempts}</Descriptions.Item>
              <Descriptions.Item label="下次重试">
                {activeTask.next_attempt_at ? formatDateTime(activeTask.next_attempt_at) : '无'}
              </Descriptions.Item>
              <Descriptions.Item label="外部任务编号">{activeTask.external_task_id ?? '尚未获得'}</Descriptions.Item>
              <Descriptions.Item label="创作方式">{activeTask.operation === 'extend' ? '续写' : '完整生成'}</Descriptions.Item>
              <Descriptions.Item label="风格要求">{activeTask.style_prompt}</Descriptions.Item>
            </Descriptions>
            {activeTask.error_message && (
              <Alert
                type="error"
                showIcon
                title={activeTask.error_message}
                description={taskErrorDescription(activeTask)}
                action={
                  isWaitingHumanVerification(activeTask) ? (
                    user?.role === 'super_admin' ? (
                      <Popconfirm
                        title="确认已完成人机验证？"
                        description="请先在正常 Suno 网页完成验证并更新本地兼容服务会话。"
                        okText="重新入队"
                        cancelText="取消"
                        onConfirm={() => void confirmHumanVerification(activeTask.id)}
                      >
                        <Button
                          icon={<ShieldCheck size={15} />}
                          loading={confirmingHumanTaskId === activeTask.id}
                        >
                          验证完成，重新入队
                        </Button>
                      </Popconfirm>
                    ) : undefined
                  ) : activeTask.status === 'failed' ? (
                    <Button
                      icon={<RefreshCw size={15} />}
                      loading={retryingTaskId === activeTask.id}
                      onClick={() => void retryTask(activeTask.id)}
                    >
                      重新入队
                    </Button>
                  ) : undefined
                }
              />
            )}
            <ApiUsageDetails records={activeTask.api_usage} />
            <div className="music-task-lyrics">
              <Typography.Title level={3}>提交歌词</Typography.Title>
              <pre>{activeTask.instrumental ? '纯音乐任务' : activeTask.lyrics}</pre>
            </div>
          </div>
        ) : <Empty description="暂无任务详情" />}
      </Drawer>

      <Modal
        title={extendSource ? `续写：${extendSource.title}` : '续写音乐'}
        open={Boolean(extendSource)}
        okText="提交续写"
        cancelText="取消"
        confirmLoading={extending}
        okButtonProps={{ disabled: quotaExhausted }}
        onOk={() => void submitExtension()}
        onCancel={() => {
          setExtendSource(null)
          extendForm.resetFields()
        }}
      >
        <Form<ExtendFormValues> form={extendForm} layout="vertical">
          <Form.Item name="title" label="新标题">
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="lyrics" label="续写歌词">
            <Input.TextArea rows={6} maxLength={5000} placeholder="留空则继续使用原任务歌词" />
          </Form.Item>
          <Form.Item name="style_prompt" label="风格调整">
            <Input.TextArea rows={3} maxLength={3000} placeholder="留空则沿用原风格" />
          </Form.Item>
          <Form.Item name="requirements" label="补充要求">
            <Input.TextArea rows={2} maxLength={2000} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={adaptSource ? `授权改编：${adaptSource.title}` : '授权改编'}
        open={Boolean(adaptSource)}
        okText="提交授权改编"
        cancelText="取消"
        confirmLoading={adapting}
        okButtonProps={{ disabled: quotaExhausted }}
        onOk={() => void submitAdaptation()}
        onCancel={() => {
          setAdaptSource(null)
          adaptForm.resetFields()
        }}
      >
        <Alert
          type="info"
          showIcon
          title="仅用于已取得授权的自有或客户作品"
          description="当前兼容实现可使用已有音乐结果的续写或根据授权创作说明重新生成，不会伪装为未提供的 Cover 或 Remix 接口。"
        />
        <Form<AdaptFormValues> form={adaptForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="title" label="新标题">
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="adaptation_mode" label="改编方式">
            <Select options={[
              { value: 'extend', label: '基于当前结果续写' },
              { value: 'recreate', label: '根据授权创作说明重新生成' },
            ]} />
          </Form.Item>
          <Form.Item name="lyrics" label="改编歌词">
            <Input.TextArea rows={4} maxLength={5000} placeholder="留空则沿用原任务歌词" />
          </Form.Item>
          <div className="form-grid">
            <Form.Item name="style_tags" label="目标风格">
              <Select mode="tags" tokenSeparators={[',', '，']} />
            </Form.Item>
            <Form.Item name="negative_tags" label="排除风格">
              <Select mode="tags" tokenSeparators={[',', '，']} />
            </Form.Item>
          </div>
          <Form.Item name="style_prompt" label="风格调整">
            <Input.TextArea rows={2} maxLength={3000} />
          </Form.Item>
          <Form.Item name="source_artist" label="来源作者或权利方">
            <Input maxLength={200} placeholder="可选，用于记录授权来源" />
          </Form.Item>
          <Form.Item name="source_url" label="来源链接">
            <Input maxLength={2000} placeholder="可选，用于记录授权来源" />
          </Form.Item>
          <Form.Item name="rights_note" label="授权备注">
            <Input.TextArea rows={2} maxLength={1000} placeholder="授权范围、联系人或内部说明" />
          </Form.Item>
          <Form.Item
            name="rights_confirmed"
            valuePropName="checked"
            rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error('请确认已取得授权')) }]}
          >
            <Checkbox>我确认已取得该来源作品的使用或改编授权</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}


function MusicResultItem({
  result,
  deleting,
  favorite,
  favoriting,
  canCreate,
  regenerating,
  onRegenerate,
  onExtend,
  onAdapt,
  onFavorite,
  onDelete,
}: {
  result: MusicResult
  deleting: boolean
  favorite: FavoriteItem | undefined
  favoriting: boolean
  canCreate: boolean
  regenerating: boolean
  onRegenerate: () => void
  onExtend: () => void
  onAdapt: () => void
  onFavorite: () => void
  onDelete: () => void
}) {
  const { message } = App.useApp()
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [loadingAudio, setLoadingAudio] = useState(false)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
  }, [audioUrl])

  const loadAudio = async () => {
    if (audioUrl) return
    setLoadingAudio(true)
    try {
      const blob = await loadMusicAudio(result.audio_path)
      setAudioUrl(URL.createObjectURL(blob))
    } catch (audioError) {
      message.error(errorMessage(audioError))
    } finally {
      setLoadingAudio(false)
    }
  }

  const download = async () => {
    setDownloading(true)
    try {
      await downloadMusicResult(result.download_path, result.title)
      message.success('已开始下载')
    } catch (downloadError) {
      message.error(errorMessage(downloadError))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <article className="music-result-item">
      <div className="music-result-cover">
        {result.image_url ? <img src={result.image_url} alt="" /> : <FileAudio size={28} />}
      </div>
      <div className="music-result-copy">
        <div className="music-result-title-row">
          <strong>{result.title}</strong>
          <Tag color={favorite ? 'gold' : 'default'}>{favorite ? favoriteCategoryLabel(favorite.category) : '待分类'}</Tag>
        </div>
        <span>任务 #{result.task_id} · {formatDateTime(result.created_at)} · 时长 {formatDuration(result.duration_seconds)}</span>
        <small>{result.task_operation === 'adapt' ? '授权改编' : result.task_operation === 'extend' ? '续写版本' : '完整生成'} · {result.task_model ?? '默认模型'}</small>
        {result.style_tags.length > 0 && <small>风格：{result.style_tags.join(' · ')}</small>}
        {result.storage_error && <small>{result.storage_error}，当前将尝试使用供应商地址试听</small>}
      </div>
      <div className="music-result-player">
        {audioUrl ? (
          <audio controls preload="metadata" src={audioUrl} aria-label={`试听 ${result.title}`} />
        ) : (
          <Button
            icon={<Play size={16} />}
            loading={loadingAudio}
            disabled={!result.audio_ready}
            onClick={() => void loadAudio()}
          >
            加载试听
          </Button>
        )}
      </div>
      <Space className="music-result-actions">
        <Button
          type="primary"
          icon={<Sparkles size={16} />}
          loading={regenerating}
          disabled={!canCreate}
          onClick={onRegenerate}
        >
          再次生成
        </Button>
        <Button disabled={!canCreate} onClick={onAdapt}>授权改编</Button>
        <Button icon={<Sparkles size={16} />} disabled={!canCreate} onClick={onExtend}>续写</Button>
        <Tooltip title="需先接入已授权的声音模型库">
          <Button icon={<Mic2 size={16} />} disabled aria-label="声音模型替换" />
        </Tooltip>
        <Tooltip title={favorite ? '取消收藏' : '加入收藏夹'}>
          <Button
            icon={<Star size={16} fill={favorite ? 'currentColor' : 'none'} />}
            className={favorite ? 'favorite-button-active' : undefined}
            loading={favoriting}
            aria-label={favorite ? '取消收藏音乐结果' : '收藏音乐结果'}
            onClick={onFavorite}
          />
        </Tooltip>
        <Tooltip title="下载音频">
          <Button
            icon={<Download size={16} />}
            loading={downloading}
            disabled={!result.audio_ready}
            aria-label="下载音乐"
            onClick={() => void download()}
          />
        </Tooltip>
        {result.provider_page_url && (
          <Tooltip title="在 Suno 查看">
            <Button
              href={result.provider_page_url}
              target="_blank"
              icon={<ExternalLink size={16} />}
              aria-label="在 Suno 查看"
            />
          </Tooltip>
        )}
        <Popconfirm
          title="删除这首音乐？"
          description="音频文件和记录会永久删除。"
          okText="删除"
          cancelText="取消"
          onConfirm={onDelete}
        >
          <Tooltip title="删除产出">
            <Button danger type="text" icon={<Trash2 size={16} />} loading={deleting} aria-label="删除音乐产出" />
          </Tooltip>
        </Popconfirm>
      </Space>
    </article>
  )
}


function isWaitingHumanVerification(task: MusicTask) {
  return task.provider_status === 'waiting_human_verification'
    || task.error_code === 'SUNO_HUMAN_VERIFICATION_REQUIRED'
}


function musicStatusLabel(task: MusicTask) {
  return isWaitingHumanVerification(task) ? '待人机验证' : STATUS_LABELS[task.status]
}


function musicStatusColor(task: MusicTask) {
  return isWaitingHumanVerification(task) ? 'warning' : STATUS_COLORS[task.status]
}


function taskErrorDescription(task: MusicTask) {
  const lines = [
    task.error_code ? `错误码：${task.error_code}` : null,
    isWaitingHumanVerification(task)
      ? '请超级管理员在正常 Suno 网页完成人机验证并更新本地兼容服务会话，然后恢复任务。'
      : null,
  ].filter(Boolean)
  return lines.length ? lines.join('\n') : undefined
}


function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}


function formatDuration(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) return '—'
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.max(0, Math.round(seconds % 60))
  return `${minutes}:${String(remainder).padStart(2, '0')}`
}


function favoriteCategoryLabel(category: FavoriteItem['category']) {
  return category === 'unclassified' ? '待分类' : `${category} 级`
}
