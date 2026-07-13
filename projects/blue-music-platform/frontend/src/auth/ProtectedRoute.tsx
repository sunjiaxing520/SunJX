import { Spin } from 'antd'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="full-page-loader">
        <Spin size="large" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}
