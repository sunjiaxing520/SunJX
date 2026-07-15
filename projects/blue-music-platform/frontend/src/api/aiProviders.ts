import type {
  AiProviderConfig,
  AiProviderListResponse,
  AiProviderTemplate,
  AiProviderTestResult,
  AiProviderWritePayload,
} from '../types/api'
import { apiRequest } from './client'


export function listAiProviderTemplates(): Promise<AiProviderTemplate[]> {
  return apiRequest<AiProviderTemplate[]>('/ai-providers/templates')
}

export function listAiProviderConfigs(): Promise<AiProviderListResponse> {
  return apiRequest<AiProviderListResponse>('/ai-providers')
}

export function createAiProviderConfig(
  payload: AiProviderWritePayload,
): Promise<AiProviderConfig> {
  return apiRequest<AiProviderConfig>('/ai-providers', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAiProviderConfig(
  configId: number,
  payload: Partial<AiProviderWritePayload>,
): Promise<AiProviderConfig> {
  return apiRequest<AiProviderConfig>(`/ai-providers/${configId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function testAiProviderConfig(
  configId: number,
): Promise<AiProviderTestResult> {
  return apiRequest<AiProviderTestResult>(`/ai-providers/${configId}/test`, {
    method: 'POST',
  })
}

export function activateAiProviderConfig(
  configId: number,
): Promise<AiProviderConfig> {
  return apiRequest<AiProviderConfig>(`/ai-providers/${configId}/activate`, {
    method: 'POST',
  })
}

export function deleteAiProviderConfig(configId: number): Promise<void> {
  return apiRequest<void>(`/ai-providers/${configId}`, { method: 'DELETE' })
}

export function importEnvironmentAiProvider(): Promise<AiProviderConfig> {
  return apiRequest<AiProviderConfig>('/ai-providers/import-environment', {
    method: 'POST',
  })
}
