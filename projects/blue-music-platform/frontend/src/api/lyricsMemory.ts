import type {
  LyricsMemoryChatList,
  LyricsMemoryChatResult,
  LyricsTeamMemory,
  LyricsMemoryCompression,
} from '../types/api'
import { apiRequest } from './client'


export function getLyricsTeamMemory(): Promise<LyricsTeamMemory> {
  return apiRequest<LyricsTeamMemory>('/lyrics-memory')
}

export function previewLyricsMemoryCompression(maxItems = 40) {
  return apiRequest<LyricsMemoryCompression>('/lyrics-memory/compress', {
    method: 'POST', body: JSON.stringify({ max_items: maxItems }),
  })
}

export function confirmLyricsMemoryCompression(previewId: number) {
  return apiRequest<LyricsTeamMemory>(`/lyrics-memory/compress/${previewId}/confirm`, { method: 'POST' })
}

export function updateLyricsMemoryInjectionLimit(
  injectionLimit: number,
): Promise<LyricsTeamMemory> {
  return apiRequest<LyricsTeamMemory>('/lyrics-memory/settings', {
    method: 'PATCH',
    body: JSON.stringify({ injection_limit: injectionLimit }),
  })
}

export function listLyricsMemoryChat(): Promise<LyricsMemoryChatList> {
  return apiRequest<LyricsMemoryChatList>('/lyrics-memory/chat')
}

export function updateLyricsMemoryByChat(
  instruction: string,
): Promise<LyricsMemoryChatResult> {
  return apiRequest<LyricsMemoryChatResult>('/lyrics-memory/chat', {
    method: 'POST',
    body: JSON.stringify({ instruction }),
  })
}
