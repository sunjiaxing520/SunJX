import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Button, Drawer, Empty, Input, Skeleton, Tabs, Tag, Typography } from 'antd'
import { Check, ChevronRight, Clock3, FolderSearch, Search } from 'lucide-react'

export interface UpstreamOutputMeta {
  label: string
  value: string
}

export interface UpstreamOutputItem {
  id: number | string
  title: string
  source: string
  summary: string
  createdAt?: string
  group?: string
  tags?: string[]
  meta?: UpstreamOutputMeta[]
  searchText?: string
}

export interface UpstreamOutputGroup {
  key: string
  label: string
}

interface UpstreamOutputFieldProps {
  label: string
  placeholder: string
  item: UpstreamOutputItem | null
  disabled?: boolean
  onClick: () => void
}

interface UpstreamOutputPickerProps {
  open: boolean
  title: string
  description: string
  items: UpstreamOutputItem[]
  selectedId?: number | string | null
  groups?: UpstreamOutputGroup[]
  loading?: boolean
  emptyText?: string
  searchPlaceholder?: string
  confirmLabel?: string
  onClose: () => void
  onConfirm: (item: UpstreamOutputItem) => void
  onPreviewChange?: (item: UpstreamOutputItem) => void
  renderPreview?: (item: UpstreamOutputItem) => ReactNode
}

function sameId(left: number | string | null | undefined, right: number | string): boolean {
  return left !== null && left !== undefined && String(left) === String(right)
}

function formatDateTime(value?: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', { hour12: false })
}

export function UpstreamOutputField({
  label,
  placeholder,
  item,
  disabled = false,
  onClick,
}: UpstreamOutputFieldProps) {
  const createdAt = formatDateTime(item?.createdAt)
  return (
    <button
      type="button"
      className={`upstream-output-field ${item ? 'selected' : ''}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="upstream-output-field-icon"><FolderSearch size={18} /></span>
      <span className="upstream-output-field-copy">
        <small>{label}</small>
        <strong>{item?.title ?? placeholder}</strong>
        {item && <span>{item.summary}</span>}
        {item && (
          <span className="upstream-output-field-meta">
            <span>{item.source}</span>
            {createdAt && <span>{createdAt}</span>}
          </span>
        )}
      </span>
      <span className="upstream-output-field-action">
        {item ? '更换' : '选择'}
        <ChevronRight size={16} />
      </span>
    </button>
  )
}

export function UpstreamOutputPicker({
  open,
  title,
  description,
  items,
  selectedId,
  groups = [],
  loading = false,
  emptyText = '暂无可用产出',
  searchPlaceholder = '搜索标题、任务编号或内容关键词',
  confirmLabel = '选择此产出',
  onClose,
  onConfirm,
  onPreviewChange,
  renderPreview,
}: UpstreamOutputPickerProps) {
  const [search, setSearch] = useState('')
  const [activeGroup, setActiveGroup] = useState('all')
  const [previewId, setPreviewId] = useState<number | string | null>(null)

  useEffect(() => {
    if (!open) return
    setSearch('')
    setActiveGroup('all')
    setPreviewId(selectedId ?? items[0]?.id ?? null)
  }, [open, selectedId, items])

  const normalizedSearch = search.trim().toLocaleLowerCase('zh-CN')
  const filteredItems = useMemo(() => items.filter((item) => {
    if (activeGroup !== 'all' && item.group !== activeGroup) return false
    if (!normalizedSearch) return true
    const haystack = [
      item.title,
      item.source,
      item.summary,
      item.searchText,
      ...(item.tags ?? []),
      ...(item.meta ?? []).flatMap((meta) => [meta.label, meta.value]),
    ].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
    return haystack.includes(normalizedSearch)
  }), [activeGroup, items, normalizedSearch])

  const activeItem = filteredItems.find((item) => sameId(previewId, item.id))
    ?? filteredItems[0]
    ?? null

  useEffect(() => {
    if (open && activeItem) onPreviewChange?.(activeItem)
  }, [activeItem, onPreviewChange, open])

  const tabItems = [
    { key: 'all', label: `最近产出 (${items.length})` },
    ...groups.map((group) => ({
      key: group.key,
      label: `${group.label} (${items.filter((item) => item.group === group.key).length})`,
    })),
  ]

  return (
    <Drawer
      title={title}
      open={open}
      onClose={onClose}
      width={1040}
      destroyOnHidden
      rootClassName="upstream-output-drawer"
      footer={(
        <div className="upstream-output-footer">
          <Typography.Text type="secondary">
            {activeItem ? `正在预览：${activeItem.title}` : '请选择一条产出后继续'}
          </Typography.Text>
          <Button
            type="primary"
            icon={<Check size={16} />}
            disabled={!activeItem}
            onClick={() => activeItem && onConfirm(activeItem)}
          >
            {confirmLabel}
          </Button>
        </div>
      )}
    >
      <div className="upstream-output-picker">
        <div className="upstream-output-toolbar">
          <Typography.Paragraph type="secondary">{description}</Typography.Paragraph>
          <Input
            allowClear
            prefix={<Search size={15} />}
            value={search}
            placeholder={searchPlaceholder}
            aria-label="搜索上游产出"
            onChange={(event) => setSearch(event.target.value)}
          />
          {tabItems.length > 1 && (
            <Tabs
              size="small"
              activeKey={activeGroup}
              items={tabItems}
              onChange={(key) => {
                setActiveGroup(key)
                setPreviewId(null)
              }}
            />
          )}
        </div>

        <div className="upstream-output-layout">
          <div className="upstream-output-results" aria-label="上游产出列表">
            {loading ? (
              <Skeleton active paragraph={{ rows: 7 }} title={false} />
            ) : filteredItems.length ? filteredItems.map((item) => {
              const active = activeItem ? sameId(activeItem.id, item.id) : false
              const selected = sameId(selectedId, item.id)
              const createdAt = formatDateTime(item.createdAt)
              return (
                <button
                  type="button"
                  key={item.id}
                  className={`upstream-output-result ${active ? 'active' : ''}`}
                  aria-pressed={active}
                  onClick={() => setPreviewId(item.id)}
                >
                  <span className="upstream-output-result-heading">
                    <strong>{item.title}</strong>
                    {selected && <Tag color="success">当前已选</Tag>}
                  </span>
                  <span className="upstream-output-result-source">{item.source}</span>
                  <span className="upstream-output-result-summary">{item.summary}</span>
                  <span className="upstream-output-result-foot">
                    <span>{createdAt && <><Clock3 size={12} />{createdAt}</>}</span>
                    <span>{item.tags?.slice(0, 2).join(' · ')}</span>
                  </span>
                </button>
              )
            }) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={normalizedSearch ? '没有匹配的产出' : emptyText} />
            )}
          </div>

          <div className="upstream-output-preview" aria-label="上游产出预览">
            {activeItem ? (
              <>
                <div className="upstream-output-preview-heading">
                  <span>{activeItem.source}</span>
                  <Typography.Title level={3}>{activeItem.title}</Typography.Title>
                  <Typography.Paragraph>{activeItem.summary}</Typography.Paragraph>
                  {activeItem.tags?.length ? (
                    <div className="upstream-output-preview-tags">
                      {activeItem.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
                    </div>
                  ) : null}
                </div>
                {activeItem.meta?.length ? (
                  <dl className="upstream-output-preview-meta">
                    {activeItem.meta.map((meta) => (
                      <div key={`${meta.label}-${meta.value}`}>
                        <dt>{meta.label}</dt>
                        <dd>{meta.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                {renderPreview?.(activeItem)}
              </>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="从左侧选择一条产出查看详情" />
            )}
          </div>
        </div>
      </div>
    </Drawer>
  )
}
