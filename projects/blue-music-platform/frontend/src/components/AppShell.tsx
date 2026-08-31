import { useMemo, useState, type ReactNode } from 'react'
import {
  App,
  Button,
  Drawer,
  Dropdown,
  Grid,
  Layout,
  Menu,
  Tooltip,
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
  BrainCircuit,
  LogOut,
  Menu as MenuIcon,
  Music2,
  Network,
  ShieldCheck,
  Settings,
  Users,
  Workflow as WorkflowIcon,
} from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { hasAgentAccess } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { copyDiagnosticReport } from '../lib/diagnostics'
import type { AgentType } from '../types/api'
import { WatermarkLayer } from './WatermarkLayer'

const { Header, Sider, Content } = Layout

interface NavigationItem {
  key: string
  label: string
  icon: ReactNode
  section: 'overview' | 'creation' | 'assets' | 'admin'
  agent?: AgentType
  adminOnly?: boolean
}

const NAVIGATION: NavigationItem[] = [
  { key: '/', label: '工作台', icon: <Gauge size={18} />, section: 'overview' },
  {
    key: '/workflows',
    label: '自动流程',
    icon: <WorkflowIcon size={18} />,
    section: 'creation',
  },
  {
    key: '/rankings',
    label: '榜单数据',
    icon: <BarChart3 size={18} />,
    section: 'creation',
  },
  {
    key: '/analysis',
    label: '内容分析',
    icon: <ChartNoAxesCombined size={18} />,
    section: 'creation',
    agent: 'analysis',
  },
  {
    key: '/lyrics',
    label: '歌词创作',
    icon: <FileMusic size={18} />,
    section: 'creation',
    agent: 'lyrics',
  },
  {
    key: '/music',
    label: '音乐创作',
    icon: <Music2 size={18} />,
    section: 'creation',
    agent: 'music',
  },
  {
    key: '/favorites',
    label: '收藏夹',
    icon: <FolderHeart size={18} />,
    section: 'assets',
  },
  {
    key: '/review-agents',
    label: '审核智能体',
    icon: <ShieldCheck size={18} />,
    section: 'assets',
  },
  {
    key: '/agents',
    label: 'Agent 状态',
    icon: <Bot size={18} />,
    section: 'assets',
  },
  {
    key: '/admin/ai-providers',
    label: 'AI 接口',
    icon: <Network size={18} />,
    section: 'admin',
    adminOnly: true,
  },
  {
    key: '/admin/lyrics-memory',
    label: '歌词记忆',
    icon: <BrainCircuit size={18} />,
    section: 'admin',
    adminOnly: true,
  },
  {
    key: '/admin/users',
    label: '账号管理',
    icon: <Users size={18} />,
    section: 'admin',
    adminOnly: true,
  },
]

const NAVIGATION_SECTIONS = [
  { key: 'overview', label: '总览' },
  { key: 'creation', label: '创作流程' },
  { key: 'assets', label: '资产与协作' },
  { key: 'admin', label: '系统管理' },
] as const

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
  const activeNavigationItem = visibleNavigation.find((item) =>
    item.key === '/' ? location.pathname === '/' : location.pathname.startsWith(item.key),
  )
  const selectedKey = activeNavigationItem?.key ?? '/'
  const pageTitle = activeNavigationItem?.label ?? '工作台'
  const menuItems: MenuProps['items'] = NAVIGATION_SECTIONS.map((section) => ({
    type: 'group' as const,
    label: <span className="navigation-group-label">{section.label}</span>,
    children: visibleNavigation
      .filter((item) => item.section === section.key)
      .map((item) => ({
        key: item.key,
        label: item.label,
        icon: item.icon,
      })),
  })).filter((section) => section.children.length > 0)

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
      <WatermarkLayer text={user?.watermark_text ?? user?.username ?? ''} />
      {isDesktop ? (
        <Sider width={236} className="app-sider" theme="light">
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
          <div className="app-header-leading">
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
            <div className="header-context">
              <span className="header-context-icon">{activeNavigationItem?.icon}</span>
              <span className="header-context-copy">
                <small>蓝乐工作台</small>
                <strong>{pageTitle}</strong>
              </span>
            </div>
          </div>
          <Dropdown menu={{ items: userMenu }} trigger={['click']}>
            <Button type="text" className="user-menu-button" aria-label="打开账号菜单">
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
