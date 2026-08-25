import { App } from 'antd'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as analysisApi from '../api/analysis'
import * as workflowApi from '../api/workflows'
import type { AnalysisTask, WorkflowRun } from '../types/api'
import { WorkflowsPage } from './WorkflowsPage'

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

vi.mock('../api/workflows', () => ({
  createWorkflowTemplate: vi.fn(),
  deleteWorkflowRun: vi.fn(),
  deleteWorkflowRuns: vi.fn(),
  deleteWorkflowTemplate: vi.fn(),
  listWorkflowRuns: vi.fn(),
  listWorkflowTemplates: vi.fn(),
  resolveWorkflowReview: vi.fn(),
  startWorkflowRun: vi.fn(),
  updateWorkflowTemplate: vi.fn(),
}))

vi.mock('../api/analysis', () => ({ getAnalysisTask: vi.fn() }))
vi.mock('../api/lyrics', () => ({ getLyricsTask: vi.fn() }))
vi.mock('../api/music', () => ({ getMusicTask: vi.fn(), loadMusicAudio: vi.fn() }))
vi.mock('../api/rankings', () => ({
  getCollectionTask: vi.fn(),
  getRankingSnapshot: vi.fn(),
  listRankingEntries: vi.fn(),
}))
vi.mock('../api/reviewAgents', () => ({
  getReviewRun: vi.fn(),
  listReviewAgents: vi.fn().mockResolvedValue([]),
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

const configuration = {
  collection: { source_mode: 'sample' as const, chart: 'rising' as const, limit: 15, rising_rank: 1 },
  analysis: { window_days: 7 },
  lyrics: {
    direction_index: 0,
    title_hint: null,
    theme: null,
    language: '中文',
    requirements: null,
  },
  review: { agent_id: null, instruction: null },
  music: { title: null, style_prompt: null, instrumental: false, requirements: null },
  reference: { source_entry_id: null, instruction: null },
}

const run: WorkflowRun = {
  id: 51,
  template_id: null,
  template_name: '榜单分析演示',
  configuration,
  status: 'completed',
  current_step: null,
  requested_by_id: 1,
  requested_by_username: 'admin',
  error_code: null,
  error_message: null,
  error_detail: null,
  started_at: '2026-08-16T08:00:00Z',
  completed_at: '2026-08-16T08:01:00Z',
  created_at: '2026-08-16T08:00:00Z',
  steps: [{
    id: 501,
    step_type: 'analysis',
    position: 1,
    status: 'completed',
    task_id: 43,
    output_id: 20,
    result_detail: null,
    error_code: null,
    error_message: null,
    started_at: '2026-08-16T08:00:00Z',
    completed_at: '2026-08-16T08:01:00Z',
  }],
}

const analysisTask: AnalysisTask = {
  id: 43,
  status: 'completed',
  provider: 'kimi',
  model: 'kimi-k2.5',
  window_days: 7,
  window_start: '2026-08-10',
  window_end: '2026-08-16',
  selected_entry_count: 1,
  error_code: null,
  error_message: null,
  started_at: '2026-08-16T08:00:00Z',
  completed_at: '2026-08-16T08:01:00Z',
  created_at: '2026-08-16T08:00:00Z',
  api_usage: [],
  report: {
    id: 20,
    task_id: 43,
    trend_summary: '飙升榜显示都市夜行情绪正在升温。',
    trend_metrics: {},
    evidence: {},
    created_at: '2026-08-16T08:01:00Z',
    creation_directions: [{
      name: '夜行叙事',
      language: '中文',
      genre_tags: ['流行'],
      mood_tags: ['克制'],
      theme_keywords: ['城市夜晚'],
      scene_tags: ['通勤'],
      tempo: 'medium',
      vocal_gender: 'unspecified',
      vocal_style: '叙事感人声',
      instrument_tags: ['钢琴'],
      structure: ['主歌', '副歌'],
      hook_direction: '短句重复',
      negative_constraints: ['避免空泛'],
    }],
  },
}

afterEach(cleanup)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(workflowApi.listWorkflowTemplates).mockResolvedValue([])
  vi.mocked(workflowApi.listWorkflowRuns).mockResolvedValue({ items: [run], total: 1 })
  vi.mocked(analysisApi.getAnalysisTask).mockResolvedValue(analysisTask)
})

describe('WorkflowsPage output details', () => {
  it('opens a completed step output in place without leaving the workflow page', async () => {
    const user = userEvent.setup()
    render(
      <App>
        <WorkflowsPage />
      </App>,
    )

    await user.click(await screen.findByText('#51 · 榜单分析演示'))
    await user.click(await screen.findByRole('button', { name: '查看产出' }))

    await waitFor(() => {
      expect(analysisApi.getAnalysisTask).toHaveBeenCalledWith(43)
    })
    expect(await screen.findByText('飙升榜显示都市夜行情绪正在升温。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: '自动流程' })).toBeInTheDocument()
    expect(screen.getByText('自动流程 #51')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /夜行叙事/ })).toBeInTheDocument()
  })
})
