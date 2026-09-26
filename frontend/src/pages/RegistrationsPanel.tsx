import { Check, Inbox, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api, ROLE_NAMES, type Role } from '@/api/client'
import { EmptyState, Panel } from '@/components/page'
import { Pill } from '@/components/status'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { dateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { refreshBadges } from '@/layout/badges'

type Registration = {
  id: number
  email: string
  full_name: string
  requested_role: Role
  justification: string | null
  status: 'pending' | 'approved' | 'rejected'
  decided_by_name: string | null
  decided_at: string | null
  reject_reason: string | null
  created_at: string
}

const FILTERS = [
  { value: 'pending', label: 'Очікують' },
  { value: 'approved', label: 'Погоджені' },
  { value: 'rejected', label: 'Відхилені' },
] as const

/** Заявки на доступ (A4.1): погодити з призначенням ролі або відхилити з причиною. */
export default function RegistrationsPanel({ onApproved }: { onApproved: () => void }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]['value']>('pending')
  const [items, setItems] = useState<Registration[] | null>(null)
  const [roles, setRoles] = useState<Record<number, Role>>({})
  const [rejecting, setRejecting] = useState<Registration | null>(null)
  const [reason, setReason] = useState('')

  const load = useCallback(() => {
    api<Registration[]>(`/registrations?status_=${filter}`).then(setItems)
  }, [filter])
  useEffect(load, [load])

  const approve = async (r: Registration) => {
    try {
      await api(`/registrations/${r.id}/approve`, { method: 'POST', body: JSON.stringify({ role: roles[r.id] ?? r.requested_role }) })
      toast.success(`Доступ надано: ${r.full_name}`)
      load()
      refreshBadges()
      onApproved()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const reject = async () => {
    if (!rejecting) return
    try {
      await api(`/registrations/${rejecting.id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) })
      toast.success('Заявку відхилено')
      setRejecting(null)
      setReason('')
      load()
      refreshBadges()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <Panel
      title="Заявки на доступ"
      description="Увійти можна лише після погодження; роль можна змінити перед погодженням"
      actions={
        <div className="flex gap-1 rounded-lg bg-muted p-0.5">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn('rounded-md px-3 py-1 text-xs', filter === f.value ? 'bg-card font-medium shadow-sm' : 'text-muted-foreground')}
            >
              {f.label}
            </button>
          ))}
        </div>
      }
      bodyClassName="p-0"
    >
      {items && items.length === 0 ? (
        <EmptyState icon={Inbox} title={filter === 'pending' ? 'Нових заявок немає' : 'Порожньо'} />
      ) : (
        <ul className="divide-y">
          {(items ?? []).map((r) => (
            <li key={r.id} className="flex flex-wrap items-start gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{r.full_name}</div>
                <div className="text-sm text-muted-foreground">{r.email}</div>
                {r.justification && <p className="mt-1.5 max-w-xl text-sm">{r.justification}</p>}
                <div className="mt-1.5 text-xs text-muted-foreground">
                  подано {dateTime(r.created_at)} · бажана роль: {ROLE_NAMES[r.requested_role]}
                  {r.decided_by_name && ` · розглянув ${r.decided_by_name} ${r.decided_at ? dateTime(r.decided_at) : ''}`}
                </div>
                {r.reject_reason && <p className="mt-1 text-sm text-critical">Причина відхилення: {r.reject_reason}</p>}
              </div>
              {r.status === 'pending' ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Select value={roles[r.id] ?? r.requested_role} onValueChange={(v) => setRoles({ ...roles, [r.id]: v as Role })}>
                    <SelectTrigger className="h-8 w-40" aria-label="Роль">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(ROLE_NAMES) as Role[]).map((role) => (
                        <SelectItem key={role} value={role}>
                          {ROLE_NAMES[role]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button size="sm" onClick={() => approve(r)}>
                    <Check /> Погодити
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setRejecting(r)}>
                    <X /> Відхилити
                  </Button>
                </div>
              ) : (
                <Pill tone={r.status === 'approved' ? 'success' : 'critical'}>{r.status === 'approved' ? 'погоджено' : 'відхилено'}</Pill>
              )}
            </li>
          ))}
        </ul>
      )}

      <Dialog open={!!rejecting} onOpenChange={(o) => !o && setRejecting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-serif text-xl">Відхилити заявку</DialogTitle>
            <DialogDescription>
              {rejecting?.full_name} ({rejecting?.email}). Причина зберігається в журналі аудиту.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="rej">Причина</Label>
            <Textarea id="rej" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} placeholder="Напр.: особу не підтверджено керівником підрозділу" />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejecting(null)}>
              Скасувати
            </Button>
            <Button variant="destructive" disabled={reason.trim().length < 3} onClick={reject}>
              Відхилити
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Panel>
  )
}
