import type { AnalysisTask, AnalysisTaskList } from '../types/api'
import { apiRequest } from './client'

export function runAnalysis(entryIds: number[], windowDays = 7): Promise<AnalysisTask> {
  return apiRequest<AnalysisTask>('/analysis/tasks', {
    method: 'POST',
    body: JSON.stringify({ entry_ids: entryIds, window_days: windowDays }),
  })
}

export function listAnalysisTasks(): Promise<AnalysisTaskList> {
  return apiRequest<AnalysisTaskList>('/analysis/tasks?limit=15')
}

export function getAnalysisTask(taskId: number): Promise<AnalysisTask> {
  return apiRequest<AnalysisTask>(`/analysis/tasks/${taskId}`)
}
