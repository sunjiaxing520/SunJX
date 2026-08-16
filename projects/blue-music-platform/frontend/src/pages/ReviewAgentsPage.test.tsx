import { App } from 'antd'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as reviewAgentApi from '../api/reviewAgents'
import * as userApi from '../api/users'
import type { ReviewAgent, User } from '../types/api'
import { ReviewAgentsPage } from './ReviewAgentsPage'

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

vi.mock('../api/reviewAgents', () => ({
  createLyricsReview: vi.fn(),
  createReviewAgent: vi.fn(),
  listReviewAgents: vi.fn(),
  listReviewLyricsOptions: vi.fn(),
  listReviewRuns: vi.fn(),
  previewReviewAgentInitialization: vi.fn(),
  saveReviewAgentMemory: vi.fn(),
  updateReviewAgentMembers: vi.fn(),
  updateReviewAgentSettings: vi.fn(),
}))

vi.mock('../api/users', () => ({
  listUsers: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      username: 'admin',
      role: 'super_admin',
      is_active: true,
      agent_permissions: [],
      music_quota: { is_unlimited: true, remaining_tasks: null, used_tasks: 0 },
    },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

const reviewAgent: ReviewAgent = {
  id: 10,
  name: '中文歌词审核官',
  pass_score: 80,
  initialization_notes: '检查歌词结构和韵律。',
  memory_summary: '关注结构、韵律和副歌记忆点。',
  memory_detail: {},
  created_by_id: 1,
  members: [{ id: 2, username: 'member-a' }],
  created_at: '2026-08-16T08:00:00Z',
  updated_at: '2026-08-16T08:00:00Z',
}

const accounts: User[] = [
  {
    id: 1,
    username: 'admin',
    role: 'super_admin',
    is_active: true,
    agent_permissions: [],
    music_quota: { is_unlimited: true, remaining_tasks: null, used_tasks: 0 },
  },
  {
    id: 2,
    username: 'member-a',
    role: 'member',
    is_active: true,
    agent_permissions: [],
    music_quota: { is_unlimited: false, remaining_tasks: 3, used_tasks: 0 },
  },
  {
    id: 3,
    username: 'member-b',
    role: 'member',
    is_active: true,
    agent_permissions: [],
    music_quota: { is_unlimited: false, remaining_tasks: 3, used_tasks: 0 },
  },
]

afterEach(cleanup)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(reviewAgentApi.listReviewAgents).mockResolvedValue([reviewAgent])
  vi.mocked(reviewAgentApi.listReviewLyricsOptions).mockResolvedValue([])
  vi.mocked(reviewAgentApi.listReviewRuns).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(reviewAgentApi.updateReviewAgentMembers).mockResolvedValue({
    ...reviewAgent,
    members: [{ id: 3, username: 'member-b' }],
  })
  vi.mocked(userApi.listUsers).mockResolvedValue(accounts)
})

describe('ReviewAgentsPage member permissions', () => {
  it('loads members and supports multi-select toggling', async () => {
    const user = userEvent.setup()
    render(
      <App>
        <ReviewAgentsPage />
      </App>,
    )

    await screen.findByRole('heading', { level: 2, name: '中文歌词审核官' })
    await user.click(screen.getByText('成员权限'))

    const memberA = await screen.findByRole('checkbox', { name: /member-a/ })
    const memberB = screen.getByRole('checkbox', { name: /member-b/ })

    expect(memberA).toBeChecked()
    expect(memberB).not.toBeChecked()

    await user.click(memberB)
    expect(memberA).toBeChecked()
    expect(memberB).toBeChecked()

    await user.click(memberA)
    expect(memberA).not.toBeChecked()
    expect(memberB).toBeChecked()

    await user.click(screen.getByRole('button', { name: '保存成员权限' }))
    await waitFor(() => {
      expect(reviewAgentApi.updateReviewAgentMembers).toHaveBeenCalledWith(10, [3])
    })
  })
})
