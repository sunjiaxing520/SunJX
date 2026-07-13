import { useState } from 'react'
import { Alert, Button, Form, Input, Typography } from 'antd'
import { ArrowRight, LockKeyhole, Music2, UserRound } from 'lucide-react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { errorMessage } from '../lib/errors'

interface LoginValues {
  username: string
  password: string
}

export function LoginPage() {
  const { user, isLoading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!isLoading && user) return <Navigate to="/" replace />

  const submit = async (values: LoginValues) => {
    setSubmitting(true)
    setError(null)
    try {
      await login(values.username.trim(), values.password)
      const destination = (location.state as { from?: { pathname?: string } } | null)
        ?.from?.pathname
      navigate(destination ?? '/', { replace: true })
    } catch (submitError) {
      setError(errorMessage(submitError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-brand">
          <span className="login-brand-mark"><Music2 size={24} /></span>
          <span>蓝乐 AI 音乐工作台</span>
        </div>
        <div className="login-heading">
          <Typography.Title id="login-title" level={1}>登录</Typography.Title>
          <Typography.Text type="secondary">使用已分配的内部账号进入工作台</Typography.Text>
        </div>
        {error && <Alert type="error" showIcon title={error} />}
        <Form<LoginValues>
          layout="vertical"
          requiredMark={false}
          onFinish={submit}
          autoComplete="off"
        >
          <Form.Item
            label="账号"
            name="username"
            rules={[{ required: true, message: '请输入账号' }]}
          >
            <Input
              size="large"
              prefix={<UserRound size={17} />}
              placeholder="请输入账号"
              autoComplete="username"
            />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少 8 位' },
            ]}
          >
            <Input.Password
              size="large"
              prefix={<LockKeyhole size={17} />}
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </Form.Item>
          <Button
            type="primary"
            size="large"
            htmlType="submit"
            loading={submitting}
            block
          >
            进入工作台 <ArrowRight size={17} />
          </Button>
        </Form>
        <footer>BLUE MUSIC PLATFORM · INTERNAL</footer>
      </section>
    </main>
  )
}
