import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
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
  Play,
  RefreshCw,
  Sparkles,
  Trash2,
} from 'lucide-react'

import { listLyricsTasks } from '../api/lyrics'
import {
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
} from '../api/music'
import { ApiUsageDetails } from '../components/ApiUsageDetails'
import { CollapsibleList } from '../components/CollapsibleList'
import { errorMessage } from '../lib/errors'
import type {
  LyricsVersion,
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
  instrumental: boolean
  negative_tags?: string[]
  requirements?: string
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
  completed: '已完成',
  failed: '失败',
}

const STATUS_COLORS: Record<WorkflowTaskStatus, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
}

export function MusicPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm<MusicFormValues>()
  const [extendForm] = Form.useForm<ExtendFormValues>()
  const [providerStatus, setProviderStatus] = useState<SunoProviderStatus | null>(null)
  const [lyricsVersions, setLyricsVersions] = useState<LyricsVersion[]>([])
  const [tasks, setTasks] = useState<MusicTask[]>([])
  const [results, setResults] = useState<MusicResult[]>([])
  const [activeTask, setActiveTask] = useState<MusicTask | null>(null)
  const [extendSource, setExtendSource] = useState<MusicResult | null>(null)
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [extending, setExtending] = useState(false)
  const [deletingTaskIds, setDeletingTaskIds] = useState<number[]>([])
  const [deletingResultId, setDeletingResultId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      const [provider, lyrics, taskHistory, resultHistory] = await Promise.all([
        getSunoProviderStatus(),
        listLyricsTasks(),
        listMusicTasks(),
        listMusicResults(),
      ])
      const versions = lyrics.items.flatMap((task) => task.versions).sort((a, b) => b.id - a.id)
      setProviderStatus(provider)
      setLyricsVersions(versions)
      setTasks(taskHistory.items)
      setResults(resultHistory.items)
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

  const submit = async () => {
    const values = await form.validateFields()
    setCreating(true)
    try {
      const payload: MusicCreatePayload = {
        ...values,
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

  const columns: TableProps<MusicTask>['columns'] = [
    {
      title: '任务',
      key: 'task',
      render: (_, task) => (
        <button type="button" className="table-link-button" onClick={() => setActiveTask(task)}>
          <strong>#{task.id} · {task.title}</strong>
          <small>{task.operation === 'extend' ? '续写' : '完整生成'} · Suno{task.model ? ` / ${task.model}` : ''}</small>
        </button>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: WorkflowTaskStatus) => <Tag color={STATUS_COLORS[value]}>{STATUS_LABELS[value]}</Tag>,
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
      {providerStatus && providerStatus.integration_status !== 'contract_pending' && (
        <Alert
          type="warning"
          showIcon
          title="Suno 官方 API 尚未配置"
          description={providerStatus.message}
          action={
            <Button
              href={providerStatus.platform_url}
              target="_blank"
              icon={<ExternalLink size={15} />}
            >
              打开 Suno Platform
            </Button>
          }
        />
      )}
      {providerStatus?.integration_status === 'contract_pending' && (
        <Alert type="info" showIcon title="Suno 账号已配置" description={providerStatus.message} />
      )}

      <section className="content-section music-create-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>创建 Suno 任务</Typography.Title>
            <Typography.Text type="secondary">选择一个歌词版本，标题和风格会自动带入</Typography.Text>
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
              <Form.Item name="negative_tags" label="排除风格">
                <Select mode="tags" tokenSeparators={[',', '，']} placeholder="例如：重金属、尖锐高音" />
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
            <Typography.Text type="secondary">生成完成的每首音频独立播放、下载和续写</Typography.Text>
          </div>
          <Tag icon={<ListMusic size={13} />}>{results.length} 首</Tag>
        </div>
        {results.length ? (
          <div className="music-result-list">
            {results.map((result) => (
              <MusicResultItem
                key={result.id}
                result={result}
                deleting={deletingResultId === result.id}
                onExtend={() => openExtend(result)}
                onDelete={() => void removeResult(result)}
              />
            ))}
          </div>
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
                <Tag color={STATUS_COLORS[activeTask.status]}>{STATUS_LABELS[activeTask.status]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="供应商">Suno{activeTask.model ? ` / ${activeTask.model}` : ''}</Descriptions.Item>
              <Descriptions.Item label="外部任务编号">{activeTask.external_task_id ?? '尚未获得'}</Descriptions.Item>
              <Descriptions.Item label="创作方式">{activeTask.operation === 'extend' ? '续写' : '完整生成'}</Descriptions.Item>
              <Descriptions.Item label="风格要求">{activeTask.style_prompt}</Descriptions.Item>
            </Descriptions>
            {activeTask.error_message && (
              <Alert
                type="error"
                showIcon
                title={activeTask.error_message}
                description={activeTask.error_code ? `错误码：${activeTask.error_code}` : undefined}
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
    </div>
  )
}


function MusicResultItem({
  result,
  deleting,
  onExtend,
  onDelete,
}: {
  result: MusicResult
  deleting: boolean
  onExtend: () => void
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
        <strong>{result.title}</strong>
        <span>任务 #{result.task_id} · {formatDateTime(result.created_at)}{result.duration_seconds ? ` · ${formatDuration(result.duration_seconds)}` : ''}</span>
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
        <Tooltip title="下载音频">
          <Button
            icon={<Download size={16} />}
            loading={downloading}
            disabled={!result.audio_ready}
            aria-label="下载音乐"
            onClick={() => void download()}
          />
        </Tooltip>
        <Button icon={<Sparkles size={16} />} onClick={onExtend}>续写</Button>
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


function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}


function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.max(0, Math.round(seconds % 60))
  return `${minutes}:${String(remainder).padStart(2, '0')}`
}
