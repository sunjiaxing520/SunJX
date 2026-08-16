import { App } from 'antd'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as favoriteApi from '../api/favorites'
import * as reviewAgentApi from '../api/reviewAgents'
import * as userApi from '../api/users'
import type {
  LyricsAssistantMessage,
  LyricsVersion,
  ReviewAgent,
  ReviewResult,
  User,
} from '../types/api'
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
  listReviewRevisionMessages: vi.fn(),
  listReviewRuns: vi.fn(),
  previewReviewAgentInitialization: vi.fn(),
  requestReviewRevisionPreview: vi.fn(),
  confirmReviewRevisionPreview: vi.fn(),
  saveReviewAgentMemory: vi.fn(),
  updateReviewAgentMembers: vi.fn(),
  updateReviewAgentSettings: vi.fn(),
}))

vi.mock('../api/favorites', () => ({
  listFavorites: vi.fn(),
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

const reviewRun: ReviewResult = {
  id: 77,
  agent_id: 10,
  lyrics_version_id: 31,
  requested_by_id: 1,
  instruction: null,
  provider: 'kimi',
  model: 'kimi-k3',
  result: {
    overall_score: 72,
    pass_score: 80,
    passed: false,
    summary: '整体结构完整，但副歌记忆点不足。',
    dimensions: [
      { name: '韵律', score: 72, feedback: '部分句尾押韵不够自然。' },
    ],
    strengths: ['主歌叙事清楚'],
    deduction_reasons: ['副歌核心句辨识度不足'],
    revision_suggestions: ['缩短副歌句子并增加重复'],
    risk_notes: [],
  },
  created_at: '2026-08-16T09:00:00Z',
}

const revisionUserMessage: LyricsAssistantMessage = {
  id: 90,
  task_id: 12,
  source_version_id: 31,
  role: 'user',
  content: '让副歌更有记忆点，并处理审核报告里的押韵问题。',
  preview: null,
  provider: null,
  model: null,
  created_at: '2026-08-16T09:10:00Z',
}

const revisionPreviewMessage: LyricsAssistantMessage = {
  id: 91,
  task_id: 12,
  source_version_id: 31,
  role: 'assistant',
  content: '已生成一份预览，确认满意后再保存为正式版本。',
  preview: {
    title: '改写后的副歌',
    content: '[副歌]\n把月光唱成一句回响',
    style_prompt: '中文流行，清晰副歌记忆点',
    sections: [{ name: '副歌', content: '把月光唱成一句回响' }],
  },
  provider: 'kimi',
  model: 'kimi-k3',
  created_at: '2026-08-16T09:10:02Z',
}

const savedRevision: LyricsVersion = {
  id: 32,
  task_id: 12,
  version_number: 3,
  title: '改写后的副歌',
  content: '[副歌]\n把月光唱成一句回响',
  style_prompt: '中文流行，清晰副歌记忆点',
  sections: [{ name: '副歌', content: '把月光唱成一句回响' }],
  is_saved: true,
  created_at: '2026-08-16T09:11:00Z',
}

afterEach(cleanup)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(reviewAgentApi.listReviewAgents).mockResolvedValue([reviewAgent])
  vi.mocked(favoriteApi.listFavorites).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(reviewAgentApi.listReviewLyricsOptions).mockResolvedValue([])
  vi.mocked(reviewAgentApi.listReviewRevisionMessages).mockResolvedValue({ items: [] })
  vi.mocked(reviewAgentApi.listReviewRuns).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(reviewAgentApi.requestReviewRevisionPreview).mockResolvedValue(revisionPreviewMessage)
  vi.mocked(reviewAgentApi.confirmReviewRevisionPreview).mockResolvedValue(savedRevision)
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

  it('keeps review reports collapsed until requested', async () => {
    const user = userEvent.setup()
    vi.mocked(reviewAgentApi.listReviewRuns).mockResolvedValue({ items: [reviewRun], total: 1 })
    render(
      <App>
        <ReviewAgentsPage />
      </App>,
    )

    await screen.findByText('审核 #77')
    expect(reviewAgentApi.listReviewRevisionMessages).not.toHaveBeenCalled()
    expect(screen.queryByRole('textbox', { name: '审核后歌词修改要求' })).not.toBeInTheDocument()
    expect(screen.queryByText('整体结构完整，但副歌记忆点不足。')).not.toBeInTheDocument()

    const expandButton = screen.getByRole('button', { name: '展开审核结果' })
    expect(expandButton).toHaveAttribute('aria-expanded', 'false')
    await user.click(expandButton)

    expect(screen.getByText('整体结构完整，但副歌记忆点不足。')).toBeInTheDocument()
    expect(screen.getByText('副歌核心句辨识度不足')).toBeInTheDocument()

    const hideButton = screen.getByRole('button', { name: '隐藏审核结果' })
    expect(hideButton).toHaveAttribute('aria-expanded', 'true')
    await user.click(hideButton)

    expect(screen.queryByText('整体结构完整，但副歌记忆点不足。')).not.toBeInTheDocument()
  })

  it('revises from a collapsed review and saves the selected preview as current', async () => {
    const user = userEvent.setup()
    vi.mocked(reviewAgentApi.listReviewRuns).mockResolvedValue({ items: [reviewRun], total: 1 })
    vi.mocked(reviewAgentApi.listReviewRevisionMessages)
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [revisionUserMessage, revisionPreviewMessage] })

    render(
      <App>
        <ReviewAgentsPage />
      </App>,
    )

    await screen.findByText('审核 #77')
    expect(screen.queryByText('整体结构完整，但副歌记忆点不足。')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '展开 AI 修改' }))
    await waitFor(() => {
      expect(reviewAgentApi.listReviewRevisionMessages).toHaveBeenCalledWith(10, 77)
    })

    const revisionInput = screen.getByRole('textbox', { name: '审核后歌词修改要求' })
    await user.type(revisionInput, revisionUserMessage.content)
    await user.click(screen.getByRole('button', { name: '发送审核修改要求' }))

    await waitFor(() => {
      expect(reviewAgentApi.requestReviewRevisionPreview).toHaveBeenCalledWith(
        10,
        77,
        revisionUserMessage.content,
      )
    })
    expect(await screen.findByText('改写后的副歌')).toBeInTheDocument()
    expect(screen.getByText('把月光唱成一句回响', { exact: false })).toBeInTheDocument()
    expect(screen.queryByText('整体结构完整，但副歌记忆点不足。')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '保存并设为当前作品' }))
    await waitFor(() => {
      expect(reviewAgentApi.confirmReviewRevisionPreview).toHaveBeenCalledWith(10, 77, 91)
    })
    expect(await screen.findByRole('button', { name: '当前作品' })).toBeDisabled()
    expect(screen.getByText('当前作品 V3')).toBeInTheDocument()
  })

  it('shows only the latest two AI revision messages until older history is expanded', async () => {
    const user = userEvent.setup()
    const olderMessage: LyricsAssistantMessage = {
      ...revisionUserMessage,
      id: 89,
      content: '这是更早的一条修改要求。',
    }
    vi.mocked(reviewAgentApi.listReviewRuns).mockResolvedValue({ items: [reviewRun], total: 1 })
    vi.mocked(reviewAgentApi.listReviewRevisionMessages).mockResolvedValue({
      items: [olderMessage, revisionUserMessage, revisionPreviewMessage],
    })

    render(
      <App>
        <ReviewAgentsPage />
      </App>,
    )

    await screen.findByText('审核 #77')
    await user.click(screen.getByRole('button', { name: '展开 AI 修改' }))

    expect(await screen.findByText(revisionUserMessage.content)).toBeInTheDocument()
    expect(screen.getByText('改写后的副歌')).toBeInTheDocument()
    expect(screen.queryByText(olderMessage.content)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '展开更早 1 条' }))
    expect(screen.getByText(olderMessage.content)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '收起 AI 修改' }))
    expect(screen.queryByText(olderMessage.content)).not.toBeInTheDocument()
    expect(screen.getByText('已省略 3 条对话')).toBeInTheDocument()
  })
})
