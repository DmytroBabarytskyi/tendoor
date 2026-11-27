import { ChevronRight, ScanSearch } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { EmptyState, Page, PageHeader, Panel } from '@/components/page'
import Pagination from '@/components/Pagination'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { dateTime, money, shortDate, unitShort } from '@/lib/format'
import { cn } from '@/lib/utils'
import ItemDrawer from './ItemDrawer'
import VerdictPill, { StatePill } from './VerdictPill'
import { useBadges } from '@/layout/badges'
import { VERDICT_REASON, VERDICT_STATUS, type Verdict, type VerdictReason, type VerdictStatus } from './verdicts'

const PAGE = 20
const ALL = '__all'

type Queue = 'review' | 'mine' | 'all'
const QUEUES: { value: Queue; label: string }[] = [
  { value: 'review', label: 'На погодженні' },
  { value: 'mine', label: 'Мої' },
  { value: 'all', label: 'Усі' },
]

/** A3: черги перевірок — чужі висновки на погодженні, мої незавершені, історія з фільтрами. */
export default function ChecksPage() {
  const [status, setStatus] = useState<VerdictStatus | undefined>()
  const [reason, setReason] = useState<VerdictReason | undefined>()
  const [mine, setMine] = useState(false)
  const [queue, setQueue] = useState<Queue>('review')
  const badges = useBadges()
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<{ key: string; total: number; items: Verdict[] } | null>(null)
  const [opened, setOpened] = useState<number | null>(null)
  const key = `${queue}|${status}|${reason}|${mine}|${page}|${reload}`

  useEffect(() => {
    let alive = true
    const p = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE), mine: String(mine) })
    if (queue !== 'all') p.set('queue', queue)
    if (status) p.set('status_', status)
    if (reason) p.set('reason', reason)
    api<{ total: number; items: Verdict[] }>(`/verdicts?${p}`).then((r) => alive && setData({ key, ...r }))
    return () => {
      alive = false
    }
  }, [queue, status, reason, mine, page, key])

  const items = data?.items ?? []
  const idx = items.findIndex((v) => v.item_id === opened)
  return (
    <Page>
      <PageHeader
        eyebrow="Аудит"
        title="Перевірки"
        description="Кожен висновок погоджує інший аудитор. Відкрийте рядок, щоб розглянути позицію, погодити чи повернути висновок."
      />
      <div className="mb-4 flex gap-1 border-b">
        {QUEUES.map((q) => {
          const n = q.value === 'review' ? badges?.to_review : q.value === 'mine' ? (badges?.in_work ?? 0) + (badges?.my_submitted ?? 0) : 0
          return (
            <button
              key={q.value}
              onClick={() => {
                setQueue(q.value)
                setPage(1)
              }}
              className={cn(
                '-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm',
                queue === q.value ? 'border-primary font-medium' : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {q.label}
              {!!n && <span className="rounded-full bg-primary px-1.5 text-[11px] leading-5 font-semibold text-primary-foreground tabular">{n}</span>}
            </button>
          )
        })}
      </div>
      <Panel
        bodyClassName="p-0"
        title={
          <div className="flex flex-wrap items-center gap-2">
            <Select value={status ?? ALL} onValueChange={(v) => { setStatus(v === ALL ? undefined : (v as VerdictStatus)); setPage(1) }}>
              <SelectTrigger className="h-8 w-52"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Усі висновки</SelectItem>
                {(Object.keys(VERDICT_STATUS) as VerdictStatus[]).map((s) => (
                  <SelectItem key={s} value={s}>{VERDICT_STATUS[s].label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={reason ?? ALL} onValueChange={(v) => { setReason(v === ALL ? undefined : (v as VerdictReason)); setPage(1) }}>
              <SelectTrigger className="h-8 w-56"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Усі причини</SelectItem>
                {(Object.keys(VERDICT_REASON) as VerdictReason[]).map((r) => (
                  <SelectItem key={r} value={r}>{VERDICT_REASON[r]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <label className="ml-1 flex cursor-pointer items-center gap-2 text-sm font-normal">
              <Switch checked={mine} onCheckedChange={(v) => { setMine(v); setPage(1) }} /> лише мої
            </label>
          </div>
        }
      >
        {data && items.length === 0 ? (
          <EmptyState icon={ScanSearch} title={queue === 'review' ? 'Немає висновків, що чекають вашого погодження' : 'Перевірок не знайдено'}>{queue === 'mine' ? 'Візьміть позиції в роботу з результатів аналізу.' : 'Змініть фільтри або розгляньте позиції в результатах аналізу.'}</EmptyState>
        ) : (
          <div className={cn('transition-opacity', data?.key !== key && 'opacity-60')}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-5">Змінено</TableHead>
                  <TableHead>Висновок і стан</TableHead>
                  <TableHead>Причина</TableHead>
                  <TableHead>Предмет</TableHead>
                  <TableHead className="text-right">Ціна</TableHead>
                  <TableHead>Замовник</TableHead>
                  <TableHead>Аудитор</TableHead>
                  <TableHead className="w-10 pr-5">
                    <span className="sr-only">Дія</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((v) => (
                  <TableRow key={v.id} className={cn('cursor-pointer', opened === v.item_id && 'bg-accent/60')} onClick={() => setOpened(v.item_id)}>
                    <TableCell className="pl-5 text-muted-foreground tabular">
                      <div className="whitespace-nowrap">{shortDate(v.updated_at)}</div>
                      <div className="text-xs">{dateTime(v.updated_at).slice(11)}</div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <VerdictPill status={v.status} />
                        <StatePill state={v.state} />
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[140px]">{v.reason ? VERDICT_REASON[v.reason] : '—'}</TableCell>
                    <TableCell className="max-w-[200px]"><span className="line-clamp-2">{v.description}</span></TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular">{money(v.unit_price_base)} грн/{unitShort(v.base_unit_code)}</TableCell>
                    <TableCell className="max-w-[170px]"><span className="line-clamp-2" title={v.entity_name}>{v.entity_name}</span></TableCell>
                    <TableCell className="max-w-[120px]"><span className="line-clamp-2">{v.user_name}</span></TableCell>
                    <TableCell className="pr-5 text-muted-foreground" title="Розглянути позицію">
                      <ChevronRight className="size-4" aria-hidden />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        <div className="border-t px-5 pb-3">
          <Pagination page={page} pageSize={PAGE} total={data?.total ?? 0} onChange={setPage} />
        </div>
      </Panel>
      <ItemDrawer
        itemId={opened}
        onClose={() => setOpened(null)}
        onSaved={() => setReload((n) => n + 1)}
        onNext={idx >= 0 && idx < items.length - 1 ? () => setOpened(items[idx + 1].item_id) : undefined}
        onPrev={idx > 0 ? () => setOpened(items[idx - 1].item_id) : undefined}
        position={idx >= 0 ? { index: (page - 1) * PAGE + idx + 1, total: data?.total ?? items.length } : undefined}
      />
    </Page>
  )
}
