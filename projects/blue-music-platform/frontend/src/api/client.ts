import { recordDiagnostic } from '../lib/diagnostics'
import type { ApiErrorBody } from '../types/api'

export const TOKEN_KEY = 'blue_music_access_token'
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

const AUTH_FAILURE_CODES = new Set([
  'AUTH_TOKEN_MISSING',
  'AUTH_TOKEN_INVALID',
  'AUTH_TOKEN_EXPIRED',
  'AUTH_TOKEN_REVOKED',
  'USER_INACTIVE',
])

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId?: string
  readonly detail?: unknown

  constructor(options: {
    message: string
    status: number
    code: string
    requestId?: string
    detail?: unknown
  }) {
    super(options.message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code
    this.requestId = options.requestId
    this.detail = options.detail
  }
}

async function readResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined

  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) return response.json()
  return response.text()
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  const token = localStorage.getItem(TOKEN_KEY)

  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  } catch {
    const error = new ApiError({
      message: '无法连接后端服务，请确认服务是否已经启动',
      status: 0,
      code: 'NETWORK_ERROR',
    })
    recordDiagnostic({
      source: 'api',
      message: error.message,
      method: options.method ?? 'GET',
      path,
      status: 0,
      code: error.code,
    })
    throw error
  }

  const body = await readResponseBody(response)
  if (response.ok) return body as T

  const apiBody = body as ApiErrorBody
  const requestId =
    apiBody?.error?.request_id ??
    response.headers.get('x-request-id') ??
    undefined
  const error = new ApiError({
    message: apiBody?.error?.message ?? `请求失败 (${response.status})`,
    status: response.status,
    code: apiBody?.error?.code ?? 'UNKNOWN_ERROR',
    requestId,
    detail: apiBody?.error?.detail,
  })

  recordDiagnostic({
    source: 'api',
    message: error.message,
    method: options.method ?? 'GET',
    path,
    status: error.status,
    code: error.code,
    request_id: error.requestId,
  })
  if (AUTH_FAILURE_CODES.has(error.code)) {
    window.dispatchEvent(new Event('blue-music:auth-failed'))
  }
  throw error
}

export async function apiBlobRequest(path: string): Promise<Blob> {
  const headers = new Headers()
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers })
  } catch {
    const error = new ApiError({
      message: '无法连接后端服务，请确认服务是否已经启动',
      status: 0,
      code: 'NETWORK_ERROR',
    })
    recordDiagnostic({
      source: 'api',
      message: error.message,
      method: 'GET',
      path,
      status: 0,
      code: error.code,
    })
    throw error
  }

  if (response.ok) return response.blob()
  const body = await readResponseBody(response)
  const apiBody = body as ApiErrorBody
  const error = new ApiError({
    message: apiBody?.error?.message ?? `请求失败 (${response.status})`,
    status: response.status,
    code: apiBody?.error?.code ?? 'UNKNOWN_ERROR',
    requestId:
      apiBody?.error?.request_id ??
      response.headers.get('x-request-id') ??
      undefined,
    detail: apiBody?.error?.detail,
  })
  recordDiagnostic({
    source: 'api',
    message: error.message,
    method: 'GET',
    path,
    status: error.status,
    code: error.code,
    request_id: error.requestId,
  })
  if (AUTH_FAILURE_CODES.has(error.code)) {
    window.dispatchEvent(new Event('blue-music:auth-failed'))
  }
  throw error
}
