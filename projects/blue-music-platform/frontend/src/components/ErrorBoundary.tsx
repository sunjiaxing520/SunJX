import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Result } from 'antd'

import { recordDiagnostic } from '../lib/diagnostics'

interface ErrorBoundaryState {
  hasError: boolean
}

export class ErrorBoundary extends Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    recordDiagnostic({
      source: 'render',
      message: `${error.message}\n${info.componentStack ?? ''}`,
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="full-page-result">
          <Result
            status="error"
            title="页面加载失败"
            subTitle="故障信息已记录，刷新后仍失败请复制诊断信息交给维护人员。"
            extra={
              <Button type="primary" onClick={() => window.location.reload()}>
                刷新页面
              </Button>
            }
          />
        </div>
      )
    }
    return this.props.children
  }
}
