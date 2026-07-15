import type {
  CreationBrief,
  LyricsCreatePayload,
  LyricsTask,
  LyricsTaskList,
  LyricsVersion,
  TaskDeleteResult,
} from '../types/api'
import { apiRequest } from './client'

export function generateLyrics(payload: LyricsCreatePayload): Promise<LyricsTask> {
  return apiRequest<LyricsTask>('/lyrics/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listLyricsTasks(): Promise<LyricsTaskList> {
  return apiRequest<LyricsTaskList>('/lyrics/tasks?limit=15')
}

export function getLyricsTask(taskId: number): Promise<LyricsTask> {
  return apiRequest<LyricsTask>(`/lyrics/tasks/${taskId}`)
}

export function deleteLyricsTask(taskId: number): Promise<void> {
  return apiRequest<void>(`/lyrics/tasks/${taskId}`, { method: 'DELETE' })
}

export function deleteLyricsTasks(taskIds: number[]): Promise<TaskDeleteResult> {
  return apiRequest<TaskDeleteResult>('/lyrics/tasks', {
    method: 'DELETE',
    body: JSON.stringify({ task_ids: taskIds }),
  })
}

export function regenerateLyrics(taskId: number): Promise<LyricsTask> {
  return apiRequest<LyricsTask>(`/lyrics/tasks/${taskId}/regenerate`, {
    method: 'POST',
  })
}

export function saveLyricsVersion(versionId: number): Promise<LyricsVersion> {
  return apiRequest<LyricsVersion>(`/lyrics/versions/${versionId}/save`, {
    method: 'PUT',
  })
}

export function getCreationBrief(versionId: number): Promise<CreationBrief> {
  return apiRequest<CreationBrief>(`/lyrics/versions/${versionId}/creation-brief`)
}
