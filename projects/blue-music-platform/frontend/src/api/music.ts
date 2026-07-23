import type {
  MusicCreatePayload,
  MusicExtendPayload,
  MusicResultList,
  MusicTask,
  MusicTaskList,
  SunoProviderStatus,
  TaskDeleteResult,
} from '../types/api'
import { apiBlobRequest, apiRequest } from './client'


export function getSunoProviderStatus() {
  return apiRequest<SunoProviderStatus>('/music/provider-status')
}

export function createMusicTask(payload: MusicCreatePayload) {
  return apiRequest<MusicTask>('/music/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listMusicTasks(limit = 15) {
  return apiRequest<MusicTaskList>(`/music/tasks?limit=${limit}`)
}

export function getMusicTask(taskId: number) {
  return apiRequest<MusicTask>(`/music/tasks/${taskId}`)
}

export function deleteMusicTask(taskId: number) {
  return apiRequest<void>(`/music/tasks/${taskId}`, { method: 'DELETE' })
}

export function deleteMusicTasks(taskIds: number[]) {
  return apiRequest<TaskDeleteResult>('/music/tasks', {
    method: 'DELETE',
    body: JSON.stringify({ task_ids: taskIds }),
  })
}

export function listMusicResults(limit = 30) {
  return apiRequest<MusicResultList>(`/music/results?limit=${limit}`)
}

export function extendMusicResult(resultId: number, payload: MusicExtendPayload) {
  return apiRequest<MusicTask>(`/music/results/${resultId}/extend`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteMusicResult(resultId: number) {
  return apiRequest<void>(`/music/results/${resultId}`, { method: 'DELETE' })
}

export function loadMusicAudio(path: string) {
  return apiBlobRequest(path)
}

export async function downloadMusicResult(path: string, title: string) {
  const blob = await apiBlobRequest(path)
  const extension = blob.type.includes('wav') ? 'wav' : blob.type.includes('mp4') ? 'm4a' : 'mp3'
  const unsafeCharacters = new Set('<>:"/\\|?*')
  const safeTitle = [...title]
    .map((character) => character.charCodeAt(0) < 32 || unsafeCharacters.has(character) ? '_' : character)
    .join('')
    .trim() || 'suno-track'
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = `${safeTitle}.${extension}`
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}
