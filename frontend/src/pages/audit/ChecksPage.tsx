import { ScanSearch } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { EmptyState, Page, PageHeader, Panel } from '@/components/page'
import Pagination from '@/components/Pagination'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { dateTime, money } from '@/lib/format'
import { cn } from '@/lib/utils'
import ItemDrawer from './ItemDrawer'
import VerdictPill from './VerdictPill'
import { VERDICT_REASON, VERDICT_STATUS, type Verdict, type VerdictReason, type VerdictStatus } from './verdicts'

const PAGE = 20
const ALL = '__all'

/** A3.3: історія перевірок — усі вердикти з фільтрами. */
export default function ChecksPage() {
  const [status, setStatus] = useState<VerdictStatus | undefined>()
  const [reason, setReason] = useState<VerdictReason | undefined>()
  const [mine, setMine] = useState(false)
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<{ key: string; total: number; items: Verdict[] } | null>(null)
  const [opened, setOpened] = useState<number | null>(null)
  const key = `${status}|${reason}|${mine}|${page}|${reload}`

  useEffect(() => {
    let alive = true
    const p = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE), mine: String(mine) })
    if (status) p.set('status_', status)
    if (reason) p.set('reason', reason)
    api<{ total: number; items: Verdict[] }>(`/verdicts?${p}`).then((r) => alive && setData({ key, ...r }))
    return () => {
      alive = false
    }
  }, [status, reason, mine, page, key])

  const items = data?.items ?? []
  const idx = items.findIndex((v) => v.item_id === opened)
  return (
    <Page>
      <PageHeader eyebrow="Аудит" title="Історія перевірок" description="Усі винесені вердикти. Відкрийте рядок, щоб переглянути позицію чи змінити висновок." />
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
          <EmptyState icon={ScanSearch} title="Вердиктів не знайдено">Змініть фільтри або розгляньте позиції в результатах аналізу.</EmptyState>
        ) : (
          <div className={cn('transition-opacity', data?.key !== key && 'opacity-60')}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-5">Змінено</TableHead>
                  <TableHead>Висновок</TableHead>
                  <TableHead>Причина</TableHead>
                  <TableHead>Предмет</TableHead>
                  <TableHead className="text-right">Ціна</TableHead>
                  <TableHead>Замовник</TableHead>
                  <TableHead className="pr-5">Аудитор</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((v) => (
                  <TableRow key={v.id} className={cn('cursor-pointer', opened === v.item_id && 'bg-accent/60')} onClick={() => setOpened(v.item_id)}>
                    <TableCell className="pl-5 whitespace-nowrap text-muted-foreground tabular">{dateTime(v.updated_at)}</TableCell>
                    <TableCell><VerdictPill status={v.status} /></TableCell>
                    <TableCell className="whitespace-nowrap">{VERDICT_REASON[v.reason]}</TableCell>
                    <TableCell className="max-w-[300px]"><span className="line-clamp-2">{v.description}</span></TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular">{money(v.unit_price_base)} грн/{v.base_unit_code}</TableCell>
                    <TableCell className="max-w-[220px] truncate">{v.entity_name}</TableCell>
                    <TableCell className="max-w-[180px] truncate pr-5">{v.user_name}</TableCell>
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
      />
    </Page>
  )
}
