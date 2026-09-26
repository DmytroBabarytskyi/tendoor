import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { Page, PageHeader, Panel } from '@/components/page'
import Pagination from '@/components/Pagination'
import { Pill } from '@/components/status'
import type { Tone } from '@/components/status-meta'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { dateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

type Entry = {
  id: number
  user_email: string | null
  action: string
  entity: string
  entity_key: string | null
  payload: Record<string, unknown> | null
  ip: string | null
  created_at: string
}

const ACTIONS: Record<string, { tone: Tone; label: string }> = {
  LOGIN: { tone: 'success', label: 'вхід' },
  LOGOUT: { tone: 'neutral', label: 'вихід' },
  LOGIN_FAILED: { tone: 'critical', label: 'невдалий вхід' },
  INSERT: { tone: 'info', label: 'створення' },
  UPDATE: { tone: 'warning', label: 'зміна' },
  DELETE: { tone: 'critical', label: 'видалення' },
}
const PAGE = 25
const ALL = '__all'

export default function AuditPage() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState<string | undefined>()
  const [data, setData] = useState<{ key: string; total: number; items: Entry[] } | null>(null)
  const key = `${page}|${action ?? ''}`

  useEffect(() => {
    let alive = true
    const params = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE) })
    if (action) params.set('action', action)
    api<{ total: number; items: Entry[] }>(`/audit-log?${params}`).then((r) => alive && setData({ key, ...r }))
    return () => {
      alive = false
    }
  }, [page, action, key])

  return (
    <Page>
      <PageHeader
        eyebrow="Адміністрування"
        title="Журнал аудиту"
        description="Входи, зміни користувачів, параметрів і вердиктів. Записи створюють тригери бази даних — їх не можна обійти з інтерфейсу."
        actions={
          <Select value={action ?? ALL} onValueChange={(v) => { setAction(v === ALL ? undefined : v); setPage(1) }}>
            <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Усі дії</SelectItem>
              {Object.entries(ACTIONS).map(([k, a]) => (
                <SelectItem key={k} value={k}>{a.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />
      <Panel bodyClassName="p-0">
        <div className={cn('transition-opacity', data?.key !== key && 'opacity-60')}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-5">Час</TableHead>
                <TableHead>Користувач</TableHead>
                <TableHead>Дія</TableHead>
                <TableHead>Об'єкт</TableHead>
                <TableHead>Зміни</TableHead>
                <TableHead className="pr-5">IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.items ?? []).map((e) => {
                const a = ACTIONS[e.action] ?? { tone: 'neutral' as Tone, label: e.action }
                return (
                  <TableRow key={e.id}>
                    <TableCell className="pl-5 whitespace-nowrap text-muted-foreground tabular">{dateTime(e.created_at)}</TableCell>
                    <TableCell className="max-w-[220px] truncate">{e.user_email ?? <span className="text-muted-foreground">система</span>}</TableCell>
                    <TableCell><Pill tone={a.tone}>{a.label}</Pill></TableCell>
                    <TableCell className="font-mono text-xs whitespace-nowrap">
                      {e.entity}{e.entity_key ? ` #${e.entity_key}` : ''}
                    </TableCell>
                    <TableCell className="max-w-[420px]">
                      {e.payload && (
                        <code className="line-clamp-2 font-mono text-[11px] break-all text-muted-foreground" title={JSON.stringify(e.payload, null, 2)}>
                          {JSON.stringify(e.payload)}
                        </code>
                      )}
                    </TableCell>
                    <TableCell className="pr-5 font-mono text-xs text-muted-foreground">{e.ip}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
        <div className="border-t px-5 pb-3">
          <Pagination page={page} pageSize={PAGE} total={data?.total ?? 0} onChange={setPage} />
        </div>
      </Panel>
    </Page>
  )
}
