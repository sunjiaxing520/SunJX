import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Tag, Tooltip } from 'antd'
import { ChevronDown, ChevronUp, Clock3, RefreshCw } from 'lucide-react'
import { apiRequest } from '../api/client'
import { errorMessage } from '../lib/errors'

type QueueItem = {
  kind: 'workflow' | 'music'
  id: number
  title: string
  status: string
  position: number | null
  expires_at: string | null
  current_step?: string | null
}
type QueueStatus = { limit: number; active_count: number; items: QueueItem[] }

export function TaskQueuePanel() {
  const [queue, setQueue] = useState<QueueStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const requestId = useRef(0)
  const initialLoad = useRef(true)
  const refresh = useCallback(async (silent = false) => {
    const id = ++requestId.current
    if (!silent) setLoading(true)
    try {
      const next = await apiRequest<QueueStatus>('/workflows/queue')
      if (id !== requestId.current) return
      setQueue(next)
      if (initialLoad.current) {
        setExpanded(next.active_count > 0)
        initialLoad.current = false
      }
      setError(null)
    } catch (err) {
      if (id === requestId.current) setError(errorMessage(err))
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(true), 5000)
    return () => { window.clearInterval(timer); requestId.current += 1 }
  }, [refresh])
  return (
    <section className="task-queue-panel">
      <div className="task-queue-heading">
        <button className="task-queue-toggle" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          <Clock3 size={18} /><strong>我的任务队列</strong><Tag>{queue ? `${queue.active_count} / ${queue.limit}` : '加载中'}</Tag>
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        <div className="task-queue-summary">
          {queue && <span>{queue.active_count ? `${queue.items.filter((item) => item.status === 'running').length} 执行 · ${queue.items.filter((item) => item.status === 'pending').length} 排队 · ${queue.items.filter((item) => item.status === 'paused').length} 待处理` : '可提交新任务'}</span>}
          <Tooltip title="刷新任务队列"><Button aria-label="刷新任务队列" icon={<RefreshCw size={15} />} loading={loading} onClick={() => void refresh()} /></Tooltip>
        </div>
      </div>
      {error && <Alert type="error" showIcon title={error} />}
      {expanded && queue?.active_count === queue?.limit && queue && <Alert type="warning" showIcon title="两个任务名额已满" />}
      {expanded && queue && !queue.items.length && <p className="task-queue-empty">暂无排队任务</p>}
      {expanded && queue?.items.map((item) => (
        <div className="task-queue-row" key={`${item.kind}-${item.id}`}>
          <div><strong>{item.title}</strong><small>{item.kind === 'workflow' ? '流程队列' : '音乐队列'} · #{item.id}</small></div>
          <div>
            <Tag color={item.status === 'paused' ? 'orange' : item.status === 'running' ? 'processing' : 'default'}>
              {item.status === 'paused' ? '待人工处理' : item.status === 'running' ? '正在执行' : `排队第 ${item.position} 位`}
            </Tag>
            {item.current_step && item.status === 'running' && <small>{({ collection: '榜单采集', analysis: '内容分析', lyrics: '歌词创作', review: '歌词审核', music: '音乐生成' } as Record<string, string>)[item.current_step] || item.current_step}</small>}
            {item.expires_at && <small>待处理记录清理：{new Date(item.expires_at).toLocaleString('zh-CN')}</small>}
          </div>
        </div>
      ))}
    </section>
  )
}
