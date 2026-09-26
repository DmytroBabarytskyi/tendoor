import { LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { changePassword, ROLE_NAMES } from '@/api/client'
import { useAuth } from '@/auth/context'
import { Page, PageHeader, Panel } from '@/components/page'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useTheme, type ThemeChoice } from '@/theme/context'
import { cn } from '@/lib/utils'

const MIN_PASSWORD = 10
const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: 'light', label: 'Світла' },
  { value: 'dark', label: 'Темна' },
  { value: 'system', label: 'Як у системі' },
]

export default function ProfilePage() {
  const { user } = useAuth()
  const { theme, setTheme } = useTheme()
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const mismatch = confirm.length > 0 && confirm !== newPassword

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (mismatch) return
    setBusy(true)
    try {
      await changePassword(oldPassword, newPassword)
      toast.success('Пароль змінено. Інші сесії завершено.')
      setOldPassword('')
      setNewPassword('')
      setConfirm('')
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page className="max-w-3xl">
      <PageHeader title="Профіль" />
      <div className="space-y-4">
        <Panel title="Обліковий запис">
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div><dt className="text-muted-foreground">ПІБ</dt><dd className="mt-0.5 font-medium">{user?.full_name}</dd></div>
            <div><dt className="text-muted-foreground">Email</dt><dd className="mt-0.5 font-medium break-all">{user?.email}</dd></div>
            <div><dt className="text-muted-foreground">Роль</dt><dd className="mt-0.5 font-medium">{user && ROLE_NAMES[user.role]}</dd></div>
          </dl>
        </Panel>
        <Panel title="Оформлення">
          <div className="flex gap-2">
            {THEMES.map((t) => (
              <button
                key={t.value}
                onClick={() => setTheme(t.value)}
                aria-pressed={theme === t.value}
                className={cn('rounded-md border px-4 py-2 text-sm transition-colors', theme === t.value ? 'border-primary bg-primary/10' : 'hover:bg-accent/60')}
              >
                {t.label}
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Зміна пароля" description="Після зміни всі інші сесії буде завершено">
          <form onSubmit={submit} className="max-w-sm space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="old">Поточний пароль</Label>
              <Input id="old" type="password" required autoComplete="current-password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new">Новий пароль</Label>
              <Input id="new" type="password" required minLength={MIN_PASSWORD} autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
              <p className="text-xs text-muted-foreground">Щонайменше {MIN_PASSWORD} символів.</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm">Повторіть новий пароль</Label>
              <Input id="confirm" type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-invalid={mismatch} />
              {mismatch && <p className="text-xs text-critical">Паролі не збігаються</p>}
            </div>
            <Button type="submit" disabled={busy || mismatch}>
              {busy && <LoaderCircle className="animate-spin" />}
              Змінити пароль
            </Button>
          </form>
        </Panel>
      </div>
    </Page>
  )
}
