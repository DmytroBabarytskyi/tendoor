import { App as AntApp, ConfigProvider, Result, Spin } from 'antd'
import ukUA from 'antd/locale/uk_UA'
import dayjs from 'dayjs'
import 'dayjs/locale/uk'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, RouterProvider, useLocation } from 'react-router'
import type { Role } from './api/client'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/context'
import AppLayout from './layout/AppLayout'
import LoginPage from './pages/LoginPage'

dayjs.locale('uk')

// сторінки завантажуються окремими частинами бандла лише при першому переході
const AuditPage = lazy(() => import('./pages/AuditPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const SyncPage = lazy(() => import('./pages/SyncPage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))

/** Маршрут лише для автентифікованих користувачів (і, за потреби, певних ролей). */
function Protected({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, ready, hasRole } = useAuth()
  const location = useLocation()
  if (!ready) return <Spin fullscreen />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !hasRole(...roles)) {
    return <Result status="403" title="Недостатньо прав" subTitle="Ця сторінка недоступна для вашої ролі." />
  }
  return <Suspense fallback={<Spin />}>{children}</Suspense>
}

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <Protected>
        <AppLayout />
      </Protected>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'sync', element: <Protected roles={['admin', 'analyst']}><SyncPage /></Protected> },
      { path: 'users', element: <Protected roles={['admin']}><UsersPage /></Protected> },
      { path: 'settings', element: <Protected roles={['admin']}><SettingsPage /></Protected> },
      { path: 'audit', element: <Protected roles={['admin']}><AuditPage /></Protected> },
      { path: 'profile', element: <ProfilePage /> },
      { path: '*', element: <Result status="404" title="Сторінку не знайдено" /> },
    ],
  },
])

export default function App() {
  return (
    <ConfigProvider locale={ukUA} theme={{ token: { colorPrimary: '#1d5fbf', borderRadius: 6 } }}>
      <AntApp>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </AntApp>
    </ConfigProvider>
  )
}
