import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Form,
  Grid,
  Input,
  InputNumber,
  Modal,
  Pagination,
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
  Cable,
  CheckCircle2,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  RotateCcw,
  Trash2,
} from 'lucide-react'

import {
  activateAiProviderConfig,
  createAiProviderConfig,
  deleteAiProviderConfig,
  importEnvironmentAiProvider,
  listAiProviderConfigs,
  listAiProviderTemplates,
  testAiProviderConfig,
  updateAiProviderConfig,
} from '../api/aiProviders'
import { errorMessage } from '../lib/errors'
import type {
  AiProviderConfig,
  AiProviderListResponse,
  AiProviderTemplate,
  AiProviderWritePayload,
  MaxTokensParameter,
  ProviderTestStatus,
} from '../types/api'


interface ProviderFormValues {
  name: string
  template_key: string
  base_url: string
  model: string
  api_key?: string
  supports_json_mode: boolean
  max_tokens_parameter: MaxTokensParameter
  request_timeout_seconds: number
  max_retries: number
  analysis_max_output_tokens: number
  lyrics_max_output_tokens: number
}

const TEST_STATUS: Record<
  ProviderTestStatus,
  { label: string; color: string }
> = {
  untested: { label: '未测试', color: 'default' },
  success: { label: '测试通过', color: 'success' },
  failed: { label: '测试失败', color: 'error' },
}

const PROVIDER_PAGE_SIZE = 8

function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

export function AiProvidersPage() {
  const { message } = App.useApp()
  const [templates, setTemplates] = useState<AiProviderTemplate[]>([])
  const [overview, setOverview] = useState<AiProviderListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<AiProviderConfig | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [action, setAction] = useState<{ id: number; type: string } | null>(null)
  const [importing, setImporting] = useState(false)
  const [providerPage, setProviderPage] = useState(1)
  const [form] = Form.useForm<ProviderFormValues>()
  const screens = Grid.useBreakpoint()
  const isMobile = screens.md === false
  const selectedTemplateKey = Form.useWatch('template_key', form)
  const selectedTemplate = useMemo(
    () => templates.find((item) => item.key === selectedTemplateKey),
    [selectedTemplateKey, templates],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [templateItems, providerOverview] = await Promise.all([
        listAiProviderTemplates(),
        listAiProviderConfigs(),
      ])
      setTemplates(templateItems)
      setOverview(providerOverview)
      setProviderPage((current) => Math.min(
        current,
        Math.max(1, Math.ceil(providerOverview.items.length / PROVIDER_PAGE_SIZE)),
      ))
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const fillTemplate = (templateKey: string) => {
    const template = templates.find((item) => item.key === templateKey)
    if (!template) return
    form.setFieldsValue({
      base_url: template.default_base_url,
      model: template.default_model,
      supports_json_mode: template.supports_json_mode,
      max_tokens_parameter: template.max_tokens_parameter,
    })
  }

  const openCreate = () => {
    const template = templates.find((item) => item.key === 'bigmodel') ?? templates[0]
    setEditing(null)
    form.setFieldsValue({
      name: '',
      template_key: template?.key ?? 'openai_compatible',
      base_url: template?.default_base_url ?? '',
      model: template?.default_model ?? '',
      api_key: '',
      supports_json_mode: template?.supports_json_mode ?? true,
      max_tokens_parameter: template?.max_tokens_parameter ?? 'max_tokens',
      request_timeout_seconds: 60,
      max_retries: 2,
      analysis_max_output_tokens: 2500,
      lyrics_max_output_tokens: 3500,
    })
    setModalOpen(true)
  }

  const openEdit = (provider: AiProviderConfig) => {
    setEditing(provider)
    form.setFieldsValue({
      name: provider.name,
      template_key: provider.template_key,
      base_url: provider.base_url,
      model: provider.model,
      api_key: '',
      supports_json_mode: provider.supports_json_mode,
      max_tokens_parameter: provider.max_tokens_parameter,
      request_timeout_seconds: provider.request_timeout_seconds,
      max_retries: provider.max_retries,
      analysis_max_output_tokens: provider.analysis_max_output_tokens,
      lyrics_max_output_tokens: provider.lyrics_max_output_tokens,
    })
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setEditing(null)
    form.resetFields()
  }

  const saveProvider = async () => {
    const values = await form.validateFields()
    const payload: AiProviderWritePayload = {
      ...values,
      name: values.name.trim(),
      base_url: values.base_url?.trim(),
      model: values.model?.trim(),
    }
    if (!values.api_key?.trim()) delete payload.api_key
    if (selectedTemplate?.protocol === 'local') {
      delete payload.api_key
      delete payload.base_url
      delete payload.model
    }
    setSaving(true)
    try {
      if (editing) await updateAiProviderConfig(editing.id, payload)
      else await createAiProviderConfig(payload)
      message.success(editing ? '接口配置已更新，请重新测试' : '接口配置已创建')
      closeModal()
      await load()
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const runAction = async (
    provider: AiProviderConfig,
    type: 'test' | 'activate' | 'delete',
  ) => {
    setAction({ id: provider.id, type })
    try {
      if (type === 'test') {
        const result = await testAiProviderConfig(provider.id)
        if (result.status === 'success') {
          message.success(`连接成功，本次测试使用 ${result.api_usage.total_tokens} Token`)
        } else {
          message.error(result.message)
        }
      } else if (type === 'activate') {
        await activateAiProviderConfig(provider.id)
        message.success(`已切换到 ${provider.name}`)
      } else {
        await deleteAiProviderConfig(provider.id)
        message.success('接口配置已删除')
      }
      await load()
    } catch (actionError) {
      message.error(errorMessage(actionError))
    } finally {
      setAction(null)
    }
  }

  const importEnvironment = async () => {
    setImporting(true)
    try {
      await importEnvironmentAiProvider()
      message.success('当前环境配置已导入')
      await load()
    } catch (importError) {
      message.error(errorMessage(importError))
    } finally {
      setImporting(false)
    }
  }

  const providerItems = overview?.items ?? []
  const visibleMobileProviders = providerItems.slice(
    (providerPage - 1) * PROVIDER_PAGE_SIZE,
    providerPage * PROVIDER_PAGE_SIZE,
  )
  const activeProvider = providerItems.find((item) => item.is_active)
  const runtime = activeProvider ?? overview?.environment_fallback
  const environmentImported = overview?.items.some((item) => item.source === 'environment')

  const columns: TableProps<AiProviderConfig>['columns'] = [
    {
      title: '连接配置',
      key: 'name',
      fixed: 'left',
      width: 210,
      render: (_, provider) => (
        <div className="account-cell provider-name-cell">
          <strong>{provider.name}</strong>
          <span>
            <Tag>{provider.template_name}</Tag>
            {provider.source === 'environment' && <Tag color="blue">环境导入</Tag>}
          </span>
        </div>
      ),
    },
    {
      title: '模型 / 接口',
      key: 'endpoint',
      render: (_, provider) => (
        <div className="account-cell api-usage-cell">
          <strong>{provider.model}</strong>
          <small>{provider.endpoint}</small>
        </div>
      ),
    },
    {
      title: '密钥',
      dataIndex: 'api_key_hint',
      key: 'key',
      width: 120,
      render: (hint: string | null, provider) =>
        provider.protocol === 'local' ? <span className="muted-copy">不需要</span> : hint ?? '已保存',
    },
    {
      title: '连接测试',
      key: 'test',
      width: 150,
      render: (_, provider) => {
        const status = TEST_STATUS[provider.last_test_status]
        return (
          <Tooltip title={provider.last_test_message ?? undefined}>
            <div className="provider-test-cell">
              <Tag color={status.color}>{status.label}</Tag>
              <small>{formatDateTime(provider.last_tested_at)}</small>
            </div>
          </Tooltip>
        )
      },
    },
    {
      title: '运行状态',
      key: 'active',
      width: 100,
      render: (_, provider) =>
        provider.is_active ? (
          <Tag color="success" icon={<CheckCircle2 size={13} />}>当前使用</Tag>
        ) : (
          <span className="muted-copy">待命</span>
        ),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 184,
      render: (_, provider) => {
        const busy = action?.id === provider.id
        return (
          <Space size={2}>
            <Tooltip title="测试连接">
              <Button
                type="text"
                icon={<Cable size={17} />}
                aria-label="测试连接"
                loading={busy && action.type === 'test'}
                onClick={() => void runAction(provider, 'test')}
              />
            </Tooltip>
            {!provider.is_active && (
              <Popconfirm
                title={`切换到 ${provider.name}？`}
                onConfirm={() => void runAction(provider, 'activate')}
                okText="切换"
                cancelText="取消"
              >
                <Tooltip title="设为当前接口">
                  <Button
                    type="text"
                    icon={<Power size={17} />}
                    aria-label="设为当前接口"
                    disabled={provider.last_test_status !== 'success'}
                    loading={busy && action.type === 'activate'}
                  />
                </Tooltip>
              </Popconfirm>
            )}
            <Tooltip title={provider.is_active ? '使用中的接口不可编辑' : '编辑配置'}>
              <Button
                type="text"
                icon={<Pencil size={17} />}
                aria-label="编辑配置"
                disabled={provider.is_active}
                onClick={() => openEdit(provider)}
              />
            </Tooltip>
            <Popconfirm
              title="删除此接口配置？"
              onConfirm={() => void runAction(provider, 'delete')}
              okText="删除"
              cancelText="取消"
              disabled={provider.is_active}
            >
              <Tooltip title={provider.is_active ? '使用中的接口不可删除' : '删除配置'}>
                <Button
                  type="text"
                  danger
                  icon={<Trash2 size={17} />}
                  aria-label="删除配置"
                  disabled={provider.is_active}
                  loading={busy && action.type === 'delete'}
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
          <Typography.Title level={1}>AI 接口</Typography.Title>
          <Typography.Text type="secondary">文本模型连接与运行时切换</Typography.Text>
        </div>
        <Space>
          <Tooltip title="刷新接口列表">
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load} />
          </Tooltip>
          <Button type="primary" icon={<Plus size={17} />} onClick={openCreate}>
            新建接口
          </Button>
        </Space>
      </div>

      {error && <Alert type="error" showIcon title={error} />}

      <section className="provider-runtime-band" aria-label="当前运行接口">
        <span className="provider-runtime-icon"><Power size={18} /></span>
        <div>
          <small>当前运行接口</small>
          <strong>{activeProvider?.name ?? runtime?.template_name ?? '未配置'}</strong>
          <span>{runtime?.model || '—'} · {runtime?.endpoint || '—'}</span>
        </div>
        <Tag color={activeProvider ? 'success' : 'blue'}>
          {activeProvider ? '数据库配置' : '环境变量后备'}
        </Tag>
        {!activeProvider && overview?.environment_fallback.configured && !environmentImported && (
          <Button
            icon={<RotateCcw size={16} />}
            loading={importing}
            onClick={() => void importEnvironment()}
          >
            导入当前配置
          </Button>
        )}
      </section>

      {isMobile ? (
        <>
          <div className="provider-mobile-list">
            {visibleMobileProviders.map((provider) => {
              const testStatus = TEST_STATUS[provider.last_test_status]
              const busy = action?.id === provider.id
              return (
                <article className="provider-mobile-item" key={provider.id}>
                  <div className="provider-mobile-heading">
                    <div>
                      <strong>{provider.name}</strong>
                      <span>{provider.template_name} · {provider.model}</span>
                    </div>
                    {provider.is_active && <Tag color="success">当前使用</Tag>}
                  </div>
                  <div className="provider-mobile-endpoint">{provider.endpoint}</div>
                  <div className="provider-mobile-meta">
                    <span>密钥 {provider.api_key_hint ?? '不需要'}</span>
                    <Tag color={testStatus.color}>{testStatus.label}</Tag>
                  </div>
                  <div className="provider-mobile-actions">
                    <Button
                      icon={<Cable size={16} />}
                      loading={busy && action.type === 'test'}
                      onClick={() => void runAction(provider, 'test')}
                    >
                      测试
                    </Button>
                    {!provider.is_active && (
                      <Popconfirm
                        title={`切换到 ${provider.name}？`}
                        onConfirm={() => void runAction(provider, 'activate')}
                        okText="切换"
                        cancelText="取消"
                      >
                        <Button
                          icon={<Power size={16} />}
                          disabled={provider.last_test_status !== 'success'}
                          loading={busy && action.type === 'activate'}
                        >
                          启用
                        </Button>
                      </Popconfirm>
                    )}
                    <Tooltip title={provider.is_active ? '使用中的接口不可编辑' : '编辑配置'}>
                      <Button
                        icon={<Pencil size={16} />}
                        aria-label="编辑配置"
                        disabled={provider.is_active}
                        onClick={() => openEdit(provider)}
                      />
                    </Tooltip>
                    <Popconfirm
                      title="删除此接口配置？"
                      onConfirm={() => void runAction(provider, 'delete')}
                      okText="删除"
                      cancelText="取消"
                      disabled={provider.is_active}
                    >
                      <Button
                        danger
                        icon={<Trash2 size={16} />}
                        aria-label="删除配置"
                        disabled={provider.is_active}
                        loading={busy && action.type === 'delete'}
                      />
                    </Popconfirm>
                  </div>
                </article>
              )
            })}
          </div>
          {providerItems.length > PROVIDER_PAGE_SIZE && (
            <Pagination
              className="provider-pagination"
              current={providerPage}
              pageSize={PROVIDER_PAGE_SIZE}
              total={providerItems.length}
              showSizeChanger={false}
              onChange={setProviderPage}
            />
          )}
        </>
      ) : (
        <Table<AiProviderConfig>
          rowKey="id"
          columns={columns}
          dataSource={providerItems}
          loading={loading}
          pagination={{
            current: providerPage,
            pageSize: PROVIDER_PAGE_SIZE,
            showSizeChanger: false,
            hideOnSinglePage: true,
            onChange: setProviderPage,
          }}
          scroll={{ x: 980 }}
          locale={{ emptyText: '暂无数据库接口配置' }}
          rowClassName={(provider) => provider.is_active ? 'provider-active-row' : ''}
        />
      )}

      <Modal
        title={editing ? `编辑接口 · ${editing.name}` : '新建 AI 接口'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => void saveProvider()}
        confirmLoading={saving}
        okText={editing ? '保存配置' : '创建配置'}
        cancelText="取消"
        width={720}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <div className="provider-form-grid">
            <Form.Item
              name="name"
              label="配置名称"
              rules={[{ required: true, min: 2, max: 80, message: '请输入 2 至 80 位名称' }]}
            >
              <Input autoComplete="off" placeholder="例如 智谱主账号" />
            </Form.Item>
            <Form.Item
              name="template_key"
              label="接口模板"
              rules={[{ required: true, message: '请选择接口模板' }]}
            >
              <Select
                options={templates.map((template) => ({
                  label: template.display_name,
                  value: template.key,
                }))}
                onChange={fillTemplate}
              />
            </Form.Item>
          </div>

          {selectedTemplate?.protocol !== 'local' && (
            <>
              <Form.Item
                name="base_url"
                label="Base URL"
                rules={[{ required: true, type: 'url', message: '请输入有效的 HTTP(S) 地址' }]}
              >
                <Input autoComplete="off" />
              </Form.Item>
              <div className="provider-form-grid">
                <Form.Item
                  name="model"
                  label="模型名称"
                  rules={[{ required: true, message: '请输入模型名称' }]}
                >
                  <Input autoComplete="off" />
                </Form.Item>
                <Form.Item
                  name="api_key"
                  label={editing ? `API Key · ${editing.api_key_hint ?? '已保存'}` : 'API Key'}
                  rules={editing ? [] : [{ required: true, message: '请输入 API Key' }]}
                >
                  <Input.Password autoComplete="new-password" placeholder={editing ? '留空保留原密钥' : ''} />
                </Form.Item>
              </div>
            </>
          )}

          <div className="provider-advanced-heading">请求参数</div>
          <div className="provider-form-grid provider-form-grid-compact">
            <Form.Item name="supports_json_mode" label="JSON 模式" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="max_tokens_parameter" label="最大 Token 参数">
              <Select
                options={[
                  { label: 'max_tokens', value: 'max_tokens' },
                  { label: 'max_completion_tokens', value: 'max_completion_tokens' },
                ]}
              />
            </Form.Item>
            <Form.Item name="request_timeout_seconds" label="超时（秒）">
              <InputNumber min={5} max={600} />
            </Form.Item>
            <Form.Item name="max_retries" label="最大尝试次数">
              <InputNumber min={1} max={5} />
            </Form.Item>
            <Form.Item name="analysis_max_output_tokens" label="分析输出上限">
              <InputNumber min={128} max={100000} />
            </Form.Item>
            <Form.Item name="lyrics_max_output_tokens" label="作词输出上限">
              <InputNumber min={128} max={100000} />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  )
}
