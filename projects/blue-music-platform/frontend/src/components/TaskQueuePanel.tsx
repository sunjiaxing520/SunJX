import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Empty, Space, Tag, Typography } from 'antd'
import { Clock3, RefreshCw } from 'lucide-react'
import { apiRequest } from '../api/client'
import { errorMessage } from '../lib/errors'

type QueueItem = {
  kind: 'workflow' | 'music'
  id: number
  title: string
  status: string
  position: number | null
  expires_at: string | null
}
type QueueStatus = { limit: number; active_count: number; items: QueueItem[] }

export function TaskQueuePanel() {
  const [queue, setQueue] = useState<QueueStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setQueue(await apiRequest<QueueStatus>('/workflows/queue'))
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 5000)
    return () => window.clearInterval(timer)
  }, [refresh])
  return (
    <section className="task-queue-panel">
      <div className="task-queue-heading">
        <Space><Clock3 size={18} /><strong>我的任务队列</strong><Tag>{queue ? `${queue.active_count} / ${queue.limit}` : '加载中'}</Tag></Space>
        <Button icon={<RefreshCw size={15} />} loading={loading} onClick={() => void refresh()}>刷新</Button>
      </div>
      {error && <Alert type="error" showIcon title={error} />}
      {queue?.active_count === queue?.limit && queue && <Alert type="warning" showIcon title="两个任务名额已满" />}
      {queue && !queue.items.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无排队任务" />}
      {queue?.items.map((item) => (
        <div className="task-queue-row" key={`${item.kind}-${item.id}`}>
          <div><strong>{item.title}</strong><Typography.Text type="secondary">{item.kind === 'workflow' ? '流程' : '音乐'} #{item.id}</Typography.Text></div>
          <div>
            <Tag color={item.status === 'paused' ? 'orange' : item.status === 'running' ? 'processing' : 'default'}>
              {item.status === 'paused' ? '待人工处理' : item.status === 'running' ? '正在执行' : `排队第 ${item.position} 位`}
            </Tag>
            {item.expires_at && <Typography.Text type="secondary">记录清理时间：{new Date(item.expires_at).toLocaleString('zh-CN')}</Typography.Text>}
          </div>
        </div>
      ))}
    </section>
  )
}
