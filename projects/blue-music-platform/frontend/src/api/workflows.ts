import { apiRequest } from './client'
import type {
  WorkflowRun,
  WorkflowRunDeleteResult,
  WorkflowRunList,
  WorkflowTemplate,
  WorkflowTemplatePayload,
} from '../types/api'


export function listWorkflowTemplates() {
  return apiRequest<WorkflowTemplate[]>('/workflows/templates')
}

export function createWorkflowTemplate(payload: WorkflowTemplatePayload) {
  return apiRequest<WorkflowTemplate>('/workflows/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWorkflowTemplate(
  templateId: number,
  payload: WorkflowTemplatePayload,
) {
  return apiRequest<WorkflowTemplate>(`/workflows/templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteWorkflowTemplate(templateId: number) {
  return apiRequest<void>(`/workflows/templates/${templateId}`, {
    method: 'DELETE',
  })
}

export function startWorkflowRun(templateId: number) {
  return apiRequest<WorkflowRun>(`/workflows/templates/${templateId}/runs`, {
    method: 'POST',
  })
}

export function listWorkflowRuns(limit = 15) {
  return apiRequest<WorkflowRunList>(`/workflows/runs?limit=${limit}`)
}

export function getWorkflowRun(runId: number) {
  return apiRequest<WorkflowRun>(`/workflows/runs/${runId}`)
}

export function deleteWorkflowRun(runId: number) {
  return apiRequest<void>(`/workflows/runs/${runId}`, {
    method: 'DELETE',
  })
}

export function deleteWorkflowRuns(runIds: number[]) {
  return apiRequest<WorkflowRunDeleteResult>('/workflows/runs', {
    method: 'DELETE',
    body: JSON.stringify({ run_ids: runIds }),
  })
}
