import type {
  LyricsMemoryChatList,
  LyricsMemoryChatResult,
  LyricsTeamMemory,
} from '../types/api'
import { apiRequest } from './client'


export function getLyricsTeamMemory(): Promise<LyricsTeamMemory> {
  return apiRequest<LyricsTeamMemory>('/lyrics-memory')
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
