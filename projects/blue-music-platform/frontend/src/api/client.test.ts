import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiRequest, TOKEN_KEY } from './client'

describe('apiRequest', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('keeps the backend request id on errors and records a safe diagnostic', async () => {
    localStorage.setItem(TOKEN_KEY, 'secret-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: 'DATABASE_UNAVAILABLE',
              message: '数据库暂时不可用',
              request_id: 'req-test-001',
            },
          }),
          { status: 503, headers: { 'content-type': 'application/json' } },
        ),
      ),
    )

    await expect(apiRequest('/dashboard')).rejects.toMatchObject({
      status: 503,
      code: 'DATABASE_UNAVAILABLE',
      requestId: 'req-test-001',
    })

    const diagnostics = localStorage.getItem('blue_music_diagnostic_events') ?? ''
    expect(diagnostics).toContain('req-test-001')
    expect(diagnostics).not.toContain('secret-token')
  })
})
