import type {
  LyricsMemoryApplyResult,
  LyricsMemoryChatList,
  LyricsMemoryChatMessage,
  LyricsMemoryDeleteResult,
  LyricsMemoryEventDetail,
  LyricsMemoryEventList,
  LyricsMemoryEventType,
  LyricsMemoryOverview,
  LyricsMemoryPreview,
  LyricsMemorySnapshotDetail,
  LyricsMemorySnapshotList,
  LyricsMemorySnapshotSummary,
} from '../types/api'
import { apiRequest } from './client'


export interface LyricsMemoryEventQuery {
  eventType?: LyricsMemoryEventType
  isUseful?: boolean
  search?: string
  page?: number
  pageSize?: number
}

export function getLyricsMemoryOverview(): Promise<LyricsMemoryOverview> {
  return apiRequest<LyricsMemoryOverview>('/lyrics-memory/overview')
}

export function getLyricsMemoryPreview(): Promise<LyricsMemoryPreview> {
  return apiRequest<LyricsMemoryPreview>('/lyrics-memory/preview')
}

export function listLyricsMemoryEvents(
  query: LyricsMemoryEventQuery = {},
): Promise<LyricsMemoryEventList> {
  const params = new URLSearchParams()
  if (query.eventType) params.set('event_type', query.eventType)
  if (query.isUseful !== undefined) params.set('is_useful', String(query.isUseful))
  if (query.search) params.set('search', query.search)
  params.set('page', String(query.page ?? 1))
  params.set('page_size', String(query.pageSize ?? 15))
  return apiRequest<LyricsMemoryEventList>(`/lyrics-memory/events?${params.toString()}`)
}

export function getLyricsMemoryEvent(eventId: number): Promise<LyricsMemoryEventDetail> {
  return apiRequest<LyricsMemoryEventDetail>(`/lyrics-memory/events/${eventId}`)
}

export function createLyricsMemoryRule(
  title: string,
  content: string,
): Promise<LyricsMemoryEventDetail> {
  return apiRequest<LyricsMemoryEventDetail>('/lyrics-memory/rules', {
    method: 'POST',
    body: JSON.stringify({ title, content }),
  })
}

export function setLyricsMemoryUsefulness(
  eventId: number,
  isUseful: boolean,
): Promise<LyricsMemoryEventDetail> {
  return apiRequest<LyricsMemoryEventDetail>(
    `/lyrics-memory/events/${eventId}/usefulness`,
    {
      method: 'PATCH',
      body: JSON.stringify({ is_useful: isUseful }),
    },
  )
}

export function deleteLyricsMemoryEvent(eventId: number): Promise<void> {
  return apiRequest<void>(`/lyrics-memory/events/${eventId}`, { method: 'DELETE' })
}

export function deleteLyricsMemoryEvents(
  eventIds: number[],
): Promise<LyricsMemoryDeleteResult> {
  return apiRequest<LyricsMemoryDeleteResult>('/lyrics-memory/events', {
    method: 'DELETE',
    body: JSON.stringify({ event_ids: eventIds }),
  })
}

export function listLyricsMemoryChat(): Promise<LyricsMemoryChatList> {
  return apiRequest<LyricsMemoryChatList>('/lyrics-memory/chat')
}

export function requestLyricsMemoryChatPreview(
  instruction: string,
): Promise<LyricsMemoryChatMessage> {
  return apiRequest<LyricsMemoryChatMessage>('/lyrics-memory/chat', {
    method: 'POST',
    body: JSON.stringify({ instruction }),
  })
}

export function applyLyricsMemoryChatProposal(
  messageId: number,
): Promise<LyricsMemoryApplyResult> {
  return apiRequest<LyricsMemoryApplyResult>(`/lyrics-memory/chat/${messageId}/apply`, {
    method: 'POST',
  })
}

export function listLyricsMemorySnapshots(): Promise<LyricsMemorySnapshotList> {
  return apiRequest<LyricsMemorySnapshotList>('/lyrics-memory/snapshots')
}

export function getLyricsMemorySnapshot(
  snapshotId: number,
): Promise<LyricsMemorySnapshotDetail> {
  return apiRequest<LyricsMemorySnapshotDetail>(`/lyrics-memory/snapshots/${snapshotId}`)
}

export function createLyricsMemorySnapshot(
  name: string,
): Promise<LyricsMemorySnapshotDetail> {
  return apiRequest<LyricsMemorySnapshotDetail>('/lyrics-memory/snapshots', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function renameLyricsMemorySnapshot(
  snapshotId: number,
  name: string,
): Promise<LyricsMemorySnapshotSummary> {
  return apiRequest<LyricsMemorySnapshotSummary>(
    `/lyrics-memory/snapshots/${snapshotId}`,
    {
      method: 'PUT',
      body: JSON.stringify({ name }),
    },
  )
}

export function deleteLyricsMemorySnapshot(snapshotId: number): Promise<void> {
  return apiRequest<void>(`/lyrics-memory/snapshots/${snapshotId}`, {
    method: 'DELETE',
  })
}
