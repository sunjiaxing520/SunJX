import { beforeEach, describe, expect, it, vi } from 'vitest'

import { copyDiagnosticReport, recordDiagnostic } from './diagnostics'

describe('diagnostic report', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('includes the current backend health beside historical errors', async () => {
    recordDiagnostic({
      source: 'api',
      message: '无法连接后端服务',
      method: 'GET',
      path: '/analysis/tasks?limit=15',
      status: 0,
      code: 'NETWORK_ERROR',
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'healthy',
            version: '0.3.0',
            service: 'blue-music-platform',
            environment: 'development',
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      ),
    )
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    await copyDiagnosticReport(null)

    const report = JSON.parse(writeText.mock.calls[0][0])
    expect(report.current_backend).toMatchObject({
      reachable: true,
      http_status: 200,
      health_status: 'healthy',
    })
    expect(report.event_window.count).toBe(1)
    expect(report.recent_events[0].code).toBe('NETWORK_ERROR')
  })

  it('still produces a report when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    await copyDiagnosticReport(null)

    const report = JSON.parse(writeText.mock.calls[0][0])
    expect(report.current_backend).toMatchObject({
      reachable: false,
      error: 'Failed to fetch',
    })
  })
})
