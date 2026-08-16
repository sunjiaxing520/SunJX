import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Checkbox,
  Collapse,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Skeleton,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  Bot,
  BrainCircuit,
  Check,
  ChevronDown,
  ChevronUp,
  FileSearch,
  MessageCircleMore,
  Plus,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'

import {
  confirmReviewRevisionPreview,
  createLyricsReview,
  createReviewAgent,
  listReviewAgents,
  listReviewLyricsOptions,
  listReviewRevisionMessages,
  listReviewRuns,
  previewReviewAgentInitialization,
  requestReviewRevisionPreview,
  saveReviewAgentMemory,
  updateReviewAgentMembers,
  updateReviewAgentSettings,
} from '../api/reviewAgents'
import { listUsers } from '../api/users'
import { useAuth } from '../auth/useAuth'
import { errorMessage } from '../lib/errors'
import type {
  LyricsAssistantMessage,
  ReviewAgent,
  ReviewChatMessage,
  ReviewLyricsOption,
  ReviewResult,
  User,
} from '../types/api'

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : []
}

function reviewDimensions(value: unknown): Array<{ name: string; score: number; feedback: string }> {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const record = item as Record<string, unknown>
    return typeof record.name === 'string' && typeof record.score === 'number' && typeof record.feedback === 'string'
      ? [{ name: record.name, score: record.score, feedback: record.feedback }]
      : []
  })
}

export function ReviewAgentsPage() {
  const { message } = App.useApp()
  const { user } = useAuth()
  const isAdmin = user?.role === 'super_admin'
  const [agents, setAgents] = useState<ReviewAgent[]>([])
  const [activeAgentId, setActiveAgentId] = useState<number | null>(null)
  const [lyricsOptions, setLyricsOptions] = useState<ReviewLyricsOption[]>([])
  const [reviewRuns, setReviewRuns] = useState<ReviewResult[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [loadingUsers, setLoadingUsers] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [agentName, setAgentName] = useState('')
  const [agentPassScore, setAgentPassScore] = useState(80)
  const [initializationMessages, setInitializationMessages] = useState<ReviewChatMessage[]>([])
  const [initializationDraft, setInitializationDraft] = useState('')
  const [initializationLoading, setInitializationLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [memberIds, setMemberIds] = useState<number[]>([])
  const [savingMembers, setSavingMembers] = useState(false)
  const [settingsPassScore, setSettingsPassScore] = useState(80)
  const [savingSettings, setSavingSettings] = useState(false)
  const [lyricsVersionId, setLyricsVersionId] = useState<number | null>(null)
  const [reviewInstruction, setReviewInstruction] = useState('')
  const [reviewing, setReviewing] = useState(false)
  const [memoryDraft, setMemoryDraft] = useState('')
  const [savingMemory, setSavingMemory] = useState(false)

  const activeAgent = useMemo(
    () => agents.find((agent) => agent.id === activeAgentId) ?? null,
    [activeAgentId, agents],
  )
  const memberAccounts = useMemo(
    () => users.filter((account) => account.role === 'member'),
    [users],
  )
  const selectedMemberCount = useMemo(
    () => memberAccounts.filter((account) => memberIds.includes(account.id)).length,
    [memberAccounts, memberIds],
  )

  const replaceAgent = useCallback((nextAgent: ReviewAgent) => {
    setAgents((current) => current.map((agent) => agent.id === nextAgent.id ? nextAgent : agent))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const nextAgents = await listReviewAgents()
      setAgents(nextAgents)
      setActiveAgentId((current) => (
        current && nextAgents.some((agent) => agent.id === current)
          ? current
          : nextAgents[0]?.id ?? null
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

  useEffect(() => {
    if (!activeAgent) {
      setLyricsOptions([])
      setReviewRuns([])
      return
    }

    let cancelled = false
    const loadDetails = async () => {
      setLoadingDetails(true)
      try {
        const [options, history] = await Promise.all([
          listReviewLyricsOptions(),
          listReviewRuns(activeAgent.id),
        ])
        if (cancelled) return
        setLyricsOptions(options)
        setReviewRuns(history.items)
        setMemberIds(activeAgent.members.map((member) => member.id))
        setSettingsPassScore(activeAgent.pass_score)
      } catch (detailsError) {
        if (!cancelled) setError(errorMessage(detailsError))
      } finally {
        if (!cancelled) setLoadingDetails(false)
      }
    }
    void loadDetails()
    return () => {
      cancelled = true
    }
  }, [activeAgent])

  useEffect(() => {
    if (!isAdmin) return
    let cancelled = false
    const loadUsers = async () => {
      setLoadingUsers(true)
      try {
        const result = await listUsers()
        if (!cancelled) setUsers(result.filter((account) => account.is_active))
      } catch (usersError) {
        if (!cancelled) setError(errorMessage(usersError))
      } finally {
        if (!cancelled) setLoadingUsers(false)
      }
    }
    void loadUsers()
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  const openCreate = () => {
    setAgentName('')
    setAgentPassScore(80)
    setInitializationMessages([])
    setInitializationDraft('')
    setCreateOpen(true)
  }

  const continueInitialization = async () => {
    const nextMessage = initializationDraft.trim()
    if (!nextMessage) return
    setInitializationLoading(true)
    try {
      const preview = await previewReviewAgentInitialization(initializationMessages, nextMessage)
      setInitializationMessages((current) => [
        ...current,
        { role: 'user', content: nextMessage },
        { role: 'assistant', content: preview.reply },
      ])
      setInitializationDraft('')
    } catch (previewError) {
      message.error(errorMessage(previewError))
    } finally {
      setInitializationLoading(false)
    }
  }

  const create = async () => {
    if (!agentName.trim()) {
      message.warning('请填写审核智能体名称')
      return
    }
    if (!initializationMessages.length) {
      message.warning('请先完成至少一轮初始化对话')
      return
    }
    setCreating(true)
    try {
      const created = await createReviewAgent(agentName.trim(), initializationMessages, agentPassScore)
      setAgents((current) => [created, ...current])
      setActiveAgentId(created.id)
      setCreateOpen(false)
      message.success('审核智能体已创建')
    } catch (createError) {
      message.error(errorMessage(createError))
    } finally {
      setCreating(false)
    }
  }

  const saveMembers = async () => {
    if (!activeAgent) return
    setSavingMembers(true)
    try {
      const updated = await updateReviewAgentMembers(activeAgent.id, memberIds)
      replaceAgent(updated)
      message.success('成员权限已更新')
    } catch (membersError) {
      message.error(errorMessage(membersError))
    } finally {
      setSavingMembers(false)
    }
  }

  const saveSettings = async () => {
    if (!activeAgent) return
    setSavingSettings(true)
    try {
      const updated = await updateReviewAgentSettings(activeAgent.id, settingsPassScore)
      replaceAgent(updated)
      message.success('自动流程及格线已更新')
    } catch (settingsError) {
      message.error(errorMessage(settingsError))
    } finally {
      setSavingSettings(false)
    }
  }

  const submitReview = async () => {
    if (!activeAgent || !lyricsVersionId) {
      message.warning('请选择要审核的歌词版本')
      return
    }
    setReviewing(true)
    try {
      const result = await createLyricsReview(activeAgent.id, lyricsVersionId, reviewInstruction.trim() || undefined)
      setReviewRuns((current) => [result, ...current])
      setReviewInstruction('')
      message.success('歌词审核已完成')
    } catch (reviewError) {
      message.error(errorMessage(reviewError))
    } finally {
      setReviewing(false)
    }
  }

  const saveMemory = async () => {
    if (!activeAgent || !memoryDraft.trim()) return
    setSavingMemory(true)
    try {
      const memory = await saveReviewAgentMemory(activeAgent.id, memoryDraft.trim())
      replaceAgent({
        ...activeAgent,
        memory_summary: memory.summary,
        memory_detail: isAdmin ? memory.detail : activeAgent.memory_detail,
      })
      setMemoryDraft('')
      message.success('记忆已整理并保存')
    } catch (memoryError) {
      message.error(errorMessage(memoryError))
    } finally {
      setSavingMemory(false)
    }
  }

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>审核智能体</Typography.Title>
          <Typography.Text type="secondary">歌词审核、评分与修改建议</Typography.Text>
        </div>
        <Space>
          <Tooltip title="刷新审核智能体">
            <Button icon={<RefreshCw size={16} />} loading={loading} aria-label="刷新审核智能体" onClick={load} />
          </Tooltip>
          {isAdmin && (
            <Button type="primary" icon={<Plus size={16} />} onClick={openCreate}>
              新建审核智能体
            </Button>
          )}
        </Space>
      </div>

      {error && <Alert type="error" showIcon closable title={error} onClose={() => setError(null)} />}

      {loading ? <Skeleton active paragraph={{ rows: 7 }} /> : agents.length ? (
        <div className="review-agent-workspace">
          <aside className="review-agent-sidebar" aria-label="审核智能体列表">
            {agents.map((agent) => (
              <button
                className={`review-agent-list-item ${agent.id === activeAgentId ? 'active' : ''}`}
                key={agent.id}
                type="button"
                aria-pressed={agent.id === activeAgentId}
                onClick={() => setActiveAgentId(agent.id)}
              >
                <span className="review-agent-list-icon"><Bot size={18} /></span>
                <span className="review-agent-list-copy">
                  <strong>{agent.name}</strong>
                  <small>{agent.memory_summary}</small>
                </span>
                <Tag>{agent.members.length} 人</Tag>
              </button>
            ))}
          </aside>

          {activeAgent && (
            <main className="review-agent-main">
              <section className="review-agent-overview">
                <div className="review-agent-heading">
                  <span className="review-agent-heading-icon"><ShieldCheck size={21} /></span>
                  <div>
                    <Typography.Title level={2}>{activeAgent.name}</Typography.Title>
                    <Typography.Text type="secondary">创建于 {formatDateTime(activeAgent.created_at)}</Typography.Text>
                  </div>
                </div>
                <Descriptions size="small" column={1} className="review-agent-descriptions">
                  <Descriptions.Item label="记忆概述">
                    <Typography.Paragraph
                      className="review-agent-memory-summary"
                      ellipsis={{
                        rows: 4,
                        expandable: 'collapsible',
                        symbol: (expanded) => expanded ? '收起概述' : '展开概述',
                      }}
                    >
                      {activeAgent.memory_summary}
                    </Typography.Paragraph>
                  </Descriptions.Item>
                  <Descriptions.Item label="自动流程及格线">{activeAgent.pass_score} 分</Descriptions.Item>
                  <Descriptions.Item label="可用成员">
                    {activeAgent.members.length
                      ? activeAgent.members.map((member) => member.username).join('、')
                      : isAdmin ? '暂未分配成员' : '由管理员管理'}
                  </Descriptions.Item>
                </Descriptions>

                {isAdmin && (
                  <Collapse
                    className="review-agent-admin-collapse"
                    items={[
                      {
                        key: 'settings',
                        label: '自动流程设置',
                        children: (
                          <div className="review-agent-settings-editor">
                            <div>
                              <Typography.Text strong>审核及格线</Typography.Text>
                              <Typography.Text type="secondary">
                                自动流程每次只审核一次；低于此分数便暂停，等待用户决定。
                              </Typography.Text>
                            </div>
                            <Space.Compact>
                              <InputNumber
                                min={1}
                                max={100}
                                value={settingsPassScore}
                                addonAfter="分"
                                onChange={(value) => setSettingsPassScore(value ?? 80)}
                              />
                              <Button loading={savingSettings} onClick={() => void saveSettings()}>
                                保存
                              </Button>
                            </Space.Compact>
                          </div>
                        ),
                      },
                      {
                        key: 'memory',
                        label: '查看完整初始化与长期记忆',
                        children: (
                          <div className="review-agent-memory-detail">
                            <Typography.Text strong>初始化对话</Typography.Text>
                            <Typography.Paragraph className="review-agent-notes">
                              {activeAgent.initialization_notes || '暂无初始化记录'}
                            </Typography.Paragraph>
                            <Typography.Text strong>长期记忆</Typography.Text>
                            <pre>{JSON.stringify(activeAgent.memory_detail ?? {}, null, 2)}</pre>
                          </div>
                        ),
                      },
                      {
                        key: 'members',
                        label: '成员权限',
                        children: (
                          <div className="review-agent-members-editor">
                            <div className="review-agent-member-box">
                              <div className="review-agent-member-toolbar">
                                <Typography.Text strong>可分配成员</Typography.Text>
                                <Typography.Text type="secondary">
                                  已选 {selectedMemberCount} / {memberAccounts.length}
                                </Typography.Text>
                              </div>
                              {loadingUsers ? (
                                <Skeleton active paragraph={{ rows: 2 }} title={false} />
                              ) : memberAccounts.length ? (
                                <Checkbox.Group
                                  className="review-agent-member-grid"
                                  value={memberIds}
                                  onChange={(values) => setMemberIds(values.map(Number))}
                                >
                                  {memberAccounts.map((account) => (
                                    <Checkbox
                                      className={`review-agent-member-option ${memberIds.includes(account.id) ? 'selected' : ''}`}
                                      key={account.id}
                                      value={account.id}
                                    >
                                      <span className="review-agent-member-copy">
                                        <strong>{account.username}</strong>
                                        <small>成员 ID {account.id}</small>
                                      </span>
                                    </Checkbox>
                                  ))}
                                </Checkbox.Group>
                              ) : (
                                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可分配成员" />
                              )}
                            </div>
                            <div className="review-agent-member-actions">
                              <Button
                                type="primary"
                                icon={<Users size={16} />}
                                loading={savingMembers}
                                disabled={loadingUsers}
                                onClick={() => void saveMembers()}
                              >
                                保存成员权限
                              </Button>
                            </div>
                          </div>
                        ),
                      },
                    ]}
                  />
                )}
              </section>

              <section className="review-agent-action-section">
                <div className="section-title-row">
                  <div>
                    <Typography.Title level={3}>发起歌词审核</Typography.Title>
                    <Typography.Text type="secondary">选择一份歌词版本，按当前审核标准输出结果。</Typography.Text>
                  </div>
                  <FileSearch size={19} />
                </div>
                <Form layout="vertical" requiredMark={false}>
                  <Form.Item label="歌词版本" required>
                    <Select
                      showSearch
                      optionFilterProp="label"
                      value={lyricsVersionId}
                      loading={loadingDetails}
                      placeholder="选择歌词版本"
                      options={lyricsOptions.map((option) => ({
                        value: option.id,
                        label: `${option.title} · 第 ${option.version_number} 版 · 任务 #${option.task_id}`,
                      }))}
                      onChange={(value) => setLyricsVersionId(value)}
                    />
                  </Form.Item>
                  <Form.Item label="本次补充要求">
                    <Input.TextArea
                      rows={3}
                      maxLength={2000}
                      value={reviewInstruction}
                      placeholder="例如：重点检查副歌的记忆点和押韵是否自然"
                      onChange={(event) => setReviewInstruction(event.target.value)}
                    />
                  </Form.Item>
                  <Button
                    type="primary"
                    icon={<Sparkles size={16} />}
                    loading={reviewing}
                    disabled={!lyricsOptions.length}
                    onClick={() => void submitReview()}
                  >
                    开始审核
                  </Button>
                </Form>
              </section>

              <section className="review-agent-action-section">
                <div className="section-title-row">
                  <div>
                    <Typography.Title level={3}>保存为长期记忆</Typography.Title>
                    <Typography.Text type="secondary">只有主动保存的内容才会影响后续审核。</Typography.Text>
                  </div>
                  <BrainCircuit size={19} />
                </div>
                <Input.TextArea
                  rows={3}
                  maxLength={4000}
                  value={memoryDraft}
                  placeholder="记录新的审核偏好、客户反馈或需要长期沿用的标准"
                  onChange={(event) => setMemoryDraft(event.target.value)}
                />
                <div className="review-agent-save-memory">
                  <Typography.Text type="secondary">AI 会合并重复内容并更新记忆概述。</Typography.Text>
                  <Button
                    icon={<Save size={16} />}
                    loading={savingMemory}
                    disabled={!memoryDraft.trim()}
                    onClick={() => void saveMemory()}
                  >
                    保存记忆
                  </Button>
                </div>
              </section>

              <section className="review-agent-history">
                <div className="section-title-row">
                  <div>
                    <Typography.Title level={3}>最近审核</Typography.Title>
                    <Typography.Text type="secondary">默认展示最近 20 条结果。</Typography.Text>
                  </div>
                </div>
                {loadingDetails ? <Skeleton active paragraph={{ rows: 4 }} /> : reviewRuns.length ? (
                  <div className="review-run-list">
                    {reviewRuns.map((run) => (
                      <ReviewRunView
                        key={run.id}
                        run={run}
                        passScore={activeAgent.pass_score}
                        agentId={activeAgent.id}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="review-agent-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无审核记录" /></div>
                )}
              </section>
            </main>
          )}
        </div>
      ) : (
        <div className="review-agent-empty">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={isAdmin ? '暂无审核智能体' : '管理员尚未向你分配审核智能体'}
          >
            {isAdmin && <Button type="primary" icon={<Plus size={16} />} onClick={openCreate}>新建审核智能体</Button>}
          </Empty>
        </div>
      )}

      <Modal
        title="新建审核智能体"
        open={createOpen}
        width={760}
        destroyOnHidden
        okText="创建审核智能体"
        cancelText="取消"
        confirmLoading={creating}
        okButtonProps={{ disabled: !agentName.trim() || !initializationMessages.length }}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void create()}
      >
        <Form layout="vertical" requiredMark={false}>
          <Form.Item label="名称" required>
            <Input
              value={agentName}
              maxLength={100}
              placeholder="例如：流行歌词韵律审核"
              onChange={(event) => setAgentName(event.target.value)}
            />
          </Form.Item>
          <Form.Item label="自动流程及格线" required>
            <InputNumber
              min={1}
              max={100}
              value={agentPassScore}
              addonAfter="分"
              onChange={(value) => setAgentPassScore(value ?? 80)}
            />
            <Typography.Paragraph type="secondary" className="review-agent-field-help">
              低于该分数时自动流程立即暂停，不会自动修改或重复审核。
            </Typography.Paragraph>
          </Form.Item>
          <Form.Item label="初始化对话" required>
            <div className="review-agent-init-history">
              {initializationMessages.length ? initializationMessages.map((item, index) => (
                <div className={`review-agent-init-message ${item.role}`} key={`${item.role}-${index}`}>
                  <strong>{item.role === 'user' ? '管理员' : 'AI 助手'}</strong>
                  <span>{item.content}</span>
                </div>
              )) : (
                <Typography.Text type="secondary">先描述审核人设、评分维度、禁忌和输出要求。</Typography.Text>
              )}
            </div>
            <Space.Compact block className="review-agent-init-input">
              <Input.TextArea
                autoSize={{ minRows: 2, maxRows: 5 }}
                maxLength={2000}
                value={initializationDraft}
                placeholder="例如：审核中文流行歌词，满分 100 分，优先检查韵律、叙事和副歌记忆点。"
                onChange={(event) => setInitializationDraft(event.target.value)}
                onPressEnter={(event) => {
                  if (event.shiftKey) return
                  event.preventDefault()
                  if (initializationDraft.trim() && !initializationLoading) void continueInitialization()
                }}
              />
              <Button
                type="primary"
                icon={<MessageCircleMore size={16} />}
                loading={initializationLoading}
                disabled={!initializationDraft.trim()}
                aria-label="继续初始化对话"
                onClick={() => void continueInitialization()}
              />
            </Space.Compact>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function ReviewRunView({
  run,
  passScore,
  agentId,
}: {
  run: ReviewResult
  passScore: number
  agentId: number
}) {
  const { message } = App.useApp()
  const [expanded, setExpanded] = useState(false)
  const [revisionMessages, setRevisionMessages] = useState<LyricsAssistantMessage[]>([])
  const [revisionInstruction, setRevisionInstruction] = useState('')
  const [revisionHistoryLoaded, setRevisionHistoryLoaded] = useState(false)
  const [revisionHistoryLoading, setRevisionHistoryLoading] = useState(false)
  const [revisionLoading, setRevisionLoading] = useState(false)
  const [confirmingPreviewId, setConfirmingPreviewId] = useState<number | null>(null)
  const [currentPreviewId, setCurrentPreviewId] = useState<number | null>(null)
  const [savedVersionNumber, setSavedVersionNumber] = useState<number | null>(null)
  const score = typeof run.result.overall_score === 'number' ? run.result.overall_score : null
  const historicalPassScore = typeof run.result.pass_score === 'number' ? run.result.pass_score : passScore
  const passed = typeof run.result.passed === 'boolean'
    ? run.result.passed
    : score !== null && score >= historicalPassScore
  const summary = typeof run.result.summary === 'string' ? run.result.summary : '审核结果已生成。'
  const dimensions = reviewDimensions(run.result.dimensions)
  const strengths = stringList(run.result.strengths)
  const deductions = stringList(run.result.deduction_reasons)
  const suggestions = stringList(run.result.revision_suggestions)
  const risks = stringList(run.result.risk_notes)

  const loadRevisionHistory = useCallback(async () => {
    if (!run.lyrics_version_id || revisionHistoryLoaded || revisionHistoryLoading) return
    setRevisionHistoryLoading(true)
    try {
      const history = await listReviewRevisionMessages(agentId, run.id)
      setRevisionMessages(history.items)
      setRevisionHistoryLoaded(true)
    } catch (historyError) {
      message.error(errorMessage(historyError))
    } finally {
      setRevisionHistoryLoading(false)
    }
  }, [
    agentId,
    message,
    revisionHistoryLoaded,
    revisionHistoryLoading,
    run.id,
    run.lyrics_version_id,
  ])

  useEffect(() => {
    void loadRevisionHistory()
  }, [loadRevisionHistory])

  const requestRevision = async () => {
    const instruction = revisionInstruction.trim()
    if (!run.lyrics_version_id || !instruction || revisionLoading) return
    setRevisionLoading(true)
    try {
      const preview = await requestReviewRevisionPreview(agentId, run.id, instruction)
      setRevisionInstruction('')
      try {
        const history = await listReviewRevisionMessages(agentId, run.id)
        setRevisionMessages(history.items)
        setRevisionHistoryLoaded(true)
      } catch {
        setRevisionMessages((current) => [...current, preview])
      }
      message.success('修改预览已生成，请检查后再保存')
    } catch (revisionError) {
      message.error(errorMessage(revisionError))
    } finally {
      setRevisionLoading(false)
    }
  }

  const saveRevision = async (previewId: number) => {
    setConfirmingPreviewId(previewId)
    try {
      const version = await confirmReviewRevisionPreview(agentId, run.id, previewId)
      setCurrentPreviewId(previewId)
      setSavedVersionNumber(version.version_number)
      message.success(`已设为当前作品 V${version.version_number}，上一版仍可恢复`)
    } catch (confirmError) {
      message.error(errorMessage(confirmError))
    } finally {
      setConfirmingPreviewId(null)
    }
  }

  return (
    <article className="review-run-item">
      <div className="review-run-heading">
        <div>
          <strong>审核 #{run.id}</strong>
          <small>{formatDateTime(run.created_at)} · {run.model || run.provider}</small>
        </div>
        <Space>
          {score !== null && <Tag color={passed ? 'success' : 'warning'}>{passed ? '通过' : '未通过'}</Tag>}
          {score !== null && <span className="review-run-score">{score}<small> / {historicalPassScore} 分</small></span>}
        </Space>
      </div>
      <div className="review-revision-assistant">
        <div className="review-revision-heading">
          <div>
            <MessageCircleMore size={16} />
            <strong>AI 修改</strong>
            <Typography.Text type="secondary">已自动带入本次审核意见</Typography.Text>
          </div>
          {savedVersionNumber !== null && <Tag color="success">当前作品 V{savedVersionNumber}</Tag>}
        </div>
        {run.lyrics_version_id ? (
          <>
            {revisionHistoryLoading && !revisionMessages.length ? (
              <Skeleton active paragraph={{ rows: 2 }} title={false} />
            ) : revisionMessages.length > 0 && (
              <div className="review-revision-history" aria-label="审核修改对话记录">
                {revisionMessages.map((item) => (
                  <div className={`review-revision-message ${item.role}`} key={item.id}>
                    <strong>{item.role === 'user' ? '你' : 'AI 助手'}</strong>
                    <span>{item.content}</span>
                    {item.preview && (
                      <div className="review-revision-preview">
                        <div className="review-revision-preview-heading">
                          <div>
                            <strong>{item.preview.title}</strong>
                            <small>{item.preview.style_prompt}</small>
                          </div>
                          <Button
                            type={currentPreviewId === item.id ? 'default' : 'primary'}
                            size="small"
                            icon={<Check size={14} />}
                            loading={confirmingPreviewId === item.id}
                            disabled={currentPreviewId === item.id || confirmingPreviewId !== null}
                            onClick={() => void saveRevision(item.id)}
                          >
                            {currentPreviewId === item.id ? '当前作品' : '保存并设为当前作品'}
                          </Button>
                        </div>
                        <pre>{item.preview.content}</pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            <Space.Compact block className="review-revision-input">
              <Input.TextArea
                autoSize={{ minRows: 1, maxRows: 4 }}
                maxLength={2000}
                value={revisionInstruction}
                placeholder="告诉 AI 需要怎样修改这份歌词"
                aria-label="审核后歌词修改要求"
                onFocus={() => void loadRevisionHistory()}
                onChange={(event) => setRevisionInstruction(event.target.value)}
                onPressEnter={(event) => {
                  if (event.shiftKey) return
                  event.preventDefault()
                  if (revisionInstruction.trim() && !revisionLoading) void requestRevision()
                }}
              />
              <Button
                type="primary"
                icon={<Send size={15} />}
                loading={revisionLoading}
                disabled={!revisionInstruction.trim()}
                aria-label="发送审核修改要求"
                onClick={() => void requestRevision()}
              />
            </Space.Compact>
          </>
        ) : (
          <Alert type="warning" showIcon message="这条历史审核未关联歌词版本，无法继续修改" />
        )}
      </div>
      <div className="review-run-toggle">
        <Button
          type="text"
          size="small"
          icon={expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          aria-expanded={expanded}
          aria-controls={`review-run-detail-${run.id}`}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? '隐藏审核结果' : '展开审核结果'}
        </Button>
      </div>
      {expanded && (
        <div className="review-run-detail" id={`review-run-detail-${run.id}`}>
          <Typography.Paragraph>{summary}</Typography.Paragraph>
          {dimensions.length > 0 && (
            <div className="review-dimension-list">
              {dimensions.map((dimension) => (
                <div key={`${dimension.name}-${dimension.score}`}>
                  <strong>{dimension.name}</strong>
                  <Tag color={dimension.score >= historicalPassScore ? 'success' : dimension.score >= 60 ? 'warning' : 'error'}>{dimension.score} 分</Tag>
                  <span>{dimension.feedback}</span>
                </div>
              ))}
            </div>
          )}
          <ReviewList label="优点" values={strengths} />
          <ReviewList label="扣分原因" values={deductions} tone="risk" />
          <ReviewList label="修改建议" values={suggestions} />
          <ReviewList label="风险提示" values={risks} tone="risk" />
        </div>
      )}
    </article>
  )
}

function ReviewList({ label, values, tone }: { label: string; values: string[]; tone?: 'risk' }) {
  if (!values.length) return null
  return (
    <div className={`review-run-list-block ${tone ?? ''}`}>
      <strong>{label}</strong>
      <ul>
        {values.map((value, index) => <li key={`${label}-${index}`}>{value}</li>)}
      </ul>
    </div>
  )
}
