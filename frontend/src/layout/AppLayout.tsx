import {
  AuditOutlined,
  CloudSyncOutlined,
  DashboardOutlined,
  LogoutOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Button, Layout, Menu, Space, Tag, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router'
import { ROLE_NAMES, type Role } from '../api/client'
import { useAuth } from '../auth/context'

type NavItem = { key: string; label: string; icon: ReactNode; roles: Role[] }

// Пункти меню відповідають бізнес-процесам; видимість — за роллю користувача
const NAV: NavItem[] = [
  { key: '/', label: 'Огляд', icon: <DashboardOutlined />, roles: ['admin', 'analyst', 'auditor'] },
  { key: '/sync', label: 'Синхронізація', icon: <CloudSyncOutlined />, roles: ['admin', 'analyst'] },
  { key: '/users', label: 'Користувачі', icon: <TeamOutlined />, roles: ['admin'] },
  { key: '/settings', label: 'Параметри аналізу', icon: <SettingOutlined />, roles: ['admin'] },
  { key: '/audit', label: 'Журнал аудиту', icon: <AuditOutlined />, roles: ['admin'] },
  { key: '/profile', label: 'Профіль', icon: <UserOutlined />, roles: ['admin', 'analyst', 'auditor'] },
]

export default function AppLayout() {
  const { user, logout, hasRole } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const items = NAV.filter((n) => hasRole(...n.roles)).map(({ key, label, icon }) => ({ key, label, icon }))

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider breakpoint="lg" collapsedWidth={0} theme="light" width={220}>
        <div style={{ padding: '20px 24px 12px' }}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Tendoor
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            цінові аномалії закупівель
          </Typography.Text>
        </div>
        <Menu mode="inline" selectedKeys={[location.pathname]} items={items} onClick={(e) => navigate(e.key)} />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{ background: '#fff', display: 'flex', justifyContent: 'flex-end', paddingInline: 24 }}
        >
          <Space>
            <span>{user?.full_name}</span>
            {user && <Tag color="blue">{ROLE_NAMES[user.role]}</Tag>}
            <Button icon={<LogoutOutlined />} onClick={() => logout().then(() => navigate('/login'))}>
              Вийти
            </Button>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ padding: 24 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
