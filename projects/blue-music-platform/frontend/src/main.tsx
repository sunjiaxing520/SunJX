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
          colorPrimary: '#d84f3d',
          colorPrimaryHover: '#c84737',
          colorPrimaryActive: '#b83e30',
          colorInfo: '#2f6fa8',
          colorSuccess: '#26805a',
          colorWarning: '#b77917',
          colorText: '#20242b',
          colorTextSecondary: '#68707b',
          colorTextTertiary: '#9298a1',
          colorBgLayout: '#f2f4f6',
          colorBgContainer: '#ffffff',
          colorBorder: '#dfe3e8',
          colorBorderSecondary: '#eceef1',
          borderRadius: 6,
          borderRadiusLG: 8,
          controlHeight: 38,
          fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', sans-serif",
        },
        components: {
          Button: { controlHeight: 38, primaryShadow: 'none' },
          Collapse: { contentBg: '#ffffff', headerBg: '#ffffff' },
          Input: { activeBorderColor: '#d84f3d', hoverBorderColor: '#c9ced5' },
          Layout: { bodyBg: '#f2f4f6', headerBg: '#ffffff', siderBg: '#ffffff' },
          Menu: {
            groupTitleColor: '#9298a1',
            itemBg: '#ffffff',
            itemBorderRadius: 6,
            itemHeight: 40,
            itemHoverBg: '#f5f6f8',
            itemMarginBlock: 2,
            itemMarginInline: 10,
            itemSelectedBg: '#fff0ec',
            itemSelectedColor: '#b83e30',
          },
          Select: { optionSelectedBg: '#fff0ec' },
          Table: {
            cellPaddingBlock: 12,
            cellPaddingInline: 14,
            headerBg: '#f7f8fa',
            headerColor: '#4b525c',
            rowHoverBg: '#fff8f6',
          },
          Tabs: { inkBarColor: '#d84f3d', itemSelectedColor: '#b83e30' },
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
