import { LogOut, Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '@/auth/context'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command'
import { useTheme } from '@/theme/context'
import { NAV } from './nav'

/** Палітра команд (Ctrl/⌘ + K): перехід до будь-якого розділу, тема, вихід — без миші. */
export default function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const navigate = useNavigate()
  const { hasRole, logout } = useAuth()
  const { setTheme } = useTheme()
  const [query, setQuery] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const run = (fn: () => void) => {
    onOpenChange(false)
    setQuery('')
    fn()
  }
  const items = NAV.filter((n) => hasRole(...n.roles))
  const analysisId = /^\d+$/.test(query.trim()) ? query.trim() : null

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Команди" description="Перехід до розділу або дія">
      <CommandInput placeholder="Куди перейти? Номер аналізу, розділ, тема…" value={query} onValueChange={setQuery} />
      <CommandList>
        <CommandEmpty>Нічого не знайдено</CommandEmpty>
        {analysisId && (
          <CommandGroup heading="Аналіз">
            <CommandItem value={`аналіз ${analysisId}`} onSelect={() => run(() => navigate(`/analysis/${analysisId}`))}>
              Відкрити аналіз №{analysisId}
            </CommandItem>
          </CommandGroup>
        )}
        <CommandGroup heading="Розділи">
          {items.map((n) => (
            <CommandItem key={n.to} value={`${n.label} ${n.hint}`} onSelect={() => run(() => navigate(n.to))}>
              <n.icon />
              <span>{n.label}</span>
              <span className="text-xs text-muted-foreground">{n.hint}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Тема">
          <CommandItem value="світла тема" onSelect={() => run(() => setTheme('light'))}>
            <Sun /> Світла
          </CommandItem>
          <CommandItem value="темна тема" onSelect={() => run(() => setTheme('dark'))}>
            <Moon /> Темна
          </CommandItem>
          <CommandItem value="системна тема" onSelect={() => run(() => setTheme('system'))}>
            <Monitor /> Як у системі
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Обліковий запис">
          <CommandItem value="вийти вихід" onSelect={() => run(() => logout().then(() => navigate('/login')))}>
            <LogOut /> Вийти
            <CommandShortcut>сесію завершено</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
