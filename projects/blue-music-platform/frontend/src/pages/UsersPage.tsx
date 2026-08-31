import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import { Gauge, KeyRound, Plus, RefreshCw, Settings2, Stamp } from 'lucide-react'

import {
  createUser,
  listUsers,
  resetUserPassword,
  setUserStatus,
  updateAgentPermissions,
  updateUserMusicQuota,
  updateUserWatermark,
} from '../api/users'
import { useAuth } from '../auth/useAuth'
import { errorMessage } from '../lib/errors'
import type { AgentType, User } from '../types/api'

const AGENT_OPTIONS: { label: string; value: AgentType }[] = [
  { label: '内容分析', value: 'analysis' },
  { label: '歌词创作', value: 'lyrics' },
  { label: '音乐创作', value: 'music' },
]
const AGENT_LABELS: Record<AgentType, string> = {
  crawler: '榜单采集（仅管理员）',
  analysis: '内容分析',
  lyrics: '歌词创作',
  music: '音乐创作',
}

interface AccountFormValues {
  username: string
  password: string
  music_quota_remaining: number
}

interface PasswordFormValues {
  password: string
}

interface MusicQuotaFormValues {
  remaining_tasks: number
}

interface WatermarkFormValues {
  watermark_text?: string
}

export function UsersPage() {
  const { message } = App.useApp()
  const { user: currentUser, replaceCurrentUser } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [permissionUser, setPermissionUser] = useState<User | null>(null)
  const [passwordUser, setPasswordUser] = useState<User | null>(null)
  const [quotaUser, setQuotaUser] = useState<User | null>(null)
  const [watermarkUser, setWatermarkUser] = useState<User | null>(null)
  const [selectedAgents, setSelectedAgents] = useState<AgentType[]>([])
  const [saving, setSaving] = useState(false)
  const [statusUserId, setStatusUserId] = useState<number | null>(null)
  const [createForm] = Form.useForm<AccountFormValues>()
  const [passwordForm] = Form.useForm<PasswordFormValues>()
  const [quotaForm] = Form.useForm<MusicQuotaFormValues>()
  const [watermarkForm] = Form.useForm<WatermarkFormValues>()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setUsers(await listUsers())
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const submitCreate = async () => {
    const values = await createForm.validateFields()
    setSaving(true)
    try {
      const user = await createUser(
        values.username.trim(),
        values.password,
        values.music_quota_remaining,
      )
      setUsers((current) => [...current, user])
      setCreateOpen(false)
      createForm.resetFields()
      message.success('成员账号已创建')
    } catch (submitError) {
      message.error(errorMessage(submitError))
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (user: User) => {
    setStatusUserId(user.id)
    try {
      const updated = await setUserStatus(user.id, !user.is_active)
      setUsers((current) =>
        current.map((item) => (item.id === user.id ? updated : item)),
      )
      message.success(updated.is_active ? '账号已启用' : '账号已停用')
    } catch (statusError) {
      message.error(errorMessage(statusError))
    } finally {
      setStatusUserId(null)
    }
  }

  const openPermissions = (user: User) => {
    setPermissionUser(user)
    setSelectedAgents(user.agent_permissions.filter((agent) => agent !== 'crawler'))
  }

  const submitPermissions = async () => {
    if (!permissionUser) return
    setSaving(true)
    try {
      const updated = await updateAgentPermissions(permissionUser.id, selectedAgents)
      setUsers((current) =>
        current.map((item) => (item.id === permissionUser.id ? updated : item)),
      )
      setPermissionUser(null)
      message.success('Agent 权限已更新')
    } catch (permissionError) {
      message.error(errorMessage(permissionError))
    } finally {
      setSaving(false)
    }
  }

  const submitPassword = async () => {
    if (!passwordUser) return
    const values = await passwordForm.validateFields()
    setSaving(true)
    try {
      await resetUserPassword(passwordUser.id, values.password)
      setPasswordUser(null)
      passwordForm.resetFields()
      message.success('密码已重置，原登录凭证已失效')
    } catch (passwordError) {
      message.error(errorMessage(passwordError))
    } finally {
      setSaving(false)
    }
  }

  const openMusicQuota = (user: User) => {
    setQuotaUser(user)
    quotaForm.setFieldsValue({
      remaining_tasks: user.music_quota.remaining_tasks ?? 0,
    })
  }

  const submitMusicQuota = async () => {
    if (!quotaUser) return
    const values = await quotaForm.validateFields()
    setSaving(true)
    try {
      const updated = await updateUserMusicQuota(
        quotaUser.id,
        values.remaining_tasks,
      )
      setUsers((current) =>
        current.map((item) => (item.id === quotaUser.id ? updated : item)),
      )
      setQuotaUser(null)
      quotaForm.resetFields()
      message.success('音乐任务额度已更新')
    } catch (quotaError) {
      message.error(errorMessage(quotaError))
    } finally {
      setSaving(false)
    }
  }

  const openWatermark = (user: User) => {
    setWatermarkUser(user)
    watermarkForm.setFieldsValue({ watermark_text: user.watermark_text })
  }

  const submitWatermark = async () => {
    if (!watermarkUser) return
    const values = await watermarkForm.validateFields()
    const watermarkText = values.watermark_text?.trim() || null
    setSaving(true)
    try {
      const updated = await updateUserWatermark(watermarkUser.id, watermarkText)
      setUsers((current) =>
        current.map((item) => (item.id === watermarkUser.id ? updated : item)),
      )
      if (updated.id === currentUser?.id) replaceCurrentUser(updated)
      setWatermarkUser(null)
      watermarkForm.resetFields()
      message.success(watermarkText ? '账号水印已更新' : '已恢复为账号名水印')
    } catch (watermarkError) {
      message.error(errorMessage(watermarkError))
    } finally {
      setSaving(false)
    }
  }

  const columns: TableProps<User>['columns'] = [
    {
      title: '账号',
      dataIndex: 'username',
      key: 'username',
      fixed: 'left',
      render: (username: string, user) => (
        <div className="account-cell">
          <strong>{username}</strong>
          <small>ID {user.id}</small>
        </div>
      ),
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 130,
      render: (role: User['role']) =>
        role === 'super_admin' ? <Tag color="gold">超级管理员</Tag> : <Tag>成员</Tag>,
    },
    {
      title: 'Agent 权限',
      dataIndex: 'agent_permissions',
      key: 'permissions',
      render: (agents: AgentType[], user) =>
        user.role === 'super_admin' ? (
          <span className="muted-copy">全部 Agent</span>
        ) : agents.some((agent) => agent !== 'crawler') ? (
          <Space size={[4, 4]} wrap>
            {agents
              .filter((agent) => agent !== 'crawler')
              .map((agent) => <Tag key={agent}>{AGENT_LABELS[agent]}</Tag>)}
          </Space>
        ) : (
          <span className="muted-copy">未分配</span>
        ),
    },
    {
      title: '页面水印',
      dataIndex: 'watermark_text',
      key: 'watermark',
      width: 170,
      render: (watermarkText: string, user) => (
        <div className="account-cell">
          <strong>{watermarkText}</strong>
          <small>{watermarkText === user.username ? '默认使用账号名' : '自定义内容'}</small>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'status',
      width: 100,
      render: (active: boolean, user) => (
        <Popconfirm
          title={active ? '确认停用此账号？' : '确认启用此账号？'}
          description={active ? '停用后现有登录凭证会立即失效。' : undefined}
          onConfirm={() => toggleStatus(user)}
          okText="确认"
          cancelText="取消"
        >
          <Switch
            size="small"
            checked={active}
            disabled={user.id === currentUser?.id}
            loading={statusUserId === user.id}
            aria-label={active ? '停用账号' : '启用账号'}
          />
        </Popconfirm>
      ),
    },
    {
      title: '音乐额度',
      key: 'music_quota',
      width: 150,
      render: (_, user) => user.music_quota.is_unlimited ? (
        <Tag color="gold">不限额</Tag>
      ) : (
        <div className="account-cell">
          <strong>剩余 {user.music_quota.remaining_tasks ?? 0} 次</strong>
          <small>累计使用 {user.music_quota.used_tasks} 次</small>
        </div>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 196,
      fixed: 'right',
      render: (_, user) => (
        <Space size={4}>
          <Tooltip title="设置页面水印">
            <Button
              type="text"
              icon={<Stamp size={17} />}
              aria-label="设置页面水印"
              onClick={() => openWatermark(user)}
            />
          </Tooltip>
          {user.role === 'member' && (
            <>
              <Tooltip title="设置 Agent 权限">
                <Button
                  type="text"
                  icon={<Settings2 size={17} />}
                  aria-label="设置 Agent 权限"
                  onClick={() => openPermissions(user)}
                />
              </Tooltip>
              <Tooltip title="重置密码">
                <Button
                  type="text"
                  icon={<KeyRound size={17} />}
                  aria-label="重置密码"
                  onClick={() => setPasswordUser(user)}
                />
              </Tooltip>
              <Tooltip title="设置音乐任务额度">
                <Button
                  type="text"
                  icon={<Gauge size={17} />}
                  aria-label="设置音乐任务额度"
                  onClick={() => openMusicQuota(user)}
                />
              </Tooltip>
            </>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>账号管理</Typography.Title>
          <Typography.Text type="secondary">成员账号与 Agent 使用权限</Typography.Text>
        </div>
        <Space>
          <Tooltip title="刷新账号列表">
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load} />
          </Tooltip>
          <Button type="primary" icon={<Plus size={17} />} onClick={() => setCreateOpen(true)}>
            新建成员
          </Button>
        </Space>
      </div>
      {error && <Alert type="error" showIcon title={error} />}
      <Table<User>
        rowKey="id"
        columns={columns}
        dataSource={users}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }}
        scroll={{ x: 1150 }}
        className="users-table"
      />

      <Modal
        title="新建成员账号"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={submitCreate}
        confirmLoading={saving}
        okText="创建账号"
        cancelText="取消"
        destroyOnHidden
      >
        <Form
          form={createForm}
          layout="vertical"
          requiredMark={false}
          initialValues={{ music_quota_remaining: 0 }}
        >
          <Form.Item
            name="username"
            label="登录账号"
            rules={[
              { required: true, message: '请输入登录账号' },
              { min: 3, max: 50, message: '账号长度为 3 至 50 位' },
              { pattern: /^[A-Za-z0-9._-]+$/, message: '仅支持字母、数字、点、横线和下划线' },
            ]}
          >
            <Input autoComplete="off" placeholder="例如 operator.one" />
          </Form.Item>
          <Form.Item
            name="password"
            label="初始密码"
            rules={[{ required: true, min: 8, max: 128, message: '密码长度为 8 至 128 位' }]}
          >
            <Input.Password autoComplete="new-password" placeholder="至少 8 位" />
          </Form.Item>
          <Form.Item
            name="music_quota_remaining"
            label="初始音乐任务额度"
            rules={[{ required: true, message: '请输入初始额度' }]}
          >
            <InputNumber min={0} max={100000} precision={0} style={{ width: '100%' }} addonAfter="次" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`设置页面水印 · ${watermarkUser?.username ?? ''}`}
        open={Boolean(watermarkUser)}
        onCancel={() => {
          setWatermarkUser(null)
          watermarkForm.resetFields()
        }}
        onOk={submitWatermark}
        confirmLoading={saving}
        okText="保存水印"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={watermarkForm} layout="vertical" requiredMark={false}>
          <Form.Item
            name="watermark_text"
            label="水印内容"
            extra={`留空后恢复为账号名：${watermarkUser?.username ?? ''}`}
            rules={[{ max: 50, message: '水印内容不能超过 50 个字符' }]}
          >
            <Input allowClear maxLength={50} showCount placeholder="输入几个用于识别的文字" />
          </Form.Item>
          <Typography.Text type="secondary">
            该账号登录后，工作台所有页面都会重复显示斜向水印。
          </Typography.Text>
        </Form>
      </Modal>

      <Modal
        title={`设置 Agent 权限 · ${permissionUser?.username ?? ''}`}
        open={Boolean(permissionUser)}
        onCancel={() => setPermissionUser(null)}
        onOk={submitPermissions}
        confirmLoading={saving}
        okText="保存权限"
        cancelText="取消"
      >
        <Checkbox.Group
          className="permissions-grid"
          options={AGENT_OPTIONS}
          value={selectedAgents}
          onChange={(values) => setSelectedAgents(values as AgentType[])}
        />
      </Modal>

      <Modal
        title={`设置音乐额度 · ${quotaUser?.username ?? ''}`}
        open={Boolean(quotaUser)}
        onCancel={() => {
          setQuotaUser(null)
          quotaForm.resetFields()
        }}
        onOk={submitMusicQuota}
        confirmLoading={saving}
        okText="保存额度"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={quotaForm} layout="vertical" requiredMark={false}>
          <Form.Item
            name="remaining_tasks"
            label="剩余音乐任务额度"
            rules={[{ required: true, message: '请输入剩余额度' }]}
          >
            <InputNumber min={0} max={100000} precision={0} style={{ width: '100%' }} addonAfter="次" />
          </Form.Item>
          <Typography.Text type="secondary">
            每次新建生成或续写任务扣除 1 次，任务重试不会重复扣除。
          </Typography.Text>
        </Form>
      </Modal>

      <Modal
        title={`重置密码 · ${passwordUser?.username ?? ''}`}
        open={Boolean(passwordUser)}
        onCancel={() => setPasswordUser(null)}
        onOk={submitPassword}
        confirmLoading={saving}
        okText="重置密码"
        cancelText="取消"
        destroyOnHidden
      >
        <Alert
          type="warning"
          showIcon
          title="保存后该账号现有登录凭证会立即失效"
          className="modal-alert"
        />
        <Form form={passwordForm} layout="vertical" requiredMark={false}>
          <Form.Item
            name="password"
            label="新密码"
            rules={[{ required: true, min: 8, max: 128, message: '密码长度为 8 至 128 位' }]}
          >
            <Input.Password autoComplete="new-password" placeholder="至少 8 位" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
