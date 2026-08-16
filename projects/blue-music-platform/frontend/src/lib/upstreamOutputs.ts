import type { UpstreamOutputGroup, UpstreamOutputItem } from '../components/UpstreamOutputPicker'
import type { FavoriteCategory, FavoriteItem } from '../types/api'

export const FAVORITE_OUTPUT_LABELS: Record<FavoriteCategory, string> = {
  unclassified: '待分类',
  S: 'S 级',
  A: 'A 级',
  B: 'B 级',
  C: 'C 级',
  D: 'D 级',
}

export const FAVORITE_OUTPUT_GROUPS: UpstreamOutputGroup[] = (
  ['unclassified', 'S', 'A', 'B', 'C', 'D'] satisfies FavoriteCategory[]
).map((category) => ({ key: category, label: FAVORITE_OUTPUT_LABELS[category] }))

export interface LyricsOutputSource {
  id: number
  task_id: number
  version_number: number
  title: string
  theme: string
  content: string
  style_prompt: string
  is_saved: boolean
  provider: string
  model: string | null
  created_at: string
}

function compactText(value: string, maxLength = 180): string {
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > maxLength ? `${compact.slice(0, maxLength)}...` : compact
}

export function buildLyricsOutputItems(
  sources: LyricsOutputSource[],
  favorites: FavoriteItem[],
): UpstreamOutputItem[] {
  const favoriteByVersion = new Map(
    favorites
      .filter((favorite) => favorite.item_type === 'lyrics')
      .map((favorite) => [favorite.target_id, favorite]),
  )
  return sources.map((source) => {
    const favorite = favoriteByVersion.get(source.id)
    const category = favorite?.category ?? 'unclassified'
    const model = source.model || source.provider
    return {
      id: source.id,
      title: source.title,
      source: `作词任务 #${source.task_id} · 歌词版本 #${source.id} · V${source.version_number}`,
      summary: compactText(source.content) || compactText(source.style_prompt) || source.theme,
      createdAt: source.created_at,
      group: category,
      tags: [
        FAVORITE_OUTPUT_LABELS[category],
        source.is_saved ? '当前作品' : `V${source.version_number}`,
      ],
      meta: [
        { label: '作词任务', value: `#${source.task_id}` },
        { label: '歌词版本', value: `#${source.id} / V${source.version_number}` },
        { label: '作品状态', value: source.is_saved ? '当前作品' : '历史版本' },
        { label: '收藏等级', value: FAVORITE_OUTPUT_LABELS[category] },
        { label: '创作主题', value: source.theme || '未记录' },
        { label: '模型 / 接口', value: model },
      ],
      searchText: [
        source.id,
        source.task_id,
        source.version_number,
        source.title,
        source.theme,
        source.content,
        source.style_prompt,
        favorite?.note,
      ].join(' '),
    }
  })
}
