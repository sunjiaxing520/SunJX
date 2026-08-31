import type { AgentType, User } from '../types/api'
import { apiRequest } from './client'

export function listUsers(): Promise<User[]> {
  return apiRequest<User[]>('/users')
}

export function createUser(
  username: string,
  password: string,
  musicQuotaRemaining = 0,
): Promise<User> {
  return apiRequest<User>('/users', {
    method: 'POST',
    body: JSON.stringify({
      username,
      password,
      music_quota_remaining: musicQuotaRemaining,
    }),
  })
}

export function setUserStatus(userId: number, isActive: boolean): Promise<User> {
  return apiRequest<User>(`/users/${userId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active: isActive }),
  })
}

export function resetUserPassword(userId: number, password: string): Promise<void> {
  return apiRequest<void>(`/users/${userId}/password`, {
    method: 'PUT',
    body: JSON.stringify({ password }),
  })
}

export function updateAgentPermissions(
  userId: number,
  agents: AgentType[],
): Promise<User> {
  return apiRequest<User>(`/users/${userId}/agent-permissions`, {
    method: 'PUT',
    body: JSON.stringify({ agents }),
  })
}

export function updateUserMusicQuota(
  userId: number,
  remainingTasks: number,
): Promise<User> {
  return apiRequest<User>(`/users/${userId}/music-quota`, {
    method: 'PUT',
    body: JSON.stringify({ remaining_tasks: remainingTasks }),
  })
}

export function updateUserWatermark(
  userId: number,
  watermarkText: string | null,
): Promise<User> {
  return apiRequest<User>(`/users/${userId}/watermark`, {
    method: 'PUT',
    body: JSON.stringify({ watermark_text: watermarkText }),
  })
}
