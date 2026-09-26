import { LogOut, Menu, Monitor, Moon, Search, Sun, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { ROLE_NAMES } from '@/api/client'
import { useAuth } from '@/auth/context'
import Logo from '@/components/Logo'
import { Kbd } from '@/components/page'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { useTheme, type ThemeChoice } from '@/theme/context'
import { useBadges, type Badges } from './badges'
import CommandPalette from './CommandPalette'
import { isActive, NAV } from './nav'

function initials(name: string | undefined) {
  return (name ?? '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0])
    .join('')
    .toUpperCase()
}

function badgeFor(to: string, b: Badges | null): number {
  if (!b) return 0
  if (to === '/checks') return b.to_review + b.returned
  if (to === '/users') return b.registrations ?? 0
  return 0
}

function SidebarNav({ onNavigate, badges }: { onNavigate?: () => void; badges: Badges | null }) {
  const { hasRole } = useAuth()
  const { pathname } = useLocation()
  const items = NAV.filter((n) => hasRole(...n.roles))
  const groups = [...new Set(items.map((i) => i.group))]
  return (
    <nav className="flex flex-col gap-5 px-3" aria-label="Розділи">
      {groups.map((g) => (
        <div key={g}>
          <div className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{g}</div>
          <ul className="space-y-0.5">
            {items
              .filter((i) => i.group === g)
              .map((n) => {
                const active = isActive(n.to, pathname)
                return (
                  <li key={n.to}>
                    <Link
                      to={n.to}
                      onClick={onNavigate}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
                        active
                          ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                          : 'text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                      )}
                    >
                      {active && <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-primary" />}
                      <n.icon className={cn('size-4', active ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground')} />
                      <span className="flex-1">{n.label}</span>
                      {badgeFor(n.to, badges) > 0 && (
                        <span
                          className="min-w-5 rounded-full bg-primary px-1.5 text-center text-[11px] leading-5 font-semibold text-primary-foreground tabular"
                          aria-label={`${badgeFor(n.to, badges)} очікують дії`}
                        >
                          {badgeFor(n.to, badges)}
                        </span>
                      )}
                    </Link>
                  </li>
                )
              })}
          </ul>
        </div>
      ))}
    </nav>
  )
}

const THEME_ICON: Record<ThemeChoice, typeof Sun> = { light: Sun, dark: Moon, system: Monitor }

export default function AppLayout() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const ThemeIcon = THEME_ICON[theme]
  const badges = useBadges()

  return (
    <div className="min-h-svh bg-background">
      {/* бічна панель — з ширини lg; на вужчих екранах висувна */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <div className="px-6 pt-6 pb-7">
          <Link to="/" aria-label="Tendoor — на головну">
            <Logo />
          </Link>
        </div>
        <SidebarNav badges={badges} />
        <div className="mt-auto p-4">
          <div className="rounded-lg border border-sidebar-border bg-background/60 p-3 text-xs text-muted-foreground">
            <div className="mb-1 font-medium text-foreground">Підказка</div>
            Натисніть <Kbd>Ctrl</Kbd> <Kbd>K</Kbd>, щоб перейти до будь-якого розділу чи аналізу за номером.
          </div>
        </div>
      </aside>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-72 bg-sidebar p-0">
          <SheetTitle className="sr-only">Меню</SheetTitle>
          <div className="px-6 pt-6 pb-6">
            <Logo />
          </div>
          <SidebarNav badges={badges} onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur-md sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Відкрити меню">
            <Menu />
          </Button>
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex h-9 w-full max-w-sm items-center gap-2 rounded-lg border bg-card px-3 text-sm text-muted-foreground transition-colors hover:bg-accent/50"
          >
            <Search className="size-4" />
            <span className="flex-1 text-left">Пошук розділу або аналізу…</span>
            <span className="hidden gap-0.5 sm:flex">
              <Kbd>Ctrl</Kbd>
              <Kbd>K</Kbd>
            </span>
          </button>
          <div className="ml-auto flex items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Тема оформлення">
                  <ThemeIcon />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Тема</DropdownMenuLabel>
                <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as ThemeChoice)}>
                  <DropdownMenuRadioItem value="light">Світла</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="dark">Темна</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="system">Як у системі</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-9 gap-2 px-1.5 sm:px-2" aria-label="Обліковий запис">
                  <Avatar className="size-7">
                    <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">{initials(user?.full_name)}</AvatarFallback>
                  </Avatar>
                  <span className="hidden text-left leading-tight sm:block">
                    <span className="block text-sm font-medium">{user?.full_name}</span>
                    <span className="block text-[11px] text-muted-foreground">{user && ROLE_NAMES[user.role]}</span>
                  </span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="text-sm font-medium">{user?.full_name}</div>
                  <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => navigate('/profile')}>
                  <UserRound /> Профіль
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onSelect={() => logout().then(() => navigate('/login'))}>
                  <LogOut /> Вийти
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}
