import { App } from 'antd'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as memoryApi from '../api/lyricsMemory'
import type { LyricsTeamMemory } from '../types/api'
import { LyricsTeamMemoryDrawer } from './LyricsTeamMemoryDrawer'


vi.mock('../api/lyricsMemory', () => ({
  getLyricsTeamMemory: vi.fn(),
  listLyricsMemoryChat: vi.fn(),
  updateLyricsMemoryByChat: vi.fn(),
  updateLyricsMemoryInjectionLimit: vi.fn(),
}))

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

const memory: LyricsTeamMemory = {
  items: [
    { category: 'preference', content: '副歌核心句简短直接。', evidence_count: 3 },
    { category: 'pattern', content: '主歌使用连续场景推进叙事。', evidence_count: 2 },
  ],
  total_items: 2,
  injection_limit: 60,
  source_count: 4,
  revision: 5,
  updated_by_id: 1,
  updated_at: '2026-09-06T08:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(memoryApi.getLyricsTeamMemory).mockResolvedValue(memory)
  vi.mocked(memoryApi.listLyricsMemoryChat).mockResolvedValue({ items: [] })
  vi.mocked(memoryApi.updateLyricsMemoryInjectionLimit).mockResolvedValue({
    ...memory,
    injection_limit: 24,
  })
})

afterEach(cleanup)

describe('LyricsTeamMemoryDrawer', () => {
  it('shows the consolidated memory and updates the injection limit', async () => {
    const user = userEvent.setup()
    render(
      <App>
        <LyricsTeamMemoryDrawer open onClose={vi.fn()} />
      </App>,
    )

    expect(await screen.findByText('副歌核心句简短直接。')).toBeInTheDocument()
    expect(screen.getByText('命中 3 次')).toBeInTheDocument()

    const input = screen.getByRole('spinbutton', { name: '单次注入数量' })
    await user.clear(input)
    await user.type(input, '24')
    await user.click(screen.getByRole('button', { name: /保存/ }))

    await waitFor(() => {
      expect(memoryApi.updateLyricsMemoryInjectionLimit).toHaveBeenCalledWith(24)
    })
  })

  it('sends an admin instruction and applies the returned memory directly', async () => {
    const user = userEvent.setup()
    vi.mocked(memoryApi.updateLyricsMemoryByChat).mockResolvedValue({
      message: {
        id: 2,
        role: 'assistant',
        content: '已合并重复内容。',
        is_applied: true,
        provider: 'local',
        model: null,
        created_by_id: 1,
        created_at: '2026-09-06T08:02:00Z',
        applied_at: '2026-09-06T08:02:00Z',
      },
      memory,
    })
    vi.mocked(memoryApi.listLyricsMemoryChat)
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({
        items: [
          {
            id: 1,
            role: 'user',
            content: '合并重复内容',
            is_applied: false,
            provider: null,
            model: null,
            created_by_id: 1,
            created_at: '2026-09-06T08:01:00Z',
            applied_at: null,
          },
          {
            id: 2,
            role: 'assistant',
            content: '已合并重复内容。',
            is_applied: true,
            provider: 'local',
            model: null,
            created_by_id: 1,
            created_at: '2026-09-06T08:02:00Z',
            applied_at: '2026-09-06T08:02:00Z',
          },
        ],
      })

    render(
      <App>
        <LyricsTeamMemoryDrawer open onClose={vi.fn()} />
      </App>,
    )
    const input = await screen.findByRole('textbox', { name: '记忆修改要求' })
    await user.type(input, '合并重复内容')
    await user.click(screen.getByRole('button', { name: /发送并更新/ }))

    expect(await screen.findByText('已合并重复内容。')).toBeInTheDocument()
    expect(memoryApi.updateLyricsMemoryByChat).toHaveBeenCalledWith('合并重复内容')
  })
})
