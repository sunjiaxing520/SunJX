import { describe, expect, it } from 'vitest'

import type {
  AnalysisTask,
  CreationDirection,
  FavoriteItem,
} from '../types/api'
import {
  analysisDirectionLabel,
  buildLyricsAnalysisDirections,
} from './lyricsAnalysis'

const direction: CreationDirection = {
  name: '雨夜归途',
  language: '中文',
  genre_tags: ['流行', 'R&B'],
  mood_tags: ['克制', '温暖'],
  theme_keywords: ['告别', '成长'],
  scene_tags: ['深夜', '通勤'],
  tempo: 'medium',
  vocal_gender: 'male',
  vocal_style: '自然叙事，副歌抬升',
  instrument_tags: ['钢琴'],
  structure: ['主歌 A', '副歌', '主歌 B'],
  hook_direction: '短句重复主题词',
  negative_constraints: ['避免照搬已有歌词'],
}

function task(taskId: number, reportId: number): AnalysisTask {
  return {
    id: taskId,
    status: 'completed',
    provider: 'local',
    model: null,
    window_days: 7,
    window_start: '2026-08-08',
    window_end: '2026-08-15',
    selected_entry_count: 1,
    error_code: null,
    error_message: null,
    started_at: '2026-08-15T08:00:00Z',
    completed_at: '2026-08-15T08:00:01Z',
    created_at: '2026-08-15T08:00:00Z',
    api_usage: [],
    report: {
      id: reportId,
      task_id: taskId,
      trend_summary: '当前歌曲叙事清晰，副歌有提升空间。',
      trend_metrics: {},
      creation_directions: [direction],
      evidence: {},
      created_at: '2026-08-15T08:00:01Z',
    },
  }
}

function favorite(reportId: number, sourceTaskId: number): FavoriteItem {
  return {
    id: 1,
    item_type: 'analysis',
    target_id: reportId,
    source_task_id: sourceTaskId,
    title: '分析收藏',
    summary: '收藏摘要',
    status: 'completed',
    provider: 'local',
    model: null,
    total_tokens: 0,
    source_created_at: '2026-08-15T08:00:01Z',
    metadata: { creation_directions: [direction] },
    category: 'S',
    note: null,
    created_by_id: 1,
    created_by_username: 'admin',
    favorited_at: '2026-08-15T08:10:00Z',
    updated_at: '2026-08-15T08:10:00Z',
  }
}

describe('lyrics analysis directions', () => {
  it('uses the analysis task number and favorite category without losing report id', () => {
    const choices = buildLyricsAnalysisDirections(
      [task(43, 20), task(44, 21)],
      [favorite(20, 43)],
    )

    const classified = choices.find((item) => item.reportId === 20)
    const unclassified = choices.find((item) => item.reportId === 21)
    expect(classified?.category).toBe('S')
    expect(classified?.analysisTaskId).toBe(43)
    expect(classified?.value).toBe('20:0')
    expect(analysisDirectionLabel(classified!)).toContain('榜单分析 #43')
    expect(analysisDirectionLabel(classified!)).not.toContain('#20')
    expect(unclassified?.category).toBe('unclassified')
  })

  it('keeps older favorited reports available', () => {
    const choices = buildLyricsAnalysisDirections([], [favorite(99, 42)])
    expect(choices).toHaveLength(1)
    expect(choices[0]).toMatchObject({ reportId: 99, analysisTaskId: 42, category: 'S' })
  })

  it('keeps complete direction details for preview without inventing user input', () => {
    const [choice] = buildLyricsAnalysisDirections([task(43, 20)], [])
    expect(choice.direction).toEqual(direction)
    expect(choice.reportId).toBe(20)
    expect(choice.directionIndex).toBe(0)
    expect(choice).not.toHaveProperty('requirements')
    expect(choice).not.toHaveProperty('title_hint')
  })
})
