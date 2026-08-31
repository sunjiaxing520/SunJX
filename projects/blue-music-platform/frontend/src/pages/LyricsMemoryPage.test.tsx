import { App } from 'antd'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as lyricsMemoryApi from '../api/lyricsMemory'
import type {
  LyricsMemoryChatMessage,
  LyricsMemoryEventSummary,
  LyricsMemoryOverview,
  LyricsMemoryPreview,
  LyricsMemorySnapshotDetail,
  LyricsMemorySnapshotSummary,
} from '../types/api'
import { LyricsMemoryPage } from './LyricsMemoryPage'

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

vi.mock('../api/lyricsMemory', () => ({
  applyLyricsMemoryChatProposal: vi.fn(),
  createLyricsMemoryRule: vi.fn(),
  createLyricsMemorySnapshot: vi.fn(),
  deleteLyricsMemoryEvent: vi.fn(),
  deleteLyricsMemoryEvents: vi.fn(),
  deleteLyricsMemorySnapshot: vi.fn(),
  distillNextLegacyLyricsMemory: vi.fn(),
  getLyricsMemoryEvent: vi.fn(),
  getLyricsMemoryOverview: vi.fn(),
  getLyricsMemoryPreview: vi.fn(),
  getLyricsMemorySnapshot: vi.fn(),
  listLyricsMemoryChat: vi.fn(),
  listLyricsMemoryEvents: vi.fn(),
  listLyricsMemorySnapshots: vi.fn(),
  renameLyricsMemorySnapshot: vi.fn(),
  requestLyricsMemoryChatPreview: vi.fn(),
  setLyricsMemoryUsefulness: vi.fn(),
}))

const overview: LyricsMemoryOverview = {
  total_events: 24,
  active_events: 22,
  inactive_events: 2,
  category_counts: {
    creation_request: 10,
    modification_request: 4,
    accepted_result: 5,
    ranking_lyrics_insight: 3,
    admin_rule: 2,
  },
  last_updated_at: '2026-08-31T09:00:00Z',
  capsule_char_count: 2680,
}

const event: LyricsMemoryEventSummary = {
  id: 11,
  event_type: 'creation_request',
  task_id: 43,
  source_version_id: null,
  created_by_id: 1,
  created_by_username: 'admin',
  content_preview: '创作一首围绕重逢主题的流行歌曲',
  context_preview: { title: '重逢' },
  is_useful: true,
  created_at: '2026-08-31T08:00:00Z',
}

const memory: Record<string, unknown> = {
  admin_rules: [{ id: 20, title: '副歌要求', content: '副歌首句要有记忆点' }],
  '1_true_creation_requirements': [{
    task_id: 43,
    requirement_summary: '以重逢为核心，用递进情绪完成流行歌表达',
  }],
  '2_true_modification_requirements': [],
  '3_requirement_context': [{ task_id: 43, source_kind: 'initial_creation', title: '重逢' }],
  '4_creation_distillation_expert': {
    accepted_evidence: [{
      task_id: 43,
      strategy_summary: '主歌从疏离推进到重逢，副歌集中释放情绪',
      result_summary: '已确认为情绪完整的有效版本',
      reusable_patterns: ['主歌铺陈后在副歌完成情绪跃升'],
      highlight_summary: '副歌首句具有辨识度',
    }],
  },
  '5_ranking_lyrics_patterns': { available: false, items: [] },
}

const preview: LyricsMemoryPreview = {
  capsule_char_count: 2680,
  distilled_insight_count: 6,
  pending_legacy_count: 0,
  memory,
}

const proposalMessage: LyricsMemoryChatMessage = {
  id: 51,
  role: 'assistant',
  content: '建议新增一条副歌固定规则，请确认后应用。',
  proposal: {
    reply: '建议新增一条副歌固定规则，请确认后应用。',
    operations: [{
      action: 'add_rule',
      event_id: null,
      title: '副歌要求',
      content: '副歌首句要有记忆点',
      reason: '管理员希望稳定强调副歌辨识度',
    }],
  },
  is_applied: false,
  provider: 'kimi',
  model: 'kimi-k2.5',
  created_by_id: 1,
  created_at: '2026-08-31T09:10:00Z',
  applied_at: null,
}

const snapshot: LyricsMemorySnapshotSummary = {
  id: 7,
  name: '客户确认版 1',
  source_event_count: 22,
  capsule_char_count: 2680,
  created_by_id: 1,
  created_at: '2026-08-31T09:20:00Z',
  updated_at: '2026-08-31T09:20:00Z',
}

const snapshotDetail: LyricsMemorySnapshotDetail = {
  ...snapshot,
  memory,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(lyricsMemoryApi.getLyricsMemoryOverview).mockResolvedValue(overview)
  vi.mocked(lyricsMemoryApi.listLyricsMemoryEvents).mockResolvedValue({
    items: [event],
    total: 1,
    page: 1,
    page_size: 15,
  })
  vi.mocked(lyricsMemoryApi.listLyricsMemoryChat).mockResolvedValue({
    items: [proposalMessage],
  })
  vi.mocked(lyricsMemoryApi.listLyricsMemorySnapshots).mockResolvedValue({
    items: [snapshot],
    total: 1,
    limit: 20,
  })
  vi.mocked(lyricsMemoryApi.getLyricsMemoryPreview).mockResolvedValue(preview)
  vi.mocked(lyricsMemoryApi.getLyricsMemorySnapshot).mockResolvedValue(snapshotDetail)
  vi.mocked(lyricsMemoryApi.distillNextLegacyLyricsMemory).mockResolvedValue({
    processed_count: 1,
    processed_event_ids: [19],
    pending_legacy_count: 0,
  })
  vi.mocked(lyricsMemoryApi.applyLyricsMemoryChatProposal).mockResolvedValue({
    message: { ...proposalMessage, is_applied: true, applied_at: '2026-08-31T09:30:00Z' },
    created_event_ids: [25],
    updated_event_ids: [],
  })
})

afterEach(cleanup)

describe('LyricsMemoryPage', () => {
  it('shows distilled memory by default and keeps original evidence secondary', async () => {
    const user = userEvent.setup()
    render(<App><LyricsMemoryPage /></App>)

    expect(await screen.findByRole('heading', { name: '歌词记忆' })).toBeInTheDocument()
    expect(screen.getByText('24')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '当前提炼记忆' })).toBeInTheDocument()
    expect(lyricsMemoryApi.getLyricsMemoryPreview).toHaveBeenCalledOnce()

    await user.click(screen.getByText('1. 已确认创作需求提炼'))
    expect(await screen.findByText('需求摘要')).toBeInTheDocument()
    expect(screen.getByText('以重逢为核心，用递进情绪完成流行歌表达')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /原始证据/ }))
    expect(await screen.findByText('仅追溯')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '预览注入内容' }))

    expect(await screen.findByText('实际注入内容')).toBeInTheDocument()
    expect(screen.getAllByText('管理员固定规则').length).toBeGreaterThan(0)
    expect(lyricsMemoryApi.getLyricsMemoryPreview).toHaveBeenCalledTimes(2)
  })

  it('keeps an AI memory proposal pending until the admin confirms it', async () => {
    const user = userEvent.setup()
    render(<App><LyricsMemoryPage /></App>)

    await screen.findByRole('heading', { name: '歌词记忆' })
    await user.click(screen.getByText('对话调整'))
    expect(await screen.findByText(proposalMessage.content)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '确认应用' })).toBeInTheDocument()
    expect(lyricsMemoryApi.applyLyricsMemoryChatProposal).not.toHaveBeenCalled()
  })

  it('distills legacy results one at a time only after an admin action', async () => {
    const user = userEvent.setup()
    vi.mocked(lyricsMemoryApi.getLyricsMemoryPreview)
      .mockResolvedValueOnce({ ...preview, pending_legacy_count: 1 })
      .mockResolvedValue({ ...preview, distilled_insight_count: 7 })
    render(<App><LyricsMemoryPage /></App>)

    const distillButton = await screen.findByRole('button', { name: '提炼下一条历史结果' })
    expect(lyricsMemoryApi.distillNextLegacyLyricsMemory).not.toHaveBeenCalled()

    await user.click(distillButton)

    await waitFor(() => {
      expect(lyricsMemoryApi.distillNextLegacyLyricsMemory).toHaveBeenCalledOnce()
    })
    expect((await screen.findAllByText('7')).length).toBeGreaterThan(0)
  })

  it('opens a named retained memory snapshot without expanding all cards inline', async () => {
    const user = userEvent.setup()
    render(<App><LyricsMemoryPage /></App>)

    await screen.findByRole('heading', { name: '歌词记忆' })
    await user.click(screen.getByText('保留记忆'))
    expect(await screen.findByText('已保留 1 / 20')).toBeInTheDocument()
    expect(lyricsMemoryApi.getLyricsMemorySnapshot).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /客户确认版 1/ }))

    await waitFor(() => {
      expect(lyricsMemoryApi.getLyricsMemorySnapshot).toHaveBeenCalledWith(7)
    })
    expect(await screen.findByText('有效证据')).toBeInTheDocument()
    expect(screen.getByText('22 条')).toBeInTheDocument()
  })
})
