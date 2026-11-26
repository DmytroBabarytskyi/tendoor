import { LoaderCircle, MapPinOff, ShieldX } from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Link, Navigate, RouterProvider, useLocation } from 'react-router'
import { ROLE_NAMES, type Role } from './api/client'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/context'
import { EmptyState } from './components/page'
import { Button } from './components/ui/button'
import { Toaster } from './components/ui/sonner'
import { TooltipProvider } from './components/ui/tooltip'
import AppLayout from './layout/AppLayout'
import { NAV } from './layout/nav'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import { ThemeProvider } from './theme/ThemeProvider'

// сторінки завантажуються окремими частинами бандла лише при першому переході
const AnalysisPage = lazy(() => import('./pages/analysis/AnalysisPage'))
const ResultPage = lazy(() => import('./pages/analysis/ResultPage'))
const AuditPage = lazy(() => import('./pages/AuditPage'))
const ChecksPage = lazy(() => import('./pages/audit/ChecksPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const SyncPage = lazy(() => import('./pages/SyncPage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))

function Loading() {
  return (
    <div className="grid min-h-[40vh] place-items-center text-muted-foreground" role="status">
      <LoaderCircle className="size-6 animate-spin" />
      <span className="sr-only">Завантаження…</span>
    </div>
  )
}

/** Маршрут лише для автентифікованих користувачів (і, за потреби, певних ролей). */
function Protected({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, ready, hasRole } = useAuth()
  const location = useLocation()
  if (!ready) return <Loading />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !hasRole(...roles)) {
    const page = NAV.find((n) => n.to !== '/' && location.pathname.startsWith(n.to))
    return (
      <EmptyState icon={ShieldX} title="Недостатньо прав" className="min-h-[50vh]">
        <p>
          {page ? `Сторінка «${page.label}»` : 'Ця сторінка'} доступна лише ролям: {roles.map((r) => ROLE_NAMES[r]).join(', ')}. Ваша роль –{' '}
          {ROLE_NAMES[user.role]}.
        </p>
        <p className="mt-1">Якщо доступ потрібен для роботи, зверніться до адміністратора системи.</p>
        <Button asChild variant="outline" size="sm" className="mt-3">
          <Link to="/">На головну</Link>
        </Button>
      </EmptyState>
    )
  }
  return <Suspense fallback={<Loading />}>{children}</Suspense>
}

function NotFound() {
  return (
    <EmptyState icon={MapPinOff} title="Сторінку не знайдено" className="min-h-[50vh]">
      <Button asChild variant="outline" size="sm" className="mt-2">
        <Link to="/">На головну</Link>
      </Button>
    </EmptyState>
  )
}

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    path: '/',
    element: (
      <Protected>
        <AppLayout />
      </Protected>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'analysis', element: <AnalysisPage /> },
      { path: 'analysis/:id', element: <ResultPage /> },
      { path: 'checks', element: <ChecksPage /> },
      { path: 'sync', element: <Protected roles={['admin', 'analyst']}><SyncPage /></Protected> },
      { path: 'users', element: <Protected roles={['admin']}><UsersPage /></Protected> },
      { path: 'settings', element: <Protected roles={['admin']}><SettingsPage /></Protected> },
      { path: 'audit', element: <Protected roles={['admin']}><AuditPage /></Protected> },
      { path: 'profile', element: <ProfilePage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

export default function App() {
  return (
    <ThemeProvider>
      <TooltipProvider delayDuration={250}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
        <Toaster position="bottom-right" richColors closeButton />
      </TooltipProvider>
    </ThemeProvider>
  )
}
