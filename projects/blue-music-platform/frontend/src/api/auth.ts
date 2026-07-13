import type { TokenResponse, User } from '../types/api'
import { apiRequest } from './client'

export function login(username: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getCurrentUser(): Promise<User> {
  return apiRequest<User>('/auth/me')
}
