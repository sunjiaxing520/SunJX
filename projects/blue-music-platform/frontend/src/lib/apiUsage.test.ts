import { describe, expect, it } from 'vitest'

import type { ApiUsageRecord, DailyApiUsage } from '../types/api'
import { groupApiUsageByTaskType, sortDailyUsageNewestFirst } from './apiUsage'

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

describe('groupApiUsageByTaskType', () => {
  it('keeps each task type separate and preserves record order inside a group', () => {
    const records = [
      { id: 3, task_type: 'provider_test' },
      { id: 2, task_type: 'analysis' },
      { id: 1, task_type: 'provider_test' },
    ] as ApiUsageRecord[]

    const groups = groupApiUsageByTaskType(records)

    expect(groups.map((group) => group.taskType)).toEqual(['analysis', 'provider_test'])
    expect(groups[0].records.map((record) => record.id)).toEqual([2])
    expect(groups[1].records.map((record) => record.id)).toEqual([3, 1])
  })
})
