import type { AnalysisTask, AnalysisTaskList, TaskDeleteResult } from '../types/api'
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

export function deleteAnalysisTask(taskId: number): Promise<void> {
  return apiRequest<void>(`/analysis/tasks/${taskId}`, { method: 'DELETE' })
}

export function deleteAnalysisTasks(taskIds: number[]): Promise<TaskDeleteResult> {
  return apiRequest<TaskDeleteResult>('/analysis/tasks', {
    method: 'DELETE',
    body: JSON.stringify({ task_ids: taskIds }),
  })
}
