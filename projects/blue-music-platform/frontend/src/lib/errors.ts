import { ApiError } from '../api/client'

function detailReason(detail: unknown): string | null {
  if (!detail || typeof detail !== 'object') return null

  const reason = (detail as { reason?: unknown }).reason
  return typeof reason === 'string' && reason.trim() ? reason.trim() : null
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const reason = detailReason(error.detail)
    const message = reason && reason !== error.message
      ? `${error.message}：${reason}`
      : error.message

    return error.requestId
      ? `${message}（请求编号：${error.requestId}）`
      : message
  }
  return error instanceof Error ? error.message : '发生未知错误'
}
