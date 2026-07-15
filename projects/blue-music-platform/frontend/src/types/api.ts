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

export type ApiUsageStatus = 'completed' | 'failed'
export type BalanceStatus =
  | 'available'
  | 'manual'
  | 'not_applicable'
  | 'hidden'
  | 'error'

export interface ApiUsageRecord {
  id: number
  task_type: string
  task_id: number
  operation: string
  provider: string
  model: string | null
  method: string
  endpoint: string
  is_external: boolean
  status: ApiUsageStatus
  external_request_id: string | null
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_tokens: number
  usage_unit: string
  usage_quantity: number
  estimated_cost: number | null
  currency: string | null
  attempt_count: number
  duration_ms: number | null
  error_code: string | null
  error_message: string | null
  started_at: string
  completed_at: string
  created_at: string
}

export interface ApiUsageMetrics {
  executions_today: number
  external_calls_today: number
  tokens_today: number
  tokens_7d: number
}

export interface DailyApiUsage {
  day: string
  executions: number
  external_calls: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

export interface ProviderAccountUsage {
  provider: string
  display_name: string
  models: string[]
  executions_today: number
  tokens_today: number
  tokens_7d: number
  usage_by_unit_7d: Record<string, number>
  balance_status: BalanceStatus
  balance_amount: number | null
  balance_unit: string | null
  balance_message: string
  console_url: string | null
  checked_at: string | null
}

export interface ApiUsageDashboard {
  metrics: ApiUsageMetrics
  daily: DailyApiUsage[]
  providers: ProviderAccountUsage[]
  recent_calls: ApiUsageRecord[]
}

export type MaxTokensParameter = 'max_tokens' | 'max_completion_tokens'
export type ProviderTestStatus = 'untested' | 'success' | 'failed'

export interface AiProviderTemplate {
  key: string
  display_name: string
  protocol: string
  description: string
  default_base_url: string
  default_model: string
  requires_api_key: boolean
  supports_json_mode: boolean
  max_tokens_parameter: MaxTokensParameter
  console_url: string | null
  docs_url: string | null
}

export interface AiProviderConfig {
  id: number
  name: string
  template_key: string
  template_name: string
  protocol: string
  base_url: string
  endpoint: string
  model: string
  has_api_key: boolean
  api_key_hint: string | null
  supports_json_mode: boolean
  max_tokens_parameter: MaxTokensParameter
  request_timeout_seconds: number
  max_retries: number
  analysis_max_output_tokens: number
  lyrics_max_output_tokens: number
  is_active: boolean
  source: string
  last_test_status: ProviderTestStatus
  last_test_message: string | null
  last_tested_at: string | null
  created_at: string
  updated_at: string
}

export interface EnvironmentAiProvider {
  configured: boolean
  template_key: string
  template_name: string
  base_url: string
  endpoint: string
  model: string
  has_api_key: boolean
  api_key_hint: string | null
}

export interface AiProviderListResponse {
  items: AiProviderConfig[]
  runtime_source: 'database' | 'environment'
  environment_fallback: EnvironmentAiProvider
}

export interface AiProviderWritePayload {
  name: string
  template_key: string
  base_url?: string
  model?: string
  api_key?: string
  supports_json_mode?: boolean
  max_tokens_parameter?: MaxTokensParameter
  request_timeout_seconds: number
  max_retries: number
  analysis_max_output_tokens: number
  lyrics_max_output_tokens: number
}

export interface AiProviderTestResult {
  status: 'success' | 'failed'
  message: string
  provider: AiProviderConfig
  api_usage: ApiUsageRecord
}

export interface DashboardResponse {
  metrics: DashboardMetrics
  agents: DashboardAgentStatus[]
  api_usage: ApiUsageDashboard
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
export type WorkflowStepType = 'collection' | 'analysis' | 'lyrics'

export interface WorkflowConfiguration {
  collection: {
    source_mode: 'live' | 'sample'
    limit: number
  }
  analysis: {
    window_days: number
  }
  lyrics: {
    direction_index: number
    title_hint: string | null
    theme: string | null
    language: string
    requirements: string | null
  }
}

export interface WorkflowTemplatePayload {
  name: string
  steps: WorkflowStepType[]
  configuration: WorkflowConfiguration
}

export interface WorkflowTemplate extends WorkflowTemplatePayload {
  id: number
  created_by_id: number | null
  created_by_username: string | null
  created_at: string
  updated_at: string
}

export interface WorkflowRunStep {
  id: number
  step_type: WorkflowStepType
  position: number
  status: WorkflowTaskStatus
  task_id: number | null
  output_id: number | null
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export interface WorkflowRun {
  id: number
  template_id: number | null
  template_name: string
  configuration: WorkflowConfiguration
  status: WorkflowTaskStatus
  current_step: WorkflowStepType | null
  requested_by_id: number | null
  requested_by_username: string | null
  error_code: string | null
  error_message: string | null
  error_detail: Record<string, unknown> | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  steps: WorkflowRunStep[]
}

export interface WorkflowRunList {
  items: WorkflowRun[]
  total: number
}

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
  api_usage: ApiUsageRecord[]
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
  api_usage: ApiUsageRecord[]
  versions: LyricsVersion[]
}

export interface LyricsTaskList {
  items: LyricsTask[]
  total: number
}

export interface TaskDeleteResult {
  deleted_count: number
  deleted_task_ids: number[]
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

export type FavoriteItemType = 'analysis' | 'lyrics'

export interface FavoriteItem {
  id: number
  item_type: FavoriteItemType
  target_id: number
  source_task_id: number
  title: string
  summary: string
  status: WorkflowTaskStatus
  provider: string
  model: string | null
  total_tokens: number
  source_created_at: string
  metadata: Record<string, unknown>
  note: string | null
  created_by_id: number | null
  created_by_username: string | null
  favorited_at: string
  updated_at: string
}

export interface FavoriteList {
  items: FavoriteItem[]
  total: number
}
