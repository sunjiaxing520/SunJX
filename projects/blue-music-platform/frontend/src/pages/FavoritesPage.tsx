import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Empty,
  Input,
  Popconfirm,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  type TableProps,
} from 'antd'
import { Eye, MessageSquareText, RefreshCw, Save, StarOff } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { deleteFavorite, listFavorites, updateFavoriteNote } from '../api/favorites'
import { hasAgentAccess } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { errorMessage } from '../lib/errors'
import type { FavoriteItem, FavoriteItemType } from '../types/api'

type FavoriteFilter = 'all' | FavoriteItemType

const CATEGORY_LABELS: Record<FavoriteItemType, string> = {
  analysis: '榜单分析',
  lyrics: '歌词创作',
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function sourceLabel(item: FavoriteItem): string {
  if (item.item_type === 'analysis') {
    return `报告 #${item.target_id} · 任务 #${item.source_task_id}`
  }
  return `第 ${Number(item.metadata.version_number ?? 1)} 版 · 任务 #${item.source_task_id}`
}

export function FavoritesPage() {
  const { message } = App.useApp()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState<FavoriteItem[]>([])
  const [activeFilter, setActiveFilter] = useState<FavoriteFilter>('all')
  const [expandedRowKeys, setExpandedRowKeys] = useState<React.Key[]>([])
  const [noteDrafts, setNoteDrafts] = useState<Record<number, string>>({})
  const [savingNoteId, setSavingNoteId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await listFavorites()
      setItems(result.items)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const counts = useMemo(() => ({
    all: items.length,
    analysis: items.filter((item) => item.item_type === 'analysis').length,
    lyrics: items.filter((item) => item.item_type === 'lyrics').length,
  }), [items])

  const visibleItems = useMemo(
    () => activeFilter === 'all'
      ? items
      : items.filter((item) => item.item_type === activeFilter),
    [activeFilter, items],
  )

  const canOpenSource = (item: FavoriteItem) => {
    if (!user) return false
    return hasAgentAccess(user, item.item_type)
  }

  const openSource = (item: FavoriteItem) => {
    if (!canOpenSource(item)) return
    if (item.item_type === 'analysis') {
      navigate(`/analysis?task_id=${item.source_task_id}`)
      return
    }
    navigate(`/lyrics?task_id=${item.source_task_id}&version_id=${item.target_id}`)
  }

  const toggleNote = (item: FavoriteItem) => {
    const isExpanded = expandedRowKeys.includes(item.id)
    setExpandedRowKeys(isExpanded ? [] : [item.id])
    if (!isExpanded) {
      setNoteDrafts((drafts) => ({ ...drafts, [item.id]: item.note ?? '' }))
    }
  }

  const saveNote = async (item: FavoriteItem) => {
    setSavingNoteId(item.id)
    try {
      const updated = await updateFavoriteNote(item.id, noteDrafts[item.id] ?? '')
      setItems((current) => current.map((value) => value.id === updated.id ? updated : value))
      setNoteDrafts((drafts) => ({ ...drafts, [item.id]: updated.note ?? '' }))
      message.success('备注已保存')
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSavingNoteId(null)
    }
  }

  const remove = async (item: FavoriteItem) => {
    try {
      await deleteFavorite(item.id)
      setItems((current) => current.filter((value) => value.id !== item.id))
      setExpandedRowKeys((keys) => keys.filter((key) => key !== item.id))
      message.success('已从收藏夹移除')
    } catch (removeError) {
      message.error(errorMessage(removeError))
    }
  }

  const columns: TableProps<FavoriteItem>['columns'] = [
    {
      title: '收藏内容',
      key: 'content',
      width: 230,
      render: (_, item) => (
        <div className="favorite-content-cell">
          <strong>{item.title}</strong>
          <small>{item.summary}</small>
        </div>
      ),
    },
    {
      title: '分类 / 来源',
      key: 'category',
      width: 150,
      render: (_, item) => (
        <div className="favorite-source-cell">
          <Tag color={item.item_type === 'analysis' ? 'blue' : 'green'}>
            {CATEGORY_LABELS[item.item_type]}
          </Tag>
          <small>{sourceLabel(item)}</small>
        </div>
      ),
    },
    {
      title: '模型 / Token',
      key: 'provider',
      width: 155,
      render: (_, item) => (
        <div className="account-cell">
          <strong>{item.model || '默认模型'}</strong>
          <small>{item.provider} · {item.total_tokens.toLocaleString()} Token</small>
        </div>
      ),
    },
    {
      title: '生成时间',
      dataIndex: 'source_created_at',
      width: 145,
      render: formatDateTime,
    },
    {
      title: '收藏信息',
      key: 'favorited',
      width: 155,
      render: (_, item) => (
        <div className="account-cell">
          <strong>{item.created_by_username ?? '已注销账号'}</strong>
          <small>{formatDateTime(item.favorited_at)}</small>
        </div>
      ),
    },
    {
      title: '',
      key: 'actions',
      fixed: 'right',
      width: 120,
      render: (_, item) => {
        const noteExpanded = expandedRowKeys.includes(item.id)
        return (
          <Space size={0}>
            <Tooltip title={item.note ? '查看备注' : '添加备注'}>
              <Button
                type={noteExpanded ? 'primary' : 'text'}
                className={item.note && !noteExpanded ? 'favorite-note-present' : undefined}
                icon={<MessageSquareText size={16} />}
                aria-label={item.note ? '查看收藏备注' : '添加收藏备注'}
                onClick={() => toggleNote(item)}
              />
            </Tooltip>
            <Tooltip title={canOpenSource(item) ? '查看原始记录' : '没有对应 Agent 权限'}>
              <Button
                type="text"
                icon={<Eye size={16} />}
                disabled={!canOpenSource(item)}
                aria-label="查看原始记录"
                onClick={() => openSource(item)}
              />
            </Tooltip>
            <Popconfirm
              title="移出收藏夹"
              description="原始分析或歌词记录不会被删除。"
              okText="移除"
              cancelText="取消"
              onConfirm={() => void remove(item)}
            >
              <Tooltip title="移出收藏夹">
                <Button type="text" icon={<StarOff size={16} />} aria-label="移出收藏夹" />
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
          <Typography.Title level={1}>收藏夹</Typography.Title>
          <Typography.Text type="secondary">团队精选的分析报告与歌词版本</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>刷新</Button>
      </div>

      {error && <Alert type="error" showIcon title={error} />}

      <section className="content-section favorites-section">
        <Tabs
          activeKey={activeFilter}
          onChange={(key) => {
            setActiveFilter(key as FavoriteFilter)
            setExpandedRowKeys([])
          }}
          items={[
            { key: 'all', label: `全部 ${counts.all}` },
            { key: 'analysis', label: `榜单分析 ${counts.analysis}` },
            { key: 'lyrics', label: `歌词创作 ${counts.lyrics}` },
          ]}
        />
        <Table<FavoriteItem>
          rowKey="id"
          columns={columns}
          dataSource={visibleItems}
          loading={loading}
          locale={{ emptyText: <Empty description="暂无收藏记录" /> }}
          pagination={{ pageSize: 8, showSizeChanger: false, hideOnSinglePage: true }}
          scroll={{ x: 955 }}
          className="data-table favorites-table"
          expandable={{
            expandedRowKeys,
            showExpandColumn: false,
            expandedRowRender: (item) => (
              <div className="favorite-note-editor">
                <div>
                  <Typography.Title level={3}>内部备注</Typography.Title>
                  <Typography.Text type="secondary">最后更新 {formatDateTime(item.updated_at)}</Typography.Text>
                </div>
                <Input.TextArea
                  value={noteDrafts[item.id] ?? item.note ?? ''}
                  rows={3}
                  maxLength={2000}
                  showCount
                  placeholder="记录选择理由、后续修改方向或制作安排"
                  onChange={(event) => setNoteDrafts((drafts) => ({
                    ...drafts,
                    [item.id]: event.target.value,
                  }))}
                />
                <Button
                  type="primary"
                  icon={<Save size={16} />}
                  loading={savingNoteId === item.id}
                  onClick={() => void saveNote(item)}
                >
                  保存备注
                </Button>
              </div>
            ),
          }}
        />
      </section>
    </div>
  )
}
