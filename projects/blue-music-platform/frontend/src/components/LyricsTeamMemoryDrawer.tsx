import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Collapse,
  Drawer,
  Empty,
  Input,
  InputNumber,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { Save, Send } from 'lucide-react'

import {
  getLyricsTeamMemory,
  listLyricsMemoryChat,
  updateLyricsMemoryByChat,
  updateLyricsMemoryInjectionLimit,
} from '../api/lyricsMemory'
import { errorMessage } from '../lib/errors'
import type {
  LyricsMemoryCategory,
  LyricsMemoryChatMessage,
  LyricsMemoryItem,
  LyricsTeamMemory,
} from '../types/api'
import { CollapsibleList } from './CollapsibleList'


const CATEGORY_ORDER: LyricsMemoryCategory[] = [
  'preference',
  'technique',
  'pattern',
  'highlight',
  'result',
]

const CATEGORY_LABELS: Record<LyricsMemoryCategory, string> = {
  preference: '用户偏好',
  technique: '创作方法',
  result: '有效结果',
  pattern: '复用规律',
  highlight: '亮点经验',
}

interface LyricsTeamMemoryDrawerProps {
  open: boolean
  onClose: () => void
}

export function LyricsTeamMemoryDrawer({ open, onClose }: LyricsTeamMemoryDrawerProps) {
  const { message } = App.useApp()
  const [memory, setMemory] = useState<LyricsTeamMemory | null>(null)
  const [chat, setChat] = useState<LyricsMemoryChatMessage[]>([])
  const [instruction, setInstruction] = useState('')
  const [injectionLimit, setInjectionLimit] = useState<number>(60)
  const [loading, setLoading] = useState(false)
  const [savingLimit, setSavingLimit] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [currentMemory, history] = await Promise.all([
        getLyricsTeamMemory(),
        listLyricsMemoryChat(),
      ])
      setMemory(currentMemory)
      setInjectionLimit(currentMemory.injection_limit)
      setChat(history.items)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) void load()
  }, [load, open])

  const groupedItems = useMemo(() => {
    const groups = new Map<LyricsMemoryCategory, LyricsMemoryItem[]>()
    for (const category of CATEGORY_ORDER) groups.set(category, [])
    for (const item of memory?.items ?? []) groups.get(item.category)?.push(item)
    return groups
  }, [memory])

  const saveLimit = async () => {
    setSavingLimit(true)
    try {
      const updated = await updateLyricsMemoryInjectionLimit(injectionLimit)
      setMemory(updated)
      setInjectionLimit(updated.injection_limit)
      message.success('单次注入数量已更新')
    } catch (saveError) {
      message.error(errorMessage(saveError))
    } finally {
      setSavingLimit(false)
    }
  }

  const sendInstruction = async () => {
    const value = instruction.trim()
    if (!value) return
    setSending(true)
    try {
      const result = await updateLyricsMemoryByChat(value)
      const history = await listLyricsMemoryChat()
      setMemory(result.memory)
      setChat(history.items)
      setInstruction('')
      message.success('团队记忆已更新')
    } catch (sendError) {
      message.error(errorMessage(sendError))
    } finally {
      setSending(false)
    }
  }

  const memoryPanels = CATEGORY_ORDER.flatMap((category) => {
    const items = groupedItems.get(category) ?? []
    if (!items.length) return []
    return [{
      key: category,
      label: (
        <span className="lyrics-team-memory-category-label">
          <strong>{CATEGORY_LABELS[category]}</strong>
          <Tag>{items.length}</Tag>
        </span>
      ),
      children: (
        <CollapsibleList items={items} previewCount={8}>
          {(visibleItems) => (
            <div className="lyrics-team-memory-items">
              {visibleItems.map((item, index) => (
                <div className="lyrics-team-memory-item" key={`${item.content}-${index}`}>
                  <Typography.Text>{item.content}</Typography.Text>
                  <span>命中 {item.evidence_count} 次</span>
                </div>
              ))}
            </div>
          )}
        </CollapsibleList>
      ),
    }]
  })

  return (
    <Drawer
      title="团队歌词记忆"
      open={open}
      onClose={onClose}
      size="large"
      className="lyrics-team-memory-drawer"
    >
      {error && <Alert type="error" showIcon title={error} />}
      {loading && !memory ? (
        <div className="lyrics-team-memory-loading"><Spin /></div>
      ) : (
        <div className="lyrics-team-memory-layout">
          <section className="lyrics-team-memory-overview">
            <div className="lyrics-team-memory-stats">
              <div><span>记忆总数</span><strong>{memory?.total_items ?? 0}</strong></div>
              <div><span>确认作品</span><strong>{memory?.source_count ?? 0}</strong></div>
              <div><span>记忆版本</span><strong>{memory?.revision ?? 0}</strong></div>
            </div>
            <div className="lyrics-team-memory-limit">
              <Typography.Text strong>单次注入数量</Typography.Text>
              <Space.Compact>
                <InputNumber
                  min={1}
                  max={200}
                  value={injectionLimit}
                  onChange={(value) => setInjectionLimit(value ?? 60)}
                  aria-label="单次注入数量"
                />
                <Button
                  icon={<Save size={16} />}
                  loading={savingLimit}
                  onClick={() => void saveLimit()}
                >
                  保存
                </Button>
              </Space.Compact>
            </div>
          </section>

          <section>
            <Typography.Title level={3}>当前记忆</Typography.Title>
            {memoryPanels.length ? (
              <Collapse items={memoryPanels} defaultActiveKey={memoryPanels[0]?.key} />
            ) : (
              <Empty description="确认并保存歌词后，提炼结果会写入这里" />
            )}
          </section>

          <section className="lyrics-team-memory-chat">
            <Typography.Title level={3}>AI 记忆助手</Typography.Title>
            <div className="lyrics-team-memory-chat-history">
              {chat.length ? chat.map((item) => (
                <div className={`lyrics-team-memory-chat-message ${item.role}`} key={item.id}>
                  <strong>{item.role === 'user' ? '管理员' : 'AI 助手'}</strong>
                  <Typography.Paragraph>{item.content}</Typography.Paragraph>
                </div>
              )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无修改记录" />}
            </div>
            <Input.TextArea
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              maxLength={2000}
              autoSize={{ minRows: 3, maxRows: 7 }}
              placeholder="例如：合并重复的副歌经验，并删除不再适用的规则"
              aria-label="记忆修改要求"
            />
            <Button
              type="primary"
              icon={<Send size={16} />}
              loading={sending}
              disabled={!instruction.trim()}
              onClick={() => void sendInstruction()}
            >
              发送并更新
            </Button>
          </section>
        </div>
      )}
    </Drawer>
  )
}
