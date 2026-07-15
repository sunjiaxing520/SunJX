import { useMemo, useState, type ReactNode } from 'react'
import {
  App,
  Button,
  Drawer,
  Dropdown,
  Grid,
  Layout,
  Menu,
  Space,
  Tooltip,
  Typography,
  type MenuProps,
} from 'antd'
import {
  BarChart3,
  Bot,
  ChartNoAxesCombined,
  ChevronDown,
  ClipboardCopy,
  FileMusic,
  FolderHeart,
  Gauge,
  LogOut,
  Menu as MenuIcon,
  Music2,
  Network,
  Settings,
  Users,
} from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { hasAgentAccess } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { copyDiagnosticReport } from '../lib/diagnostics'
import type { AgentType } from '../types/api'

const { Header, Sider, Content } = Layout

interface NavigationItem {
  key: string
  label: string
  icon: ReactNode
  agent?: AgentType
  adminOnly?: boolean
}

const NAVIGATION: NavigationItem[] = [
  { key: '/', label: '工作台', icon: <Gauge size={18} /> },
  {
    key: '/rankings',
    label: '榜单采集',
    icon: <BarChart3 size={18} />,
    agent: 'crawler',
  },
  {
    key: '/analysis',
    label: '内容分析',
    icon: <ChartNoAxesCombined size={18} />,
    agent: 'analysis',
  },
  {
    key: '/lyrics',
    label: '歌词创作',
    icon: <FileMusic size={18} />,
    agent: 'lyrics',
  },
  {
    key: '/music',
    label: '音乐创作',
    icon: <Music2 size={18} />,
    agent: 'music',
  },
  { key: '/favorites', label: '收藏夹', icon: <FolderHeart size={18} /> },
  { key: '/agents', label: 'Agent 状态', icon: <Bot size={18} /> },
  {
    key: '/admin/ai-providers',
    label: 'AI 接口',
    icon: <Network size={18} />,
    adminOnly: true,
  },
  {
    key: '/admin/users',
    label: '账号管理',
    icon: <Users size={18} />,
    adminOnly: true,
  },
]

function Brand() {
  return (
    <div className="brand-lockup">
      <span className="brand-mark"><Music2 size={19} /></span>
      <span>
        <strong>蓝乐</strong>
        <small>AI MUSIC OPS</small>
      </span>
    </div>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const screens = Grid.useBreakpoint()
  const isDesktop = screens.lg ?? false
  const [drawerOpen, setDrawerOpen] = useState(false)
  const environmentLabel = import.meta.env.PROD ? '生产环境' : '开发环境'

  const visibleNavigation = useMemo(
    () =>
      NAVIGATION.filter((item) => {
        if (!user) return false
        if (item.adminOnly && user.role !== 'super_admin') return false
        return !item.agent || hasAgentAccess(user, item.agent)
      }),
    [user],
  )
  const selectedKey =
    visibleNavigation.find((item) =>
      item.key === '/' ? location.pathname === '/' : location.pathname.startsWith(item.key),
    )?.key ?? '/'
  const pageTitle =
    visibleNavigation.find((item) => item.key === selectedKey)?.label ?? '工作台'
  const menuItems: MenuProps['items'] = visibleNavigation.map((item) => ({
    key: item.key,
    label: item.label,
    icon: item.icon,
  }))

  const navigateFromMenu: MenuProps['onClick'] = ({ key }) => {
    navigate(key)
    setDrawerOpen(false)
  }
  const userMenu: MenuProps['items'] = [
    {
      key: 'diagnostics',
      icon: <ClipboardCopy size={16} />,
      label: '复制诊断信息',
      onClick: async () => {
        try {
          await copyDiagnosticReport(user)
          message.success('诊断信息已复制')
        } catch {
          message.error('复制失败，请检查浏览器剪贴板权限')
        }
      },
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogOut size={16} />,
      label: '退出登录',
      danger: true,
      onClick: () => {
        logout()
        navigate('/login', { replace: true })
      },
    },
  ]

  const navigationMenu = (
    <Menu
      mode="inline"
      selectedKeys={[selectedKey]}
      items={menuItems}
      onClick={navigateFromMenu}
    />
  )

  return (
    <Layout className="app-layout">
      {isDesktop ? (
        <Sider width={232} className="app-sider" theme="light">
          <Brand />
          <nav className="main-navigation" aria-label="主导航">
            {navigationMenu}
          </nav>
          <div className="sider-environment">
            <Settings size={15} />
            <span>{environmentLabel}</span>
            <span className="environment-dot" />
          </div>
        </Sider>
      ) : (
        <Drawer
          placement="left"
          size={272}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          title={<Brand />}
          className="navigation-drawer"
        >
          {navigationMenu}
        </Drawer>
      )}

      <Layout>
        <Header className="app-header">
          <Space size={12}>
            {!isDesktop && (
              <Tooltip title="打开导航">
                <Button
                  type="text"
                  icon={<MenuIcon size={20} />}
                  aria-label="打开导航"
                  onClick={() => setDrawerOpen(true)}
                />
              </Tooltip>
            )}
            <Typography.Title level={2}>{pageTitle}</Typography.Title>
          </Space>
          <Dropdown menu={{ items: userMenu }} trigger={['click']}>
            <Button type="text" className="user-menu-button">
              <span className="user-avatar">{user?.username.charAt(0).toUpperCase()}</span>
              <span className="user-menu-copy">
                <strong>{user?.username}</strong>
                <small>{user?.role === 'super_admin' ? '超级管理员' : '成员'}</small>
              </span>
              <ChevronDown size={15} />
            </Button>
          </Dropdown>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
