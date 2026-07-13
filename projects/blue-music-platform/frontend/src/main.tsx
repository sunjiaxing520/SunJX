import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter } from 'react-router-dom'

import AppRoutes from './App'
import { AuthProvider } from './auth/AuthProvider'
import { ErrorBoundary } from './components/ErrorBoundary'
import 'antd/dist/reset.css'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#e1543f',
          colorInfo: '#3b73c5',
          colorSuccess: '#27845b',
          colorWarning: '#c08317',
          colorText: '#25272d',
          colorTextSecondary: '#70737c',
          colorBgLayout: '#f3f4f6',
          colorBorder: '#dedfe3',
          borderRadius: 6,
          fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', sans-serif",
        },
        components: {
          Button: { controlHeight: 36 },
          Layout: { headerBg: '#ffffff', siderBg: '#ffffff' },
          Menu: { itemBorderRadius: 5, itemHeight: 42 },
          Table: { headerBg: '#f6f7f8' },
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <ErrorBoundary>
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          </ErrorBoundary>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
)
