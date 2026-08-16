import type {
  CollectionTask,
  RankingEntryPage,
  RankingSnapshot,
  TaskDeleteResult,
} from '../types/api'
import { apiRequest } from './client'

export function runRankingCollection(
  sourceMode: 'live' | 'sample' = 'live',
  limit = 100,
  chart: 'top500' | 'rising' = 'top500',
): Promise<CollectionTask> {
  return apiRequest<CollectionTask>('/rankings/collections', {
    method: 'POST',
    body: JSON.stringify({ source_mode: sourceMode, limit, chart }),
  })
}

export function listCollectionTasks(): Promise<CollectionTask[]> {
  return apiRequest<CollectionTask[]>('/rankings/collections?limit=15')
}

export function getCollectionTask(taskId: number): Promise<CollectionTask> {
  return apiRequest<CollectionTask>(`/rankings/collections/${taskId}`)
}

export function deleteCollectionTask(taskId: number): Promise<void> {
  return apiRequest<void>(`/rankings/collections/${taskId}`, { method: 'DELETE' })
}

export function deleteCollectionTasks(taskIds: number[]): Promise<TaskDeleteResult> {
  return apiRequest<TaskDeleteResult>('/rankings/collections', {
    method: 'DELETE',
    body: JSON.stringify({ task_ids: taskIds }),
  })
}

export function listRankingSnapshots(limit = 15): Promise<RankingSnapshot[]> {
  return apiRequest<RankingSnapshot[]>(`/rankings/snapshots?limit=${limit}`)
}

export function getRankingSnapshot(snapshotId: number): Promise<RankingSnapshot> {
  return apiRequest<RankingSnapshot>(`/rankings/snapshots/${snapshotId}`)
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
