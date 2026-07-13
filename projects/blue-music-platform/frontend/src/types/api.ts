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

export type WorkflowTaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface CollectionTask {
  id: number
  platform: string
  chart_code: string
  chart_name: string
  source_mode: 'live' | 'sample'
  snapshot_date: string
  status: WorkflowTaskStatus
  snapshot_id: number | null
  item_count: number
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface RankingSnapshot {
  id: number
  platform: string
  chart_code: string
  chart_name: string
  snapshot_date: string
  source_updated_date: string | null
  item_count: number
  collected_at: string
}

export interface RankingEntry {
  id: number
  snapshot_id: number
  source_song_id: string
  title: string
  artist: string
  rank: number
  popularity: number | null
  cover_url: string | null
  source_url: string | null
  duration_seconds: number | null
}

export interface RankingEntryPage {
  items: RankingEntry[]
  total: number
  page: number
  page_size: number
}

export interface CreationDirection {
  name: string
  language: string
  genre_tags: string[]
  mood_tags: string[]
  theme_keywords: string[]
  scene_tags: string[]
  tempo: 'slow' | 'medium' | 'fast'
  vocal_gender: 'male' | 'female' | 'unspecified'
  vocal_style: string
  instrument_tags: string[]
  structure: string[]
  hook_direction: string
  negative_constraints: string[]
}

export interface AnalysisReport {
  id: number
  task_id: number
  trend_summary: string
  trend_metrics: Record<string, unknown>
  creation_directions: CreationDirection[]
  evidence: Record<string, unknown>
  created_at: string
}

export interface AnalysisTask {
  id: number
  status: WorkflowTaskStatus
  provider: string
  model: string | null
  window_days: number
  window_start: string
  window_end: string
  selected_entry_count: number
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  report: AnalysisReport | null
}

export interface AnalysisTaskList {
  items: AnalysisTask[]
  total: number
}

export interface LyricsVersion {
  id: number
  task_id: number
  version_number: number
  title: string
  content: string
  style_prompt: string
  sections: { name: string; content: string }[]
  is_saved: boolean
  created_at: string
}

export interface LyricsTask {
  id: number
  status: WorkflowTaskStatus
  provider: string
  model: string | null
  analysis_report_id: number | null
  direction_index: number | null
  title_hint: string | null
  theme: string
  language: string
  genre_tags: string[]
  mood_tags: string[]
  scene_tags: string[]
  keywords: string[]
  tempo: string | null
  vocal_gender: string | null
  vocal_style: string | null
  requirements: string | null
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  versions: LyricsVersion[]
}

export interface LyricsTaskList {
  items: LyricsTask[]
  total: number
}

export interface LyricsCreatePayload {
  analysis_report_id?: number
  direction_index?: number
  title_hint?: string
  theme: string
  language?: string
  genre_tags?: string[]
  mood_tags?: string[]
  scene_tags?: string[]
  keywords?: string[]
  tempo?: 'slow' | 'medium' | 'fast'
  vocal_gender?: 'male' | 'female' | 'unspecified'
  vocal_style?: string
  requirements?: string
  reference_text?: string
}

export interface CreationBrief {
  title: string
  creation_type: 'vocal'
  language: string
  genre_tags: string[]
  mood_tags: string[]
  theme_keywords: string[]
  scene_tags: string[]
  tempo: string
  vocal_gender: string
  vocal_style: string
  instrument_tags: string[]
  structure: string[]
  hook_direction: string
  lyrics: string
  negative_constraints: string[]
  source_analysis_report_id: number | null
  source_lyrics_version_id: number
}
