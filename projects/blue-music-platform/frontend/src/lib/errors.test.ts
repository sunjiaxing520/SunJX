import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { errorMessage } from './errors'

describe('errorMessage', () => {
  it('includes the provider failure reason and request id', () => {
    const error = new ApiError({
      message: '歌词生成失败，请检查 AI 供应商配置后重试',
      status: 502,
      code: 'LYRICS_PROVIDER_FAILED',
      requestId: 'request-123',
      detail: {
        task_id: 5,
        reason: 'AI 接口请求超时（单次等待上限 60 秒）；已尝试 2 次',
      },
    })

    expect(errorMessage(error)).toBe(
      '歌词生成失败，请检查 AI 供应商配置后重试：' +
        'AI 接口请求超时（单次等待上限 60 秒）；已尝试 2 次' +
        '（请求编号：request-123）',
    )
  })

  it('keeps the normal API message when no reason is present', () => {
    const error = new ApiError({
      message: '请求失败',
      status: 400,
      code: 'BAD_REQUEST',
    })

    expect(errorMessage(error)).toBe('请求失败')
  })
})
