import type {
  CollectionTask,
  RankingEntryPage,
  RankingSnapshot,
} from '../types/api'
import { apiRequest } from './client'

export function runRankingCollection(
  sourceMode: 'live' | 'sample' = 'live',
  limit = 100,
): Promise<CollectionTask> {
  return apiRequest<CollectionTask>('/rankings/collections', {
    method: 'POST',
    body: JSON.stringify({ source_mode: sourceMode, limit }),
  })
}

export function listCollectionTasks(): Promise<CollectionTask[]> {
  return apiRequest<CollectionTask[]>('/rankings/collections?limit=15')
}

export function listRankingSnapshots(): Promise<RankingSnapshot[]> {
  return apiRequest<RankingSnapshot[]>('/rankings/snapshots?limit=15')
}

export function listRankingEntries(options: {
  snapshotId?: number
  page?: number
  pageSize?: number
  search?: string
} = {}): Promise<RankingEntryPage> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 50),
  })
  if (options.snapshotId) params.set('snapshot_id', String(options.snapshotId))
  if (options.search) params.set('search', options.search)
  return apiRequest<RankingEntryPage>(`/rankings/entries?${params}`)
}
