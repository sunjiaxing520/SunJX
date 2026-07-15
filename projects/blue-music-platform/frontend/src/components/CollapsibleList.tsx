import { useState, type ReactNode } from 'react'
import { Button } from 'antd'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface CollapsibleListProps<Item> {
  items: readonly Item[]
  children: (visibleItems: Item[]) => ReactNode
  previewCount?: number
  previewFrom?: 'start' | 'end'
  expandText?: (hiddenCount: number) => string
  collapseText?: string
}

export function CollapsibleList<Item>({
  items,
  children,
  previewCount = 5,
  previewFrom = 'start',
  expandText = (hiddenCount) => `展开其余 ${hiddenCount} 条`,
  collapseText = '收起记录',
}: CollapsibleListProps<Item>) {
  const [expanded, setExpanded] = useState(false)
  const safePreviewCount = Math.max(1, previewCount)
  const hiddenCount = Math.max(0, items.length - safePreviewCount)
  const visibleItems = expanded
    ? Array.from(items)
    : Array.from(
        previewFrom === 'end'
          ? items.slice(-safePreviewCount)
          : items.slice(0, safePreviewCount),
      )

  return (
    <div className="collapsible-list">
      {children(visibleItems)}
      {hiddenCount > 0 && (
        <div className="collapsible-list-toggle">
          <Button
            type="text"
            size="small"
            icon={expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? collapseText : expandText(hiddenCount)}
          </Button>
        </div>
      )}
    </div>
  )
}
