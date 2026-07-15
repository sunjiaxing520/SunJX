import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Checkbox,
  Collapse,
  Empty,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Segmented,
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
  ArrowRight,
  BarChart3,
  ChartNoAxesCombined,
  FileMusic,
  Music2,
  Pencil,
  Play,
  RefreshCw,
  Save,
  Trash2,
  X,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import {
  createWorkflowTemplate,
  deleteWorkflowTemplate,
  listWorkflowRuns,
  listWorkflowTemplates,
  startWorkflowRun,
  updateWorkflowTemplate,
} from '../api/workflows'
import { hasAgentAccess } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { CollapsibleList } from '../components/CollapsibleList'
import { errorMessage } from '../lib/errors'
import {
  toggleWorkflowStep,
  WORKFLOW_STEP_LABELS,
  WORKFLOW_STEP_ORDER,
} from '../lib/workflows'
import type {
  AgentType,
  WorkflowRun,
  WorkflowRunStep,
  WorkflowStepType,
  WorkflowTaskStatus,
  WorkflowTemplate,
  WorkflowTemplatePayload,
} from '../types/api'

interface WorkflowFormValues {
  name: string
  steps: WorkflowStepType[]
  source_mode: 'live' | 'sample'
  collection_limit: number
  window_days: number
  direction_number: number
  title_hint?: string
  theme?: string
  requirements?: string
}

const STEP_AGENT: Record<WorkflowStepType, AgentType> = {
  collection: 'crawler',
  analysis: 'analysis',
  lyrics: 'lyrics',
}

const STEP_META = {
  collection: {
    icon: BarChart3,
    description: '输出榜单快照和歌曲 ID',
  },
  analysis: {
    icon: ChartNoAxesCombined,
    description: '输入歌曲 ID，输出分析报告',
  },
  lyrics: {
    icon: FileMusic,
    description: '输入分析报告，输出歌词版本',
  },
} as const

const STATUS_META: Record<
  WorkflowTaskStatus,
  {
    label: string
    color?: string
    stepStatus: 'wait' | 'process' | 'finish' | 'error'
  }
> = {
  pending: { label: '等待中', stepStatus: 'wait' },
  running: { label: '运行中', color: 'processing', stepStatus: 'process' },
  completed: { label: '已完成', color: 'success', stepStatus: 'finish' },
  failed: { label: '失败', color: 'error', stepStatus: 'error' },
}

function formatTime(value: string | null) {
  return value
    ? new Date(value).toLocaleString('zh-CN', { hour12: false })
    : '-'
}

function optionalText(value?: string) {
  const cleaned = value?.trim()
  return cleaned || null
}

function WorkflowStepSelector({
  value = [],
  onChange,
  allowedSteps,
}: {
  value?: WorkflowStepType[]
  onChange?: (steps: WorkflowStepType[]) => void
  allowedSteps: Set<WorkflowStepType>
}) {
  return (
    <div className="workflow-step-selector">
      {WORKFLOW_STEP_ORDER.map((step, index) => {
        const meta = STEP_META[step]
        const Icon = meta.icon
        const checked = value.includes(step)
        const disabled = !allowedSteps.has(step)
        return (
          <div
            className={`workflow-step-option${checked ? ' workflow-step-option-selected' : ''}`}
            key={step}
          >
            <Checkbox
              checked={checked}
              disabled={disabled}
              aria-label={`选择${WORKFLOW_STEP_LABELS[step]}步骤`}
              onChange={(event) =>
                onChange?.(
                  toggleWorkflowStep(value, step, event.target.checked),
                )
              }
            />
            <span className="workflow-step-option-icon"><Icon size={18} /></span>
            <span className="workflow-step-option-copy">
              <strong>{index + 1}. {WORKFLOW_STEP_LABELS[step]}</strong>
              <small>{disabled ? '当前账号无权限' : meta.description}</small>
            </span>
          </div>
        )
      })}
      <div className="workflow-step-option workflow-step-option-disabled">
        <Checkbox disabled aria-label="音乐创作步骤尚未开放" />
        <span className="workflow-step-option-icon"><Music2 size={18} /></span>
        <span className="workflow-step-option-copy">
          <strong>4. 音乐创作</strong>
          <small>等待正式音乐生成接口接入</small>
        </span>
      </div>
    </div>
  )
}

function DataHandoffs({ steps }: { steps: WorkflowStepType[] }) {
  const handoffs = [
    steps.includes('collection') && steps.includes('analysis')
      ? ['榜单快照 + 歌曲 ID', '内容分析输入']
      : null,
    steps.includes('analysis') && steps.includes('lyrics')
      ? ['分析报告 + 创作方向', '歌词创作输入']
      : null,
  ].filter((value): value is string[] => value !== null)

  if (!handoffs.length) return null
  return (
    <div className="workflow-handoff-list" aria-label="步骤参数传递">
      {handoffs.map(([output, input]) => (
        <span key={output}>
          <strong>{output}</strong>
          <ArrowRight size={15} />
          <small>{input}</small>
        </span>
      ))}
    </div>
  )
}

export function WorkflowsPage() {
  const { user } = useAuth()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [form] = Form.useForm<WorkflowFormValues>()
  const selectedSteps = Form.useWatch('steps', form) ?? []
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshingRuns, setRefreshingRuns] = useState(false)
  const [saveMode, setSaveMode] = useState<'save' | 'run' | null>(null)
  const [runningTemplateId, setRunningTemplateId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const allowedSteps = useMemo(() => {
    if (!user) return new Set<WorkflowStepType>()
    const values = new Set(
      WORKFLOW_STEP_ORDER.filter((step) =>
        hasAgentAccess(user, STEP_AGENT[step]),
      ),
    )
    if (!values.has('analysis')) values.delete('lyrics')
    return values
  }, [user])

  const defaultSteps = useMemo(() => {
    return WORKFLOW_STEP_ORDER.filter((step) => allowedSteps.has(step))
  }, [allowedSteps])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [templateItems, runItems] = await Promise.all([
        listWorkflowTemplates(),
        listWorkflowRuns(),
      ])
      setTemplates(templateItems)
      setRuns(runItems.items)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshRuns = useCallback(async () => {
    setRefreshingRuns(true)
    try {
      const result = await listWorkflowRuns()
      setRuns(result.items)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setRefreshingRuns(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    form.setFieldsValue({
      name: '完整创作流程',
      steps: defaultSteps,
      source_mode: 'live',
      collection_limit: 100,
      window_days: 7,
      direction_number: 1,
    })
  }, [defaultSteps, form])

  useEffect(() => {
    if (!runs.some((run) => run.status === 'pending' || run.status === 'running')) {
      return undefined
    }
    const timer = window.setInterval(() => void refreshRuns(), 2500)
    return () => window.clearInterval(timer)
  }, [refreshRuns, runs])

  const resetEditor = () => {
    setEditingId(null)
    form.setFieldsValue({
      name: '完整创作流程',
      steps: defaultSteps,
      source_mode: 'live',
      collection_limit: 100,
      window_days: 7,
      direction_number: 1,
      title_hint: undefined,
      theme: undefined,
      requirements: undefined,
    })
  }

  const toPayload = (values: WorkflowFormValues): WorkflowTemplatePayload => ({
    name: values.name.trim(),
    steps: values.steps,
    configuration: {
      collection: {
        source_mode: values.source_mode,
        limit: values.collection_limit,
      },
      analysis: { window_days: values.window_days },
      lyrics: {
        direction_index: values.direction_number - 1,
        title_hint: optionalText(values.title_hint),
        theme: optionalText(values.theme),
        language: '中文',
        requirements: optionalText(values.requirements),
      },
    },
  })

  const saveTemplate = async (runAfterSave: boolean) => {
    const values = await form.validateFields()
    let templateSaved = false
    setSaveMode(runAfterSave ? 'run' : 'save')
    try {
      const payload = toPayload(values)
      const template = editingId
        ? await updateWorkflowTemplate(editingId, payload)
        : await createWorkflowTemplate(payload)
      templateSaved = true
      message.success(editingId ? '流程设置已更新' : '流程已保存')
      resetEditor()
      if (runAfterSave) {
        setRunningTemplateId(template.id)
        await startWorkflowRun(template.id)
        message.success('自动流程已经启动')
      }
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSaveMode(null)
      setRunningTemplateId(null)
      if (templateSaved) await load()
    }
  }

  const editTemplate = (template: WorkflowTemplate) => {
    setEditingId(template.id)
    form.setFieldsValue({
      name: template.name,
      steps: template.steps,
      source_mode: template.configuration.collection.source_mode,
      collection_limit: template.configuration.collection.limit,
      window_days: template.configuration.analysis.window_days,
      direction_number: template.configuration.lyrics.direction_index + 1,
      title_hint: template.configuration.lyrics.title_hint ?? undefined,
      theme: template.configuration.lyrics.theme ?? undefined,
      requirements: template.configuration.lyrics.requirements ?? undefined,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const canUseTemplate = (template: WorkflowTemplate) =>
    template.steps.every((step) => allowedSteps.has(step))

  const runTemplate = async (template: WorkflowTemplate) => {
    setRunningTemplateId(template.id)
    try {
      await startWorkflowRun(template.id)
      message.success('自动流程已经启动')
      await refreshRuns()
    } catch (runError) {
      message.error(errorMessage(runError))
    } finally {
      setRunningTemplateId(null)
    }
  }

  const removeTemplate = async (templateId: number) => {
    setDeletingId(templateId)
    try {
      await deleteWorkflowTemplate(templateId)
      message.success('流程已删除')
      if (editingId === templateId) resetEditor()
      await load()
    } catch (deleteError) {
      message.error(errorMessage(deleteError))
    } finally {
      setDeletingId(null)
    }
  }

  const activeTemplateIds = useMemo(
    () => new Set(
      runs
        .filter((run) => run.status === 'pending' || run.status === 'running')
        .map((run) => run.template_id)
        .filter((value): value is number => value !== null),
    ),
    [runs],
  )

  const templateColumns: TableProps<WorkflowTemplate>['columns'] = [
    {
      title: '流程',
      dataIndex: 'name',
      render: (name: string, template) => (
        <div className="account-cell">
          <strong>{name}</strong>
          <small>{template.created_by_username ?? '系统'} · {formatTime(template.updated_at)}</small>
        </div>
      ),
    },
    {
      title: '执行顺序',
      dataIndex: 'steps',
      render: (steps: WorkflowStepType[]) => (
        <span className="workflow-sequence">
          {steps.map((step) => WORKFLOW_STEP_LABELS[step]).join(' → ')}
        </span>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 190,
      fixed: 'right',
      render: (_, template) => (
        <Space size={2}>
          <Button
            type="primary"
            size="small"
            icon={<Play size={14} />}
            disabled={!canUseTemplate(template)}
            loading={runningTemplateId === template.id}
            onClick={() => void runTemplate(template)}
          >
            运行
          </Button>
          <Tooltip title="修改流程">
            <Button
              type="text"
              icon={<Pencil size={15} />}
              disabled={!canUseTemplate(template)}
              aria-label={`修改流程 ${template.name}`}
              onClick={() => editTemplate(template)}
            />
          </Tooltip>
          <Popconfirm
            title="删除这个流程？"
            description="已有运行记录会保留。"
            okText="删除"
            cancelText="取消"
            disabled={activeTemplateIds.has(template.id)}
            onConfirm={() => void removeTemplate(template.id)}
          >
            <Tooltip title={activeTemplateIds.has(template.id) ? '运行中不能删除' : '删除流程'}>
              <Button
                type="text"
                danger
                icon={<Trash2 size={15} />}
                loading={deletingId === template.id}
                disabled={activeTemplateIds.has(template.id)}
                aria-label={`删除流程 ${template.name}`}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const openStepResult = (step: WorkflowRunStep) => {
    if (!step.task_id) return
    if (step.step_type === 'collection') navigate('/rankings')
    if (step.step_type === 'analysis') navigate(`/analysis?task_id=${step.task_id}`)
    if (step.step_type === 'lyrics') navigate(`/lyrics?task_id=${step.task_id}`)
  }

  const runItems = runs.map((run) => {
    const statusMeta = STATUS_META[run.status]
    const template = templates.find((item) => item.id === run.template_id)
    const providerReason = typeof run.error_detail?.reason === 'string'
      ? run.error_detail.reason
      : null
    return {
      key: String(run.id),
      label: (
        <div className="workflow-run-summary">
          <div>
            <strong>#{run.id} · {run.template_name}</strong>
            <small>{run.requested_by_username ?? '未知账号'} · {formatTime(run.created_at)}</small>
          </div>
          <span>{run.current_step ? `当前：${WORKFLOW_STEP_LABELS[run.current_step]}` : `${run.steps.length} 个步骤`}</span>
          <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
        </div>
      ),
      children: (
        <div className="workflow-run-detail">
          {run.error_message && (
            <Alert
              type="error"
              showIcon
              title={run.error_message}
              description={[
                run.error_code ? `错误码：${run.error_code}` : null,
                providerReason,
              ].filter(Boolean).join(' · ') || undefined}
            />
          )}
          <Steps
            responsive
            items={run.steps.map((step) => ({
              title: WORKFLOW_STEP_LABELS[step.step_type],
              status: STATUS_META[step.status].stepStatus,
              description: (
                <span className="workflow-step-result">
                  <span>
                    {step.task_id
                      ? `任务 #${step.task_id}${step.output_id ? ` · 产出 #${step.output_id}` : ''}`
                      : STATUS_META[step.status].label}
                  </span>
                  {step.task_id && (
                    <Button type="link" size="small" onClick={() => openStepResult(step)}>
                      {step.status === 'completed' ? '查看产出' : '查看任务'}
                    </Button>
                  )}
                </span>
              ),
            }))}
          />
          <div className="workflow-run-footer">
            <Typography.Text type="secondary">
              开始 {formatTime(run.started_at)} · 完成 {formatTime(run.completed_at)}
            </Typography.Text>
            {template && (
              <Button
                icon={<Play size={15} />}
                disabled={!canUseTemplate(template)}
                loading={runningTemplateId === template.id}
                onClick={() => void runTemplate(template)}
              >
                再次运行
              </Button>
            )}
          </div>
        </div>
      ),
    }
  })

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>自动流程</Typography.Title>
          <Typography.Text type="secondary">选择步骤后，上一步产出会自动成为下一步输入</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon title={error} closable />}
      {allowedSteps.size === 0 && (
        <Alert type="warning" showIcon title="当前账号没有可用于自动流程的 Agent 权限" />
      )}

      <section className="content-section workflow-builder-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>{editingId ? '修改流程' : '配置新流程'}</Typography.Title>
            <Typography.Text type="secondary">步骤按数据依赖自动排序</Typography.Text>
          </div>
          {editingId && (
            <Button icon={<X size={15} />} onClick={resetEditor}>取消修改</Button>
          )}
        </div>
        <Form form={form} layout="vertical" requiredMark={false}>
          <div className="workflow-builder-surface">
            <Form.Item
              name="name"
              label="流程名称"
              rules={[{ required: true, whitespace: true, message: '请输入流程名称' }]}
            >
              <Input maxLength={100} placeholder="例如：完整创作流程" />
            </Form.Item>
            <Form.Item
              name="steps"
              label="流程步骤"
              rules={[{ required: true, message: '至少选择一个流程步骤' }]}
            >
              <WorkflowStepSelector allowedSteps={allowedSteps} />
            </Form.Item>
            <DataHandoffs steps={selectedSteps} />

            {selectedSteps.includes('collection') && (
              <div className="workflow-config-band">
                <div className="workflow-config-heading">
                  <BarChart3 size={17} />
                  <strong>榜单采集设置</strong>
                </div>
                <div className="form-grid">
                  <Form.Item name="source_mode" label="数据来源">
                    <Segmented
                      block
                      options={[
                        { label: '实时榜单', value: 'live' },
                        { label: '固定样例', value: 'sample' },
                      ]}
                    />
                  </Form.Item>
                  <Form.Item
                    name="collection_limit"
                    label="采集歌曲数"
                    rules={[{ required: true, message: '请输入采集数量' }]}
                  >
                    <InputNumber min={1} max={500} step={10} />
                  </Form.Item>
                </div>
              </div>
            )}

            {selectedSteps.includes('analysis') && (
              <div className="workflow-config-band">
                <div className="workflow-config-heading">
                  <ChartNoAxesCombined size={17} />
                  <strong>内容分析设置</strong>
                </div>
                <Form.Item name="window_days" label="趋势窗口">
                  <Segmented
                    options={[
                      { label: '3 天', value: 3 },
                      { label: '7 天', value: 7 },
                      { label: '14 天', value: 14 },
                      { label: '30 天', value: 30 },
                    ]}
                  />
                </Form.Item>
              </div>
            )}

            {selectedSteps.includes('lyrics') && (
              <div className="workflow-config-band">
                <div className="workflow-config-heading">
                  <FileMusic size={17} />
                  <strong>歌词创作设置</strong>
                </div>
                <div className="form-grid">
                  <Form.Item name="direction_number" label="使用创作方向">
                    <Segmented
                      block
                      options={[
                        { label: '方向 1', value: 1 },
                        { label: '方向 2', value: 2 },
                        { label: '方向 3', value: 3 },
                      ]}
                    />
                  </Form.Item>
                  <Form.Item name="title_hint" label="歌名方向">
                    <Input maxLength={200} placeholder="可留空自动生成" />
                  </Form.Item>
                  <Form.Item name="theme" label="歌曲主题">
                    <Input maxLength={500} placeholder="可留空使用分析主题" />
                  </Form.Item>
                </div>
                <Form.Item name="requirements" label="补充要求">
                  <Input.TextArea rows={3} maxLength={2000} />
                </Form.Item>
              </div>
            )}

            <Space wrap>
              <Button
                type="primary"
                icon={<Play size={16} />}
                loading={saveMode === 'run'}
                disabled={selectedSteps.length === 0}
                onClick={() => void saveTemplate(true)}
              >
                保存并运行
              </Button>
              <Button
                icon={<Save size={16} />}
                loading={saveMode === 'save'}
                disabled={selectedSteps.length === 0}
                onClick={() => void saveTemplate(false)}
              >
                {editingId ? '保存修改' : '仅保存流程'}
              </Button>
            </Space>
          </div>
        </Form>
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>已保存流程</Typography.Title>
            <Typography.Text type="secondary">常用流程可以直接运行或修改</Typography.Text>
          </div>
        </div>
        {loading ? <Skeleton active paragraph={{ rows: 3 }} /> : templates.length ? (
          <CollapsibleList items={templates} previewCount={4}>
            {(visibleTemplates) => (
              <Table<WorkflowTemplate>
                rowKey="id"
                columns={templateColumns}
                dataSource={visibleTemplates}
                pagination={false}
                scroll={{ x: 760 }}
                className="data-table"
              />
            )}
          </CollapsibleList>
        ) : (
          <div className="ranking-snapshot-empty">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无已保存流程" />
          </div>
        )}
      </section>

      <section className="content-section">
        <div className="section-title-row">
          <div>
            <Typography.Title level={2}>最近运行</Typography.Title>
            <Typography.Text type="secondary">任务编号和产出编号用于追踪整条数据链</Typography.Text>
          </div>
          <Tooltip title="刷新运行状态">
            <Button
              icon={<RefreshCw size={16} />}
              loading={refreshingRuns}
              onClick={() => void refreshRuns()}
            />
          </Tooltip>
        </div>
        {loading ? <Skeleton active paragraph={{ rows: 4 }} /> : runs.length ? (
          <CollapsibleList items={runItems} previewCount={5}>
            {(visibleItems) => (
              <Collapse
                accordion
                destroyOnHidden
                expandIconPlacement="end"
                className="workflow-run-list"
                items={visibleItems}
              />
            )}
          </CollapsibleList>
        ) : (
          <div className="ranking-snapshot-empty">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无流程运行记录" />
          </div>
        )}
      </section>
    </div>
  )
}
