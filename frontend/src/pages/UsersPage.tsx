import { KeyRound, LoaderCircle, Plus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { api, ROLE_NAMES, type Role, type User } from '@/api/client'
import { useAuth } from '@/auth/context'
import { Page, PageHeader, Panel } from '@/components/page'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { dateTime } from '@/lib/format'
import { useBadges } from '@/layout/badges'
import RegistrationsPanel from './RegistrationsPanel'

const ROLES = Object.keys(ROLE_NAMES) as Role[]
const MIN_PASSWORD = 10

function RoleSelect({ value, onChange, disabled, className }: { value: Role; onChange: (r: Role) => void; disabled?: boolean; className?: string }) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as Role)} disabled={disabled}>
      <SelectTrigger className={className}><SelectValue /></SelectTrigger>
      <SelectContent>
        {ROLES.map((r) => (
          <SelectItem key={r} value={r}>{ROLE_NAMES[r]}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default function UsersPage() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState<User[] | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [creating, setCreating] = useState(false)
  const [resetFor, setResetFor] = useState<User | null>(null)
  const [form, setForm] = useState({ full_name: '', email: '', role: 'auditor' as Role, password: '' })
  const [newPassword, setNewPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<'users' | 'requests'>('users')
  const badges = useBadges()

  useEffect(() => {
    let alive = true
    api<User[]>('/users').then(
      (list) => alive && setUsers(list),
      (e: Error) => toast.error(e.message),
    )
    return () => {
      alive = false
    }
  }, [reloadKey])

  const patch = async (id: number, body: Partial<User> & { password?: string }) => {
    try {
      const updated = await api<User>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
      setUsers((list) => list?.map((u) => (u.id === id ? updated : u)) ?? null)
      toast.success('Збережено')
      return true
    } catch (e) {
      toast.error((e as Error).message)
      return false
    }
  }

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api<User>('/users', { method: 'POST', body: JSON.stringify(form) })
      toast.success('Користувача створено')
      setCreating(false)
      setForm({ full_name: '', email: '', role: 'auditor', password: '' })
      setReloadKey((k) => k + 1)
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Адміністрування"
        title="Користувачі"
        description="Облікові записи й ролі. Зміни фіксуються в журналі аудиту разом з автором."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus /> Новий користувач
          </Button>
        }
      />
      <div className="mb-4 flex gap-1 border-b">
        {(
          [
            ['users', 'Користувачі'],
            ['requests', 'Заявки на доступ'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm ${tab === key ? 'border-primary font-medium' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
          >
            {label}
            {key === 'requests' && (badges?.registrations ?? 0) > 0 && (
              <span className="rounded-full bg-primary px-1.5 text-[11px] leading-5 font-semibold text-primary-foreground">{badges?.registrations}</span>
            )}
          </button>
        ))}
      </div>
      {tab === 'requests' && <RegistrationsPanel onApproved={() => setReloadKey((k) => k + 1)} />}
      <Panel bodyClassName="p-0" className={tab === 'users' ? '' : 'hidden'}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">Користувач</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead>Активний</TableHead>
              <TableHead>Останній вхід</TableHead>
              <TableHead className="pr-5" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {users === null
              ? [0, 1, 2].map((i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5} className="px-5"><Skeleton className="h-8" /></TableCell>
                  </TableRow>
                ))
              : users.map((u) => (
                  <TableRow key={u.id} className={u.is_active ? '' : 'opacity-60'}>
                    <TableCell className="pl-5">
                      <div className="flex items-center gap-3">
                        <Avatar className="size-8">
                          <AvatarFallback className="bg-muted text-xs">{u.full_name.slice(0, 2).toUpperCase()}</AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <div className="truncate font-medium">{u.full_name}{u.id === me?.id && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(ви)</span>}</div>
                          <div className="truncate text-xs text-muted-foreground">{u.email}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <RoleSelect value={u.role} className="h-8 w-44" disabled={u.id === me?.id} onChange={(r) => patch(u.id, { role: r })} />
                    </TableCell>
                    <TableCell>
                      <Switch checked={u.is_active} disabled={u.id === me?.id} onCheckedChange={(v) => patch(u.id, { is_active: v })} aria-label="Активний" />
                    </TableCell>
                    <TableCell className="text-muted-foreground tabular">{u.last_login_at ? dateTime(u.last_login_at) : 'ще не входив'}</TableCell>
                    <TableCell className="pr-5 text-right">
                      <Button variant="ghost" size="sm" onClick={() => setResetFor(u)}>
                        <KeyRound /> Пароль
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </Panel>

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <form onSubmit={create} className="space-y-4">
            <DialogHeader>
              <DialogTitle className="font-serif text-xl">Новий користувач</DialogTitle>
              <DialogDescription>Початковий пароль передайте користувачу особисто; його можна змінити в профілі.</DialogDescription>
            </DialogHeader>
            <div className="space-y-1.5">
              <Label htmlFor="u-name">ПІБ</Label>
              <Input id="u-name" required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="u-email">Email</Label>
              <Input id="u-email" type="email" required autoComplete="off" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Роль</Label>
              <RoleSelect value={form.role} className="w-full" onChange={(r) => setForm({ ...form, role: r })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="u-pass">Початковий пароль</Label>
              <Input id="u-pass" type="password" required minLength={MIN_PASSWORD} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <p className="text-xs text-muted-foreground">Щонайменше {MIN_PASSWORD} символів.</p>
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCreating(false)}>Скасувати</Button>
              <Button type="submit" disabled={busy}>{busy && <LoaderCircle className="animate-spin" />}Створити</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!resetFor} onOpenChange={(o) => !o && setResetFor(null)}>
        <DialogContent>
          <form
            className="space-y-4"
            onSubmit={async (e) => {
              e.preventDefault()
              if (resetFor && (await patch(resetFor.id, { password: newPassword }))) {
                setResetFor(null)
                setNewPassword('')
              }
            }}
          >
            <DialogHeader>
              <DialogTitle className="font-serif text-xl">Новий пароль</DialogTitle>
              <DialogDescription>{resetFor?.email} — усі активні сесії користувача буде завершено.</DialogDescription>
            </DialogHeader>
            <div className="space-y-1.5">
              <Label htmlFor="r-pass">Пароль</Label>
              <Input id="r-pass" type="password" required minLength={MIN_PASSWORD} autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setResetFor(null)}>Скасувати</Button>
              <Button type="submit">Зберегти</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
