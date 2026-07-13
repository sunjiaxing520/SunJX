import type { DashboardResponse } from '../types/api'
import { apiRequest } from './client'

export function getDashboard(): Promise<DashboardResponse> {
  return apiRequest<DashboardResponse>('/dashboard')
}
