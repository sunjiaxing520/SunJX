import { ApiError } from '../api/client'

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.requestId
      ? `${error.message}（请求编号：${error.requestId}）`
      : error.message
  }
  return error instanceof Error ? error.message : '发生未知错误'
}
