import { App } from 'antd'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as rankingApi from '../api/rankings'
import type { RankingSnapshot } from '../types/api'
import { RankingsPage } from './RankingsPage'

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

vi.mock('../api/rankings', () => ({
  deleteCollectionTask: vi.fn(),
  deleteCollectionTasks: vi.fn(),
  listCollectionTasks: vi.fn(),
  listRankingEntries: vi.fn(),
  listRankingSnapshots: vi.fn(),
  runRankingCollection: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 2,
      username: 'member',
      watermark_text: 'member',
      role: 'member',
      is_active: true,
      agent_permissions: ['analysis'],
      music_quota: { is_unlimited: false, remaining_tasks: 0, used_tasks: 0 },
    },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

const snapshots: RankingSnapshot[] = [
  {
    id: 3,
    platform: 'kugou',
    chart_code: '8888',
    chart_name: '酷狗 TOP500',
    snapshot_date: '2026-08-31',
    source_updated_date: '2026-08-31',
    item_count: 100,
    collected_at: '2026-08-31T08:30:00Z',
  },
  {
    id: 2,
    platform: 'kugou',
    chart_code: '6666',
    chart_name: '酷狗飙升榜',
    snapshot_date: '2026-08-31',
    source_updated_date: '2026-08-31',
    item_count: 20,
    collected_at: '2026-08-31T08:20:00Z',
  },
  {
    id: 1,
    platform: 'kugou',
    chart_code: '8888',
    chart_name: '酷狗 TOP500',
    snapshot_date: '2026-08-30',
    source_updated_date: '2026-08-30',
    item_count: 100,
    collected_at: '2026-08-30T08:30:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(rankingApi.listRankingSnapshots).mockResolvedValue(snapshots)
  vi.mocked(rankingApi.listRankingEntries).mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
  })
})

afterEach(cleanup)

describe('RankingsPage member view', () => {
  it('shows latest ranking results without collection controls or task history', async () => {
    render(
      <MemoryRouter>
        <App>
          <RankingsPage />
        </App>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '榜单数据' })).toBeInTheDocument()
    expect(screen.getByText('酷狗 TOP500')).toBeInTheDocument()
    expect(screen.getByText('酷狗飙升榜')).toBeInTheDocument()
    expect(screen.queryByText('2026-08-30')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '采集 TOP500' })).not.toBeInTheDocument()
    expect(screen.queryByText('运行记录')).not.toBeInTheDocument()
    expect(rankingApi.listCollectionTasks).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(rankingApi.listRankingEntries).toHaveBeenCalledWith({
        snapshotId: 3,
        page: 1,
        pageSize: 20,
        search: '',
      })
    })
  })
})
