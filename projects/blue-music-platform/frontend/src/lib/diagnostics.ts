import type { User } from '../types/api'

const DIAGNOSTIC_KEY = 'blue_music_diagnostic_events'
const MAX_EVENTS = 20

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

export function buildDiagnosticReport(user: User | null): string {
  return JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      frontend_version: '0.3.0',
      page: window.location.href,
      browser: navigator.userAgent,
      user: user
        ? { id: user.id, username: user.username, role: user.role }
        : null,
      recent_events: readEvents(),
    },
    null,
    2,
  )
}

export async function copyDiagnosticReport(user: User | null): Promise<void> {
  await navigator.clipboard.writeText(buildDiagnosticReport(user))
}
