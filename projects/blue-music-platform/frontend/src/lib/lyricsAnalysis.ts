import type {
  AnalysisTask,
  CreationDirection,
  FavoriteCategory,
  FavoriteItem,
} from '../types/api'

export const ANALYSIS_CATEGORY_ORDER: FavoriteCategory[] = [
  'unclassified',
  'S',
  'A',
  'B',
  'C',
  'D',
]

export const ANALYSIS_CATEGORY_LABELS: Record<FavoriteCategory, string> = {
  unclassified: '待分类',
  S: 'S 级',
  A: 'A 级',
  B: 'B 级',
  C: 'C 级',
  D: 'D 级',
}

export interface LyricsAnalysisDirection {
  value: string
  analysisTaskId: number
  reportId: number
  category: FavoriteCategory
  directionIndex: number
  direction: CreationDirection
  summary: string
  createdAt: string
}

export function buildLyricsAnalysisDirections(
  tasks: AnalysisTask[],
  favorites: FavoriteItem[],
): LyricsAnalysisDirection[] {
  const favoriteByReport = new Map(
    favorites.map((favorite) => [favorite.target_id, favorite]),
  )
  const knownReportIds = new Set<number>()
  const choices = tasks.flatMap((task) => {
    const report = task.report
    if (!report) return []
    knownReportIds.add(report.id)
    const favorite = favoriteByReport.get(report.id)
    return report.creation_directions.map((direction, directionIndex) => ({
      value: `${report.id}:${directionIndex}`,
      analysisTaskId: task.id,
      reportId: report.id,
      category: favorite?.category ?? 'unclassified',
      directionIndex,
      direction,
      summary: report.trend_summary,
      createdAt: report.created_at,
    }))
  })

  for (const favorite of favorites) {
    if (knownReportIds.has(favorite.target_id)) continue
    const rawDirections = favorite.metadata.creation_directions
    if (!Array.isArray(rawDirections)) continue
    rawDirections.forEach((rawDirection, directionIndex) => {
      if (!rawDirection || typeof rawDirection !== 'object') return
      choices.push({
        value: `${favorite.target_id}:${directionIndex}`,
        analysisTaskId: favorite.source_task_id,
        reportId: favorite.target_id,
        category: favorite.category,
        directionIndex,
        direction: rawDirection as CreationDirection,
        summary: favorite.summary,
        createdAt: favorite.source_created_at,
      })
    })
  }

  return choices.sort((left, right) => {
    const dateOrder = right.createdAt.localeCompare(left.createdAt)
    if (dateOrder) return dateOrder
    return left.directionIndex - right.directionIndex
  })
}

export function analysisDirectionLabel(choice: LyricsAnalysisDirection): string {
  return `榜单分析 #${choice.analysisTaskId} · 方向 ${choice.directionIndex + 1}：${choice.direction.name}`
}
