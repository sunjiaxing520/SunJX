import { lazy, Suspense } from 'react'
import { Spin } from 'antd'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { hasAgentAccess } from './auth/permissions'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { useAuth } from './auth/useAuth'
import { AppShell } from './components/AppShell'
import type { AgentType } from './types/api'

const AgentsPage = lazy(() =>
  import('./pages/AgentsPage').then((module) => ({ default: module.AgentsPage })),
)
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const EmptyModulePage = lazy(() =>
  import('./pages/EmptyModulePage').then((module) => ({ default: module.EmptyModulePage })),
)
const LoginPage = lazy(() =>
  import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })),
)
const UsersPage = lazy(() =>
  import('./pages/UsersPage').then((module) => ({ default: module.UsersPage })),
)

function AgentRoute({ agent }: { agent: AgentType }) {
  const { user } = useAuth()
  return user && hasAgentAccess(user, agent) ? <Outlet /> : <Navigate to="/" replace />
}

function AdminRoute() {
  const { user } = useAuth()
  return user?.role === 'super_admin' ? <Outlet /> : <Navigate to="/" replace />
}

export default function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div className="full-page-loader">
          <Spin size="large" />
        </div>
      }
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route element={<AgentRoute agent="crawler" />}>
              <Route
                path="rankings"
                element={<EmptyModulePage title="榜单采集" description="采集任务与数据记录" />}
              />
            </Route>
            <Route element={<AgentRoute agent="analysis" />}>
              <Route
                path="analysis"
                element={<EmptyModulePage title="内容分析" description="作品分析任务与报告" />}
              />
            </Route>
            <Route element={<AgentRoute agent="lyrics" />}>
              <Route
                path="lyrics"
                element={<EmptyModulePage title="歌词创作" description="歌词任务与产出文件" />}
              />
            </Route>
            <Route element={<AgentRoute agent="music" />}>
              <Route
                path="music"
                element={<EmptyModulePage title="音乐创作" description="音乐任务与产出文件" />}
              />
            </Route>
            <Route path="agents" element={<AgentsPage />} />
            <Route element={<AdminRoute />}>
              <Route path="admin/users" element={<UsersPage />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
