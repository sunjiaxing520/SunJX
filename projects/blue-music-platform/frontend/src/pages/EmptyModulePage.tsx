import { Button, Empty, Typography } from 'antd'
import { RefreshCw } from 'lucide-react'

export function EmptyModulePage({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div>
          <Typography.Title level={1}>{title}</Typography.Title>
          <Typography.Text type="secondary">{description}</Typography.Text>
        </div>
        <Button icon={<RefreshCw size={16} />}>刷新</Button>
      </div>
      <section className="module-empty-state">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无${title}记录`} />
      </section>
    </div>
  )
}
