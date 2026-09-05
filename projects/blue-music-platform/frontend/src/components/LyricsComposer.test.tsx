import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import { LyricsComposer } from './LyricsComposer'
import type { UpstreamOutputItem } from './UpstreamOutputPicker'

vi.stubGlobal('ResizeObserver', class {
  observe() {}
  unobserve() {}
  disconnect() {}
})

const analysis: UpstreamOutputItem = {
  id: '20:0', title: '晚风与重逢', source: '榜单分析 #43 · 报告 #20 · 方向 1',
  summary: '温暖的兄弟情', createdAt: '2026-09-05T10:00:00Z', group: 'S',
  tags: ['民谣'], meta: [],
}

afterEach(cleanup)

it('requires an analysis selection, not manual feature fields or an adjustment', async () => {
  const user = userEvent.setup()
  const onChooseAnalysis = vi.fn()
  const onSubmit = vi.fn().mockResolvedValue(true)
  const props = { loading: false, onChooseAnalysis, onSubmit }
  const view = render(<LyricsComposer {...props} selectedAnalysis={null} />)
  expect(screen.getByRole('button', { name: '生成歌词' })).toBeDisabled()
  expect(screen.getAllByRole('textbox')).toHaveLength(1)
  expect(screen.queryByLabelText('歌曲主题')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /引用分析方向/ }))
  expect(onChooseAnalysis).toHaveBeenCalledOnce()

  view.rerender(<LyricsComposer {...props} selectedAnalysis={analysis} />)
  expect(screen.getByText(/榜单分析 #43/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '生成歌词' }))
  expect(onSubmit).toHaveBeenCalledWith('analysis', '')
})

it('keeps separate drafts and submits only the active mode', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn().mockResolvedValue(true)
  render(<LyricsComposer selectedAnalysis={analysis} loading={false} onChooseAnalysis={vi.fn()} onSubmit={onSubmit} />)
  await user.type(screen.getByLabelText('细节调整（选填）'), '副歌更温暖')
  await user.click(screen.getByText('自由描述创作'))
  expect(screen.queryByRole('button', { name: /引用分析方向/ })).not.toBeInTheDocument()
  expect(screen.getByLabelText('创作描述')).toHaveValue('')
  expect(screen.getByRole('button', { name: '生成歌词' })).toBeDisabled()
  await user.type(screen.getByLabelText('创作描述'), '  写一首励志歌曲  ')
  await user.click(screen.getByText('根据分析创作'))
  expect(screen.getByLabelText('细节调整（选填）')).toHaveValue('副歌更温暖')
  await user.click(screen.getByText('自由描述创作'))
  await user.click(screen.getByRole('button', { name: '生成歌词' }))
  expect(onSubmit).toHaveBeenCalledWith('prompt', '写一首励志歌曲')
  await waitFor(() => expect(screen.getByLabelText('创作描述')).toHaveValue(''))
  await user.click(screen.getByText('根据分析创作'))
  expect(screen.getByLabelText('细节调整（选填）')).toHaveValue('副歌更温暖')
})

it('preserves input on failure and prevents changes during generation', async () => {
  const user = userEvent.setup()
  const props = { selectedAnalysis: analysis, onChooseAnalysis: vi.fn(), onSubmit: vi.fn().mockResolvedValue(false) }
  const view = render(<LyricsComposer {...props} loading={false} />)
  await user.type(screen.getByLabelText('细节调整（选填）'), '歌名《并肩》')
  await user.click(screen.getByRole('button', { name: '生成歌词' }))
  expect(screen.getByLabelText('细节调整（选填）')).toHaveValue('歌名《并肩》')
  view.rerender(<LyricsComposer {...props} loading />)
  expect(screen.getByLabelText('细节调整（选填）')).toBeDisabled()
  expect(screen.getByRole('button', { name: /引用分析方向/ })).toBeDisabled()
  for (const mode of screen.getAllByRole('radio')) expect(mode).toBeDisabled()
})
