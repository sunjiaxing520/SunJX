import type { AgentType, User } from '../types/api'
import { apiRequest } from './client'

export function listUsers(): Promise<User[]> {
  return apiRequest<User[]>('/users')
}

export function createUser(username: string, password: string): Promise<User> {
  return apiRequest<User>('/users', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
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
