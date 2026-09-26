import {
  FlaskConical,
  LayoutDashboard,
  RefreshCw,
  ScanSearch,
  ScrollText,
  SlidersHorizontal,
  UserRound,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { Role } from '@/api/client'

export type NavItem = { to: string; label: string; icon: LucideIcon; roles: Role[]; group: string; hint: string }

const ALL: Role[] = ['admin', 'analyst', 'auditor']

// Пункти меню відповідають бізнес-процесам (A1–A4); видимість — за роллю користувача
export const NAV: NavItem[] = [
  { to: '/', label: 'Огляд', icon: LayoutDashboard, roles: ALL, group: 'Робота', hint: 'стан бази закупівель' },
  { to: '/analysis', label: 'Аналіз аномалій', icon: FlaskConical, roles: ALL, group: 'Робота', hint: 'нова вибірка, мої аналізи' },
  { to: '/checks', label: 'Перевірки', icon: ScanSearch, roles: ALL, group: 'Робота', hint: 'історія вердиктів' },
  { to: '/sync', label: 'Синхронізація', icon: RefreshCw, roles: ['admin', 'analyst'], group: 'Дані', hint: 'завантаження з Prozorro' },
  { to: '/users', label: 'Користувачі', icon: Users, roles: ['admin'], group: 'Адміністрування', hint: 'облікові записи й ролі' },
  { to: '/settings', label: 'Параметри аналізу', icon: SlidersHorizontal, roles: ['admin'], group: 'Адміністрування', hint: 'значення за замовчуванням' },
  { to: '/audit', label: 'Журнал аудиту', icon: ScrollText, roles: ['admin'], group: 'Адміністрування', hint: 'усі дії в системі' },
  { to: '/profile', label: 'Профіль', icon: UserRound, roles: ALL, group: 'Обліковий запис', hint: 'зміна пароля' },
]

export const isActive = (to: string, path: string) => (to === '/' ? path === '/' : path === to || path.startsWith(`${to}/`))
