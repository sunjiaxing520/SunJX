import type { User } from '../types/api'

const DIAGNOSTIC_KEY = 'blue_music_diagnostic_events'
const MAX_EVENTS = 20
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '')

export interface DiagnosticEvent {
  occurred_at: string
  source: 'api' | 'render'
  message: string
  method?: string
  path?: string
  status?: number
  code?: string
  request_id?: string
}

interface BackendHealthPayload {
  status?: unknown
  version?: unknown
  service?: unknown
  environment?: unknown
}

export interface BackendDiagnostic {
  checked_at: string
  url: string
  reachable: boolean
  http_status?: number
  health_status?: string
  version?: string
  service?: string
  environment?: string
  error?: string
}

function readEvents(): DiagnosticEvent[] {
  try {
    const raw = localStorage.getItem(DIAGNOSTIC_KEY)
    return raw ? (JSON.parse(raw) as DiagnosticEvent[]) : []
  } catch {
    return []
  }
}

export function recordDiagnostic(
  event: Omit<DiagnosticEvent, 'occurred_at'>,
): void {
  const events = [
    { ...event, occurred_at: new Date().toISOString() },
    ...readEvents(),
  ].slice(0, MAX_EVENTS)

  try {
    localStorage.setItem(DIAGNOSTIC_KEY, JSON.stringify(events))
  } catch {
    // Diagnostics must never interrupt the user's primary workflow.
  }
}

export async function checkBackendHealth(): Promise<BackendDiagnostic> {
  const checkedAt = new Date().toISOString()
  const url = `${API_BASE_URL}/health`

  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
    const contentType = response.headers.get('content-type') ?? ''
    const body = contentType.includes('application/json')
      ? ((await response.json()) as BackendHealthPayload)
      : null

    return {
      checked_at: checkedAt,
      url,
      reachable: true,
      http_status: response.status,
      health_status:
        typeof body?.status === 'string' ? body.status : undefined,
      version: typeof body?.version === 'string' ? body.version : undefined,
      service: typeof body?.service === 'string' ? body.service : undefined,
      environment:
        typeof body?.environment === 'string' ? body.environment : undefined,
    }
  } catch (error) {
    return {
      checked_at: checkedAt,
      url,
      reachable: false,
      error: error instanceof Error ? error.message : 'Unknown network error',
    }
  }
}

export function buildDiagnosticReport(
  user: User | null,
  backend?: BackendDiagnostic,
): string {
  const events = readEvents()

  return JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      frontend_version: '0.3.0',
      page: window.location.href,
      browser: navigator.userAgent,
      current_backend: backend ?? null,
      user: user
        ? { id: user.id, username: user.username, role: user.role }
        : null,
      event_window: {
        count: events.length,
        newest_at: events[0]?.occurred_at ?? null,
        oldest_at: events.at(-1)?.occurred_at ?? null,
      },
      recent_events: events,
    },
    null,
    2,
  )
}

export async function copyDiagnosticReport(user: User | null): Promise<void> {
  const backend = await checkBackendHealth()
  await navigator.clipboard.writeText(buildDiagnosticReport(user, backend))
}
