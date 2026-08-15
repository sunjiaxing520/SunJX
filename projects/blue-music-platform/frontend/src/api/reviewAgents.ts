import type {
  ReviewAgent,
  ReviewAgentInitializationPreview,
  ReviewChatMessage,
  ReviewLyricsOption,
  ReviewList,
  ReviewMemory,
  ReviewResult,
} from '../types/api'
import { apiRequest } from './client'

export function listReviewAgents(): Promise<ReviewAgent[]> {
  return apiRequest<ReviewAgent[]>('/review-agents')
}

export function getReviewAgent(agentId: number): Promise<ReviewAgent> {
  return apiRequest<ReviewAgent>(`/review-agents/${agentId}`)
}

export function createReviewAgent(
  name: string,
  initializationMessages: ReviewChatMessage[],
  passScore: number,
): Promise<ReviewAgent> {
  return apiRequest<ReviewAgent>('/review-agents', {
    method: 'POST',
    body: JSON.stringify({
      name,
      initialization_messages: initializationMessages,
      pass_score: passScore,
    }),
  })
}

export function previewReviewAgentInitialization(
  messages: ReviewChatMessage[],
  message: string,
): Promise<ReviewAgentInitializationPreview> {
  return apiRequest<ReviewAgentInitializationPreview>('/review-agents/initialize-preview', {
    method: 'POST',
    body: JSON.stringify({ messages, message }),
  })
}

export function updateReviewAgentMembers(agentId: number, userIds: number[]): Promise<ReviewAgent> {
  return apiRequest<ReviewAgent>(`/review-agents/${agentId}/members`, {
    method: 'PUT',
    body: JSON.stringify({ user_ids: userIds }),
  })
}

export function updateReviewAgentSettings(agentId: number, passScore: number): Promise<ReviewAgent> {
  return apiRequest<ReviewAgent>(`/review-agents/${agentId}/settings`, {
    method: 'PATCH',
    body: JSON.stringify({ pass_score: passScore }),
  })
}

export function listReviewLyricsOptions(): Promise<ReviewLyricsOption[]> {
  return apiRequest<ReviewLyricsOption[]>('/review-agents/lyrics-options')
}

export function createLyricsReview(
  agentId: number,
  lyricsVersionId: number,
  instruction?: string,
): Promise<ReviewResult> {
  return apiRequest<ReviewResult>(`/review-agents/${agentId}/reviews`, {
    method: 'POST',
    body: JSON.stringify({ lyrics_version_id: lyricsVersionId, instruction }),
  })
}

export function listReviewRuns(agentId: number): Promise<ReviewList> {
  return apiRequest<ReviewList>(`/review-agents/${agentId}/reviews?limit=20`)
}

export function saveReviewAgentMemory(agentId: number, content: string): Promise<ReviewMemory> {
  return apiRequest<ReviewMemory>(`/review-agents/${agentId}/memory`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}
