import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { CollapsibleList } from './CollapsibleList'

afterEach(cleanup)

function renderItems(items: string[], previewFrom: 'start' | 'end' = 'start') {
  return render(
    <CollapsibleList items={items} previewCount={2} previewFrom={previewFrom}>
      {(visibleItems) => (
        <ul>
          {visibleItems.map((item) => <li key={item}>{item}</li>)}
        </ul>
      )}
    </CollapsibleList>,
  )
}

describe('CollapsibleList', () => {
  it('shows a preview and expands the remaining items', async () => {
    const user = userEvent.setup()
    renderItems(['最新', '第二条', '较早'])

    expect(screen.getByText('最新')).toBeInTheDocument()
    expect(screen.queryByText('较早')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '展开其余 1 条' }))

    expect(screen.getByText('较早')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '收起记录' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('can preview the newest items from the end of a chronological list', () => {
    renderItems(['最早', '中间', '最新'], 'end')

    expect(screen.queryByText('最早')).not.toBeInTheDocument()
    expect(screen.getByText('中间')).toBeInTheDocument()
    expect(screen.getByText('最新')).toBeInTheDocument()
  })
})
