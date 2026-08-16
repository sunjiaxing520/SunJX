import { App } from 'antd'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  UpstreamOutputField,
  UpstreamOutputPicker,
  type UpstreamOutputItem,
} from './UpstreamOutputPicker'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

const outputs: UpstreamOutputItem[] = [
  {
    id: 11,
    title: '月光方向',
    source: '榜单分析 #43 · 方向 1',
    summary: '围绕城市夜晚和离别展开。',
    createdAt: '2026-08-16T08:00:00Z',
    group: 'unclassified',
    tags: ['待分类', '中文流行'],
    meta: [{ label: '模型', value: 'kimi-k2.5' }],
  },
  {
    id: 12,
    title: '风吟细语',
    source: '榜单分析 #44 · 方向 2',
    summary: '轻快民谣方向，强调自然意象。',
    createdAt: '2026-08-16T09:00:00Z',
    group: 'S',
    tags: ['S 级', '民谣'],
    meta: [{ label: '模型', value: 'kimi-k2.5' }],
  },
]

afterEach(cleanup)

describe('UpstreamOutputPicker', () => {
  it('shows the current selection as a compact field', () => {
    render(
      <UpstreamOutputField
        label="引用分析方向"
        placeholder="请选择分析方向"
        item={outputs[0]}
        onClick={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /引用分析方向/ })).toHaveTextContent('月光方向')
    expect(screen.getByRole('button', { name: /引用分析方向/ })).toHaveTextContent('榜单分析 #43')
    expect(screen.getByText('更换')).toBeInTheDocument()
  })

  it('previews a candidate without changing the committed selection', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const onPreviewChange = vi.fn()

    render(
      <App>
        <UpstreamOutputPicker
          open
          title="选择分析方向"
          description="先查看详情，再明确确认。"
          items={outputs}
          selectedId={11}
          groups={[
            { key: 'unclassified', label: '待分类' },
            { key: 'S', label: 'S 级' },
          ]}
          onClose={vi.fn()}
          onConfirm={onConfirm}
          onPreviewChange={onPreviewChange}
          renderPreview={(item) => <div>完整预览：{item.title}</div>}
        />
      </App>,
    )

    const results = await screen.findByLabelText('上游产出列表')
    await user.click(within(results).getByRole('button', { name: /风吟细语/ }))

    expect(screen.getByText('完整预览：风吟细语')).toBeInTheDocument()
    expect(onPreviewChange).toHaveBeenLastCalledWith(outputs[1])
    expect(onConfirm).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '选择此产出' }))
    expect(onConfirm).toHaveBeenCalledWith(outputs[1])
  })

  it('filters outputs by category and search text', async () => {
    const user = userEvent.setup()

    render(
      <App>
        <UpstreamOutputPicker
          open
          title="选择分析方向"
          description="按分类或关键词寻找产出。"
          items={outputs}
          groups={[
            { key: 'unclassified', label: '待分类' },
            { key: 'S', label: 'S 级' },
          ]}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
        />
      </App>,
    )

    const results = await screen.findByLabelText('上游产出列表')
    await user.click(screen.getByRole('tab', { name: /S 级/ }))
    expect(within(results).queryByRole('button', { name: /月光方向/ })).not.toBeInTheDocument()
    expect(within(results).getByRole('button', { name: /风吟细语/ })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /最近产出/ }))
    await user.type(screen.getByRole('textbox', { name: '搜索上游产出' }), '城市夜晚')
    expect(within(results).getByRole('button', { name: /月光方向/ })).toBeInTheDocument()
    expect(within(results).queryByRole('button', { name: /风吟细语/ })).not.toBeInTheDocument()
  })
})
