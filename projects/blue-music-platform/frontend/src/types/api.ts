export type UserRole = 'super_admin' | 'member'
export type AgentType = 'crawler' | 'analysis' | 'lyrics' | 'music'
export type AgentRuntimeStatus =
  | 'not_configured'
  | 'idle'
  | 'running'
  | 'failed'

export interface User {
  id: number
  username: string
  role: UserRole
  is_active: boolean
  agent_permissions: AgentType[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface DashboardMetrics {
  crawled_today: number
  analyzed_today: number
  lyrics_tasks_today: number
  music_tasks_today: number
}

export interface DashboardAgentStatus {
  agent: AgentType
  name: string
  status: AgentRuntimeStatus
  message: string
}

export interface DashboardResponse {
  metrics: DashboardMetrics
  agents: DashboardAgentStatus[]
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    request_id?: string
    detail?: unknown
  }
}
