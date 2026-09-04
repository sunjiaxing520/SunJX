import { useCallback, useEffect, useState, type Key } from 'react'
import {
  Alert,
  App,
  Button,
  Collapse,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import {
  Archive,
  Ban,
  BrainCircuit,
  CheckCircle2,
  Database,
  Eye,
  FileClock,
  MessageSquareText,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Send,
  Trash2,
} from 'lucide-react'

import {
  applyLyricsMemoryChatProposal,
  createLyricsMemoryRule,
  createLyricsMemorySnapshot,
  deleteLyricsMemoryEvent,
  deleteLyricsMemoryEvents,
  deleteLyricsMemorySnapshot,
  distillNextLegacyLyricsMemory,
  getLyricsMemoryEvent,
  getLyricsMemoryOverview,
  getLyricsMemoryPreview,
  getLyricsMemorySnapshot,
  listLyricsMemoryChat,
  listLyricsMemoryEvents,
  listLyricsMemorySnapshots,
  renameLyricsMemorySnapshot,
  requestLyricsMemoryChatPreview,
  setLyricsMemoryUsefulness,
} from '../api/lyricsMemory'
import { errorMessage } from '../lib/errors'
import type {
  LyricsMemoryChatMessage,
  LyricsMemoryEventDetail,
  LyricsMemoryEventSummary,
  LyricsMemoryEventType,
  LyricsMemoryOperation,
  LyricsMemoryOverview,
  LyricsMemoryPreview,
  LyricsMemorySnapshotDetail,
  LyricsMemorySnapshotSummary,
} from '../types/api'


const EVENT_META: Record<
  LyricsMemoryEventType,
  { label: string; color: string }
> = {
  creation_request: { label: '创作原始证据', color: 'blue' },
  modification_request: { label: '修改原始证据', color: 'purple' },
  prompt_essence: { label: '团队提示词精华', color: 'cyan' },
  accepted_result: { label: '确认结果', color: 'green' },
  ranking_lyrics_insight: { label: '榜单歌词规律', color: 'gold' },
  admin_rule: { label: '管理员规则', color: 'volcano' },
}

const MEMORY_SECTIONS = [
  { key: 'admin_rules', label: '管理员固定规则' },
  { key: 'team_prompt_essences', label: '团队提示词精华' },
  { key: '1_true_creation_requirements', label: '1. 已确认创作需求提炼' },
  { key: '2_true_modification_requirements', label: '2. 已确认修改需求提炼' },
  { key: '3_requirement_context', label: '3. 经验形成场景' },
  { key: '4_creation_distillation_expert', label: '4. 有效创作经验' },
  { key: '5_ranking_lyrics_patterns', label: '5. 榜单歌词规律' },
] as const

const OPERATION_LABELS: Record<LyricsMemoryOperation['action'], string> = {
  add_rule: '新增固定规则',
  update_rule: '修改固定规则',
  disable_event: '停用记忆',
  enable_event: '恢复记忆',
}

const PAGE_SIZE = 15

const MEMORY_FIELD_LABELS: Record<string, string> = {
  task: '用途',
  task_id: '任务',
  title: '歌名',
  rule: '规则内容',
  source: '来源',
  source_kind: '形成阶段',
  theme: '主题',
  genre_tags: '风格',
  mood_tags: '情绪',
  available: '是否已有经验',
  requirement_summary: '提示词精华',
  prompt_essence: '提示词精华',
  strategy_summary: '采用方法',
  result_summary: '有效结果',
  reusable_patterns: '可复用经验',
  highlight_summary: '亮点总结',
  accepted_evidence: '已确认的提炼经验',
  items: '规律条目',
  summary: '总结',
  scope: '使用范围',
  source_event_count: '来源记录数',
  merged_item_count: '合并后精华数',
  included_item_count: '本次注入数',
  is_compacted: '是否已压缩',
  source_account_count: '来源账号数',
  use_count: '出现次数',
  themes: '相关主题',
  source_kinds: '形成阶段',
}

function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

function memorySectionCount(value: unknown): number {
  if (Array.isArray(value)) return value.length
  if (value && typeof value === 'object') {
    const evidence = (value as Record<string, unknown>).accepted_evidence
    const items = (value as Record<string, unknown>).items
    if (Array.isArray(evidence)) return evidence.length
    if (Array.isArray(items)) return items.length
  }
  return value ? 1 : 0
}

function memoryFieldLabel(key: string): string {
  return MEMORY_FIELD_LABELS[key] ?? key
}

function isTraceOnlyEvent(eventType: LyricsMemoryEventType): boolean {
  return eventType === 'creation_request' || eventType === 'modification_request'
}

function MemoryValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') {
    return <Typography.Text type="secondary">暂无内容</Typography.Text>
  }
  if (value === 'initial_creation') return <span>首次创作</span>
  if (value === 'revision') return <span>确认修改</span>
  if (value === 'all_accounts') return <span>全部账号共享</span>
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>
  if (typeof value === 'string' || typeof value === 'number') return <span>{value}</span>
  if (Array.isArray(value)) {
    if (!value.length) return <Typography.Text type="secondary">暂无内容</Typography.Text>
    return (
      <div className="lyrics-memory-value-list">
        {value.map((item, index) => (
          <div className="lyrics-memory-value-item" key={index}>
            <MemoryValue value={item} />
          </div>
        ))}
      </div>
    )
  }
  return (
    <div className="lyrics-memory-field-list">
      {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
        <div className="lyrics-memory-field" key={key}>
          <strong>{memoryFieldLabel(key)}</strong>
          <div><MemoryValue value={item} /></div>
        </div>
      ))}
    </div>
  )
}

function MemoryCapsuleView({ memory }: { memory: Record<string, unknown> }) {
  return (
    <Collapse
      className="lyrics-memory-capsule"
      items={MEMORY_SECTIONS.map((section) => {
        const value = memory[section.key]
        return {
          key: section.key,
          label: (
            <span className="lyrics-memory-section-label">
              <strong>{section.label}</strong>
              <Tag>{memorySectionCount(value)} 项</Tag>
            </span>
          ),
          children: <MemoryValue value={value} />,
        }
      })}
    />
  )
}

function OperationList({ operations }: { operations: LyricsMemoryOperation[] }) {
  if (!operations.length) {
    return <Typography.Text type="secondary">本次没有需要应用的改动</Typography.Text>
  }
  return (
    <div className="lyrics-memory-operation-list">
      {operations.map((operation, index) => (
        <div className="lyrics-memory-operation" key={`${operation.action}-${index}`}>
          <Tag color="blue">{OPERATION_LABELS[operation.action]}</Tag>
          <div>
            <strong>{operation.title || (operation.event_id ? `记忆 #${operation.event_id}` : '新规则')}</strong>
            {operation.content && <span>{operation.content}</span>}
            <small>{operation.reason}</small>
          </div>
        </div>
      ))}
    </div>
  )
}

export function LyricsMemoryPage() {
  const { message } = App.useApp()
  const [overview, setOverview] = useState<LyricsMemoryOverview | null>(null)
  const [events, setEvents] = useState<LyricsMemoryEventSummary[]>([])
  const [eventTotal, setEventTotal] = useState(0)
  const [chatMessages, setChatMessages] = useState<LyricsMemoryChatMessage[]>([])
  const [snapshots, setSnapshots] = useState<LyricsMemorySnapshotSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [eventLoading, setEventLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('memory')
  const [eventType, setEventType] = useState<'all' | LyricsMemoryEventType>('all')
  const [usefulness, setUsefulness] = useState<'all' | 'active' | 'inactive'>('all')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Key[]>([])
  const [detail, setDetail] = useState<LyricsMemoryEventDetail | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [preview, setPreview] = useState<LyricsMemoryPreview | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [distillingLegacy, setDistillingLegacy] = useState(false)
  const [actionId, setActionId] = useState<number | null>(null)
  const [deletingMany, setDeletingMany] = useState(false)
  const [ruleOpen, setRuleOpen] = useState(false)
  const [savingRule, setSavingRule] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatting, setChatting] = useState(false)
  const [applyingMessageId, setApplyingMessageId] = useState<number | null>(null)
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false)
  const [snapshotEditing, setSnapshotEditing] = useState<LyricsMemorySnapshotSummary | null>(null)
  const [savingSnapshot, setSavingSnapshot] = useState(false)
  const [snapshotDetail, setSnapshotDetail] = useState<LyricsMemorySnapshotDetail | null>(null)
  const [snapshotDrawerOpen, setSnapshotDrawerOpen] = useState(false)
  const [snapshotDetailLoading, setSnapshotDetailLoading] = useState(false)
  const [ruleForm] = Form.useForm<{ title: string; content: string }>()
  const [snapshotForm] = Form.useForm<{ name: string }>()

  const loadOverview = useCallback(async () => {
    setOverview(await getLyricsMemoryOverview())
  }, [])

  const loadEvents = useCallback(async () => {
    setEventLoading(true)
    try {
      const result = await listLyricsMemoryEvents({
        eventType: eventType === 'all' ? undefined : eventType,
        isUseful: usefulness === 'all' ? undefined : usefulness === 'active',
        search,
        page,
        pageSize: PAGE_SIZE,
      })
      setEvents(result.items)
      setEventTotal(result.total)
      setSelectedIds([])
    } finally {
      setEventLoading(false)
    }
  }, [eventType, page, search, usefulness])

  const loadChat = useCallback(async () => {
    const result = await listLyricsMemoryChat()
    setChatMessages(result.items)
  }, [])

  const loadSnapshots = useCallback(async () => {
    const result = await listLyricsMemorySnapshots()
    setSnapshots(result.items)
  }, [])

  const loadPreview = useCallback(async () => {
    setPreviewLoading(true)
    try {
      const result = await getLyricsMemoryPreview()
      setPreview(result)
      return result
    } finally {
      setPreviewLoading(false)
    }
  }, [])

  const loadInitial = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([loadOverview(), loadChat(), loadSnapshots(), loadPreview()])
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [loadChat, loadOverview, loadPreview, loadSnapshots])

  useEffect(() => {
    void loadInitial()
  }, [loadInitial])

  useEffect(() => {
    loadEvents().catch((loadError) => setError(errorMessage(loadError)))
  }, [loadEvents])

  const refreshAll = async () => {
    setError(null)
    try {
      await Promise.all([loadOverview(), loadEvents(), loadChat(), loadSnapshots(), loadPreview()])
      message.success('歌词记忆已刷新')
    } catch (refreshError) {
      setError(errorMessage(refreshError))
    }
  }

  const openDetail = async (eventId: number) => {
    setDetailOpen(true)
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await getLyricsMemoryEvent(eventId))
    } catch (detailError) {
      message.error(errorMessage(detailError))
      setDetailOpen(false)
    } finally {
      setDetailLoading(false)
    }
  }

  const openPreview = async () => {
    setPreviewOpen(true)
    try {
      await loadPreview()
    } catch (previewError) {
      message.error(errorMessage(previewError))
      setPreviewOpen(false)
    }
  }

  const distillNextLegacy = async () => {
    setDistillingLegacy(true)
    try {
      const result = await distillNextLegacyLyricsMemory()
      await Promise.all([loadPreview(), loadOverview(), loadEvents()])
      if (result.processed_count > 0) {
        message.success(`已提炼 1 条历史确认结果，剩余 ${result.pending_legacy_count} 条`)
      } else {
        message.info('已没有待提炼的历史结果')
      }
    } catch (distillError) {
      message.error(errorMessage(distillError))
    } finally {
      setDistillingLegacy(false)
    }
  }

  const toggleUsefulness = async (eventId: number, isUseful: boolean) => {
    setActionId(eventId)
    try {
      const updated = await setLyricsMemoryUsefulness(eventId, isUseful)
      setEvents((current) => current.map((event) => event.id === eventId ? updated : event))
      if (detail?.id === eventId) setDetail(updated)
      await loadOverview()
      message.success(isUseful ? '记忆已恢复' : '记忆已停用')
    } catch (actionError) {
      message.error(errorMessage(actionError))
    } finally {
      setActionId(null)
    }
  }

  const removeEvent = async (eventId: number) => {
    setActionId(eventId)
    try {
      await deleteLyricsMemoryEvent(eventId)
      if (detail?.id === eventId) setDetailOpen(false)
      await Promise.all([loadOverview(), loadEvents()])
      message.success('记忆已删除')
    } catch (actionError) {
      message.error(errorMessage(actionError))
    } finally {
      setActionId(null)
    }
  }

  const removeSelected = async () => {
    const ids = selectedIds.map(Number)
    setDeletingMany(true)
    try {
      await deleteLyricsMemoryEvents(ids)
      await Promise.all([loadOverview(), loadEvents()])
      message.success(`已删除 ${ids.length} 条记忆`)
    } catch (actionError) {
      message.error(errorMessage(actionError))
    } finally {
      setDeletingMany(false)
    }
  }

  const saveRule = async () => {
    const values = await ruleForm.validateFields()
    setSavingRule(true)
    try {
      await createLyricsMemoryRule(values.title.trim(), values.content.trim())
      setRuleOpen(false)
      ruleForm.resetFields()
      await Promise.all([loadOverview(), loadEvents()])
      message.success('固定规则已加入歌词记忆')
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSavingRule(false)
    }
  }

  const sendChat = async () => {
    const instruction = chatInput.trim()
    if (!instruction) return
    setChatting(true)
    try {
      await requestLyricsMemoryChatPreview(instruction)
      setChatInput('')
      await loadChat()
    } catch (chatError) {
      message.error(errorMessage(chatError))
    } finally {
      setChatting(false)
    }
  }

  const applyProposal = async (messageId: number) => {
    setApplyingMessageId(messageId)
    try {
      await applyLyricsMemoryChatProposal(messageId)
      await Promise.all([loadChat(), loadOverview(), loadEvents()])
      message.success('记忆调整方案已应用')
    } catch (applyError) {
      message.error(errorMessage(applyError))
    } finally {
      setApplyingMessageId(null)
    }
  }

  const openSnapshotCreate = () => {
    setSnapshotEditing(null)
    snapshotForm.resetFields()
    setSnapshotModalOpen(true)
  }

  const openSnapshotRename = (snapshot: LyricsMemorySnapshotSummary) => {
    setSnapshotEditing(snapshot)
    snapshotForm.setFieldsValue({ name: snapshot.name })
    setSnapshotModalOpen(true)
  }

  const saveSnapshot = async () => {
    const values = await snapshotForm.validateFields()
    setSavingSnapshot(true)
    try {
      if (snapshotEditing) {
        await renameLyricsMemorySnapshot(snapshotEditing.id, values.name.trim())
        message.success('保留记忆已改名')
      } else {
        await createLyricsMemorySnapshot(values.name.trim())
        message.success('当前歌词记忆已保留')
      }
      setSnapshotModalOpen(false)
      snapshotForm.resetFields()
      await loadSnapshots()
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSavingSnapshot(false)
    }
  }

  const openSnapshotDetail = async (snapshotId: number) => {
    setSnapshotDrawerOpen(true)
    setSnapshotDetailLoading(true)
    setSnapshotDetail(null)
    try {
      setSnapshotDetail(await getLyricsMemorySnapshot(snapshotId))
    } catch (snapshotError) {
      message.error(errorMessage(snapshotError))
      setSnapshotDrawerOpen(false)
    } finally {
      setSnapshotDetailLoading(false)
    }
  }

  const removeSnapshot = async (snapshotId: number) => {
    try {
      await deleteLyricsMemorySnapshot(snapshotId)
      await loadSnapshots()
      message.success('保留记忆已删除')
    } catch (snapshotError) {
      message.error(errorMessage(snapshotError))
    }
  }

  const columns: TableProps<LyricsMemoryEventSummary>['columns'] = [
    {
      title: '类型',
      dataIndex: 'event_type',
      width: 132,
      render: (value: LyricsMemoryEventType) => (
        <Tag color={EVENT_META[value].color}>{EVENT_META[value].label}</Tag>
      ),
    },
    {
      title: '证据摘要',
      dataIndex: 'content_preview',
      render: (value: string, event) => (
        <button className="lyrics-memory-summary-button" onClick={() => void openDetail(event.id)}>
          <strong>{value || '无有效摘要'}</strong>
          <small>
            {event.task_id ? `任务 #${event.task_id}` : '团队规则'}
            {event.source_version_id ? ` · 歌词 #${event.source_version_id}` : ''}
          </small>
        </button>
      ),
    },
    {
      title: '记录人',
      dataIndex: 'created_by_username',
      width: 112,
      render: (value: string | null) => value ?? '历史数据',
    },
    {
      title: '记忆状态',
      dataIndex: 'is_useful',
      width: 92,
      render: (value: boolean, event) => isTraceOnlyEvent(event.event_type) ? (
        <Tag>仅追溯</Tag>
      ) : (
        <Tooltip title={value ? '停用后不再注入模型' : '恢复到隐藏记忆'}>
          <Switch
            size="small"
            checked={value}
            loading={actionId === event.id}
            aria-label={value ? '停用记忆' : '恢复记忆'}
            onChange={(checked) => void toggleUsefulness(event.id, checked)}
          />
        </Tooltip>
      ),
    },
    {
      title: '记录时间',
      dataIndex: 'created_at',
      width: 170,
      render: formatDateTime,
    },
    {
      title: '操作',
      key: 'actions',
      width: 92,
      fixed: 'right',
      render: (_, event) => (
        <Space size={2}>
          <Tooltip title="查看完整证据">
            <Button
              type="text"
              icon={<Eye size={16} />}
              aria-label="查看完整证据"
              onClick={() => void openDetail(event.id)}
            />
          </Tooltip>
          <Popconfirm
            title="永久删除这条证据？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => void removeEvent(event.id)}
          >
            <Tooltip title="删除证据">
              <Button
                type="text"
                danger
                icon={<Trash2 size={16} />}
                loading={actionId === event.id}
                aria-label="删除证据"
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const categoryOptions = [
    { label: `全部 ${overview?.total_events ?? 0}`, value: 'all' },
    ...Object.entries(EVENT_META).map(([value, meta]) => ({
      label: `${meta.label} ${overview?.category_counts[value] ?? 0}`,
      value,
    })),
  ]

  const currentMemoryPanel = (
    <div className="lyrics-memory-current-panel">
      <div className="lyrics-memory-current-heading">
        <div>
          <Typography.Title level={2}>当前提炼记忆</Typography.Title>
          <Typography.Text type="secondary">
            只展示从用户已确认歌词中提炼的需求、方法和有效结果
          </Typography.Text>
        </div>
        <Space wrap>
          {(preview?.pending_legacy_count ?? 0) > 0 && (
            <Button
              icon={<BrainCircuit size={16} />}
              loading={distillingLegacy}
              onClick={() => void distillNextLegacy()}
            >
              提炼下一条历史结果
            </Button>
          )}
          <Button icon={<Eye size={16} />} onClick={() => void openPreview()}>
            抽屉查看
          </Button>
        </Space>
      </div>
      <div className="lyrics-memory-current-summary">
        <div><span>已形成提炼记忆</span><strong>{preview?.distilled_insight_count ?? 0}</strong></div>
        <div><span>历史待提炼</span><strong>{preview?.pending_legacy_count ?? 0}</strong></div>
        <div><span>当前注入字符</span><strong>{(preview?.capsule_char_count ?? 0).toLocaleString()}</strong></div>
      </div>
      {(preview?.pending_legacy_count ?? 0) > 0 && (
        <Alert
          type="warning"
          showIcon
          title={`${preview?.pending_legacy_count} 条历史确认结果还没有结构化提炼，当前不会注入 AI`}
        />
      )}
      {preview ? (
        <MemoryCapsuleView memory={preview.memory} />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={previewLoading ? '正在读取提炼记忆' : '暂无提炼记忆'} />
      )}
    </div>
  )

  const eventPanel = (
    <div className="lyrics-memory-panel">
      <div className="lyrics-memory-filter-row">
        <div className="lyrics-memory-category-strip">
          <Radio.Group
            optionType="button"
            buttonStyle="solid"
            value={eventType}
            options={categoryOptions}
            onChange={(event) => {
              setEventType(event.target.value)
              setPage(1)
            }}
          />
        </div>
        <Space wrap>
          <Select
            value={usefulness}
            style={{ width: 116 }}
            options={[
              { label: '全部状态', value: 'all' },
              { label: '使用中', value: 'active' },
              { label: '已停用', value: 'inactive' },
            ]}
            onChange={(value) => {
              setUsefulness(value)
              setPage(1)
            }}
          />
          <Input.Search
            value={searchInput}
            allowClear
            placeholder="搜索原始证据"
            style={{ width: 220 }}
            onChange={(event) => setSearchInput(event.target.value)}
            onSearch={(value) => {
              setSearch(value.trim())
              setPage(1)
            }}
          />
        </Space>
      </div>

      {selectedIds.length > 0 && (
        <div className="lyrics-memory-bulk-bar">
          <span>已选择 {selectedIds.length} 条</span>
          <Popconfirm
            title={`永久删除选中的 ${selectedIds.length} 条证据？`}
            okText="删除"
            cancelText="取消"
            onConfirm={() => void removeSelected()}
          >
            <Button danger icon={<Trash2 size={16} />} loading={deletingMany}>
              批量删除
            </Button>
          </Popconfirm>
        </div>
      )}

      <Table<LyricsMemoryEventSummary>
        rowKey="id"
        columns={columns}
        dataSource={events}
        loading={eventLoading}
        rowSelection={{ selectedRowKeys: selectedIds, onChange: setSelectedIds }}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: eventTotal,
          showSizeChanger: false,
          hideOnSinglePage: true,
          onChange: setPage,
        }}
        scroll={{ x: 980 }}
        locale={{ emptyText: '暂无符合条件的原始证据' }}
        className="lyrics-memory-table"
      />
    </div>
  )

  const chatPanel = (
    <div className="lyrics-memory-chat-panel">
      <div className="lyrics-memory-chat-history">
        {chatMessages.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无记忆调整对话" />
        ) : (
          chatMessages.map((chatMessage) => (
            <article
              className={`lyrics-memory-chat-message ${chatMessage.role}`}
              key={chatMessage.id}
            >
              <div className="lyrics-memory-chat-meta">
                <strong>{chatMessage.role === 'user' ? '管理员' : '记忆助手'}</strong>
                <span>{formatDateTime(chatMessage.created_at)}</span>
              </div>
              <Typography.Paragraph>{chatMessage.content}</Typography.Paragraph>
              {chatMessage.proposal && (
                <div className="lyrics-memory-proposal">
                  <Collapse
                    ghost
                    items={[
                      {
                        key: 'operations',
                        label: `调整方案 · ${chatMessage.proposal.operations.length} 项`,
                        children: <OperationList operations={chatMessage.proposal.operations} />,
                      },
                    ]}
                  />
                  <div className="lyrics-memory-proposal-action">
                    {chatMessage.is_applied ? (
                      <Tag color="success" icon={<CheckCircle2 size={13} />}>已应用</Tag>
                    ) : (
                      <Popconfirm
                        title="确认应用这份记忆调整方案？"
                        okText="应用"
                        cancelText="取消"
                        onConfirm={() => void applyProposal(chatMessage.id)}
                      >
                        <Button
                          type="primary"
                          size="small"
                          icon={<CheckCircle2 size={15} />}
                          loading={applyingMessageId === chatMessage.id}
                        >
                          确认应用
                        </Button>
                      </Popconfirm>
                    )}
                  </div>
                </div>
              )}
            </article>
          ))
        )}
      </div>
      <div className="lyrics-memory-chat-composer">
        <Input.TextArea
          value={chatInput}
          autoSize={{ minRows: 3, maxRows: 7 }}
          maxLength={2000}
          showCount
          placeholder="告诉记忆助手要新增、修改、停用或恢复什么内容"
          onChange={(event) => setChatInput(event.target.value)}
        />
        <div>
          <Typography.Text type="secondary">方案确认后才会改变当前记忆</Typography.Text>
          <Button
            type="primary"
            icon={<Send size={16} />}
            loading={chatting}
            disabled={!chatInput.trim()}
            onClick={() => void sendChat()}
          >
            生成调整方案
          </Button>
        </div>
      </div>
    </div>
  )

  const snapshotPanel = (
    <div className="lyrics-memory-snapshot-panel">
      <div className="lyrics-memory-snapshot-toolbar">
        <div>
          <strong>已保留 {snapshots.length} / 20</strong>
          <span>{snapshots.length >= 20 ? '请先删除一份再继续保留' : '当前记忆可保存为独立快照'}</span>
        </div>
        <Button
          type="primary"
          icon={<Save size={16} />}
          disabled={snapshots.length >= 20}
          onClick={openSnapshotCreate}
        >
          保留当前记忆
        </Button>
      </div>
      {snapshots.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无保留记忆" />
      ) : (
        <div className="lyrics-memory-snapshot-grid">
          {snapshots.map((snapshot) => (
            <article className="lyrics-memory-snapshot-tile" key={snapshot.id}>
              <button
                className="lyrics-memory-snapshot-main"
                onClick={() => void openSnapshotDetail(snapshot.id)}
              >
                <span className="lyrics-memory-snapshot-icon"><Archive size={20} /></span>
                <strong>{snapshot.name}</strong>
                <small>创建 {formatDateTime(snapshot.created_at)}</small>
                <small>修改 {formatDateTime(snapshot.updated_at)}</small>
                <span>{snapshot.source_event_count} 条证据 · {snapshot.capsule_char_count.toLocaleString()} 字符</span>
              </button>
              <div className="lyrics-memory-snapshot-actions">
                <Tooltip title="修改名称">
                  <Button
                    type="text"
                    icon={<Pencil size={15} />}
                    aria-label="修改保留记忆名称"
                    onClick={() => openSnapshotRename(snapshot)}
                  />
                </Tooltip>
                <Popconfirm
                  title="删除这份保留记忆？"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => void removeSnapshot(snapshot.id)}
                >
                  <Tooltip title="删除保留记忆">
                    <Button
                      type="text"
                      danger
                      icon={<Trash2 size={15} />}
                      aria-label="删除保留记忆"
                    />
                  </Tooltip>
                </Popconfirm>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )

  return (
    <div className="page-stack">
      <div className="page-heading-row lyrics-memory-page-heading">
        <div>
          <Typography.Title level={1}>歌词记忆</Typography.Title>
          <Typography.Text type="secondary">提炼后的团队作词经验、调整与保留版本</Typography.Text>
        </div>
        <Space wrap className="lyrics-memory-page-actions">
          <Tooltip title="刷新歌词记忆">
            <Button
              icon={<RefreshCw size={16} />}
              loading={loading}
              aria-label="刷新歌词记忆"
              onClick={() => void refreshAll()}
            />
          </Tooltip>
          <Button icon={<Eye size={16} />} onClick={() => void openPreview()}>
            预览注入内容
          </Button>
          <Button type="primary" icon={<Plus size={16} />} onClick={() => setRuleOpen(true)}>
            新增固定规则
          </Button>
        </Space>
      </div>

      {error && <Alert type="error" showIcon title={error} />}

      <div className="metrics-grid lyrics-memory-metrics">
        <div className="metric-card">
          <span className="metric-icon metric-icon-blue"><Database size={20} /></span>
          <div><span>记忆记录</span><strong>{overview?.total_events ?? 0}</strong></div>
        </div>
        <div className="metric-card">
          <span className="metric-icon metric-icon-green"><CheckCircle2 size={20} /></span>
          <div><span>已形成提炼</span><strong>{preview?.distilled_insight_count ?? 0}</strong></div>
        </div>
        <div className="metric-card">
          <span className="metric-icon metric-icon-yellow"><Ban size={20} /></span>
          <div><span>历史待提炼</span><strong>{preview?.pending_legacy_count ?? 0}</strong></div>
        </div>
        <div className="metric-card">
          <span className="metric-icon metric-icon-coral"><BrainCircuit size={20} /></span>
          <div><span>注入字符</span><strong>{(overview?.capsule_char_count ?? 0).toLocaleString()}</strong></div>
        </div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'memory', label: <span><BrainCircuit size={15} /> 提炼记忆</span>, children: currentMemoryPanel },
          { key: 'events', label: <span><Database size={15} /> 记忆记录</span>, children: eventPanel },
          { key: 'chat', label: <span><MessageSquareText size={15} /> 对话调整</span>, children: chatPanel },
          { key: 'snapshots', label: <span><FileClock size={15} /> 保留记忆</span>, children: snapshotPanel },
        ]}
        className="lyrics-memory-tabs"
      />

      <Drawer
        title={detail ? `${EVENT_META[detail.event_type].label} #${detail.id}` : '记忆详情'}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        size={720}
        loading={detailLoading}
        extra={detail && (
          <Space>
            {isTraceOnlyEvent(detail.event_type) ? (
              <Tag>仅追溯</Tag>
            ) : (
              <Switch
                size="small"
                checked={detail.is_useful}
                loading={actionId === detail.id}
                onChange={(checked) => void toggleUsefulness(detail.id, checked)}
              />
            )}
            <Popconfirm
              title="永久删除这条记忆记录？"
              okText="删除"
              cancelText="取消"
              onConfirm={() => void removeEvent(detail.id)}
            >
              <Button danger icon={<Trash2 size={16} />}>删除</Button>
            </Popconfirm>
          </Space>
        )}
        className="lyrics-memory-drawer"
      >
        {detail && (
          <div className="lyrics-memory-detail">
            <Descriptions
              size="small"
              column={2}
              items={[
                {
                  key: 'status',
                  label: '记忆状态',
                  children: isTraceOnlyEvent(detail.event_type) ? '仅作原始证据' : detail.is_useful ? '使用中' : '已停用',
                },
                { key: 'user', label: '记录人', children: detail.created_by_username ?? '历史数据' },
                { key: 'task', label: '任务', children: detail.task_id ? `#${detail.task_id}` : '—' },
                { key: 'version', label: '歌词版本', children: detail.source_version_id ? `#${detail.source_version_id}` : '—' },
                { key: 'time', label: '记录时间', children: formatDateTime(detail.created_at), span: 2 },
              ]}
            />
            <section>
              <Typography.Title level={3}>清洗后证据</Typography.Title>
              <pre>{detail.cleaned_content}</pre>
            </section>
            <Collapse
              items={[
                { key: 'raw', label: '原始输入', children: <pre>{detail.raw_content}</pre> },
                { key: 'context', label: '完整上下文', children: <pre>{JSON.stringify(detail.context, null, 2)}</pre> },
              ]}
            />
          </div>
        )}
      </Drawer>

      <Drawer
        title="实际注入内容"
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        size={760}
        loading={previewLoading}
        extra={preview && <Tag>{preview.capsule_char_count.toLocaleString()} 字符</Tag>}
        className="lyrics-memory-drawer"
      >
        {preview && <MemoryCapsuleView memory={preview.memory} />}
      </Drawer>

      <Drawer
        title={snapshotDetail?.name ?? '保留记忆详情'}
        open={snapshotDrawerOpen}
        onClose={() => setSnapshotDrawerOpen(false)}
        size={760}
        loading={snapshotDetailLoading}
        className="lyrics-memory-drawer"
      >
        {snapshotDetail && (
          <div className="lyrics-memory-detail">
            <Descriptions
              size="small"
              column={2}
              items={[
                { key: 'created', label: '创建时间', children: formatDateTime(snapshotDetail.created_at) },
                { key: 'updated', label: '最后修改', children: formatDateTime(snapshotDetail.updated_at) },
                { key: 'events', label: '有效证据', children: `${snapshotDetail.source_event_count} 条` },
                { key: 'chars', label: '胶囊长度', children: `${snapshotDetail.capsule_char_count.toLocaleString()} 字符` },
              ]}
            />
            <MemoryCapsuleView memory={snapshotDetail.memory} />
          </div>
        )}
      </Drawer>

      <Modal
        title="新增管理员固定规则"
        open={ruleOpen}
        onCancel={() => setRuleOpen(false)}
        onOk={() => void saveRule()}
        okText="加入记忆"
        cancelText="取消"
        confirmLoading={savingRule}
        destroyOnHidden
      >
        <Form form={ruleForm} layout="vertical" requiredMark={false}>
          <Form.Item
            name="title"
            label="规则名称"
            rules={[{ required: true, max: 80, message: '请输入不超过 80 字的名称' }]}
          >
            <Input maxLength={80} placeholder="例如 副歌表达" />
          </Form.Item>
          <Form.Item
            name="content"
            label="规则内容"
            rules={[{ required: true, min: 2, max: 2000, message: '请输入 2 至 2000 字规则' }]}
          >
            <Input.TextArea autoSize={{ minRows: 5, maxRows: 10 }} maxLength={2000} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={snapshotEditing ? '修改保留记忆名称' : '保留当前歌词记忆'}
        open={snapshotModalOpen}
        onCancel={() => setSnapshotModalOpen(false)}
        onOk={() => void saveSnapshot()}
        okText={snapshotEditing ? '保存名称' : '确认保留'}
        cancelText="取消"
        confirmLoading={savingSnapshot}
        destroyOnHidden
      >
        <Form form={snapshotForm} layout="vertical" requiredMark={false}>
          <Form.Item
            name="name"
            label="记忆名称"
            rules={[{ required: true, max: 100, message: '请输入不超过 100 字的名称' }]}
          >
            <Input maxLength={100} placeholder="例如 第一轮客户偏好" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
