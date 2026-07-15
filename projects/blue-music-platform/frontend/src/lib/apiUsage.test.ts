import { describe, expect, it } from 'vitest'

import type { DailyApiUsage } from '../types/api'
import { sortDailyUsageNewestFirst } from './apiUsage'

function usage(day: string): DailyApiUsage {
  return {
    day,
    executions: 0,
    external_calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  }
}

describe('sortDailyUsageNewestFirst', () => {
  it('puts the latest day first without mutating the API response', () => {
    const records = [usage('2026-07-13'), usage('2026-07-15'), usage('2026-07-14')]

    expect(sortDailyUsageNewestFirst(records).map((record) => record.day)).toEqual([
      '2026-07-15',
      '2026-07-14',
      '2026-07-13',
    ])
    expect(records.map((record) => record.day)).toEqual([
      '2026-07-13',
      '2026-07-15',
      '2026-07-14',
    ])
  })
})
