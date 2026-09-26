import { subDays } from 'date-fns'
import { CloudDownload, LoaderCircle, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import DateRangePicker, { type Range } from '@/components/DateRangePicker'
import { EmptyState, Page, PageHeader, Panel } from '@/components/page'
import { Pill } from '@/components/status'
import { REQUEST_STATUS, type RequestStatus } from '@/components/status-meta'
import TagsInput from '@/components/TagsInput'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { date, int, isoDay } from '@/lib/format'
import { cn } from '@/lib/utils'

type Job = {
  id: number
  status: RequestStatus
  date_from: string
  date_to: string
  cpv_prefixes: string[]
  categories: string[]
  scanned: number
  saved: number
  normalized: number
  errors: number
  message: string | null
  created_at: string
  finished_at: string | null
}

const STATUS_LABEL: Record<RequestStatus, string> = { queued: 'у черзі', running: 'виконується', done: 'завершено', failed: 'помилка' }
const CATEGORIES = [
  { value: 'goods', label: 'Товари' },
  { value: 'services', label: 'Послуги' },
  { value: 'works', label: 'Роботи' },
]
// приблизно 25 тис. змін у фіді Prozorro за добу — для оцінки прогресу
const FEED_PER_DAY = 25000
const DAY_MS = 86_400_000

export default function SyncPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [period, setPeriod] = useState<Range | null>({ from: subDays(new Date(), 1), to: subDays(new Date(), 1) })
  const [cpv, setCpv] = useState<string[]>([])
  const [categories, setCategories] = useState<string[]>(['goods'])
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(() => {
    api<Job[]>('/sync/jobs').then(setJobs)
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [load])

  const submit = async () => {
    if (!period) return
    setSubmitting(true)
    try {
      await api('/sync/jobs', {
        method: 'POST',
        body: JSON.stringify({ date_from: isoDay(period.from), date_to: isoDay(period.to), cpv_prefixes: cpv, categories }),
      })
      toast.success('Завдання поставлено в чергу')
      load()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const days = period ? Math.round((period.to.getTime() - period.from.getTime()) / DAY_MS) + 1 : 0
  return (
    <Page>
      <PageHeader
        eyebrow="Дані"
        title="Синхронізація з Prozorro"
        description="Завантаження змінених закупівель з відкритого API Prozorro. Документи зберігаються без змін, а позиції з цінами нормалізуються для аналізу."
      />
      <Panel title="Нове завантаження">
        <div className="grid items-end gap-5 lg:grid-cols-[1.1fr_1fr_1fr_auto]">
          <div className="space-y-1.5">
            <Label htmlFor="sync-period">Період змін у Prozorro</Label>
            <DateRangePicker id="sync-period" value={period} onChange={setPeriod} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sync-cpv">Коди ДК 021 (префікси)</Label>
            <TagsInput id="sync-cpv" value={cpv} onChange={setCpv} placeholder="усі; напр. 15, 0322" validate={(s) => /^\d{2,8}$/.test(s)} />
          </div>
          <div className="space-y-1.5">
            <Label>Предмет закупівлі</Label>
            <div className="flex gap-1.5">
              {CATEGORIES.map((c) => {
                const on = categories.includes(c.value)
                return (
                  <button
                    key={c.value}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setCategories(on ? categories.filter((x) => x !== c.value) : [...categories, c.value])}
                    className={cn(
                      'h-9 flex-1 rounded-md border px-3 text-sm transition-colors',
                      on ? 'border-primary bg-primary/10' : 'text-muted-foreground hover:bg-accent/60',
                    )}
                  >
                    {c.label}
                  </button>
                )
              })}
            </div>
          </div>
          <Button onClick={submit} disabled={!period || submitting}>
            {submitting ? <LoaderCircle className="animate-spin" /> : <CloudDownload />}
            Запустити
          </Button>
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          Одна доба — близько 25 тис. змін і ~10 хвилин обробки
          {days > 1 && ` · обраний період: ${days} діб, орієнтовно ${Math.round(days * 10)} хв`}. Перерване завдання продовжиться з того
          ж місця.
        </p>
      </Panel>

      <Panel className="mt-4" title="Завдання" bodyClassName="p-0" actions={<RefreshCw className="size-4 text-muted-foreground" aria-label="оновлюється автоматично" />}>
        {jobs && jobs.length === 0 ? (
          <EmptyState icon={CloudDownload} title="Ще не було завантажень" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-14 pl-5">№</TableHead>
                <TableHead>Період</TableHead>
                <TableHead>ДК 021</TableHead>
                <TableHead>Стан</TableHead>
                <TableHead className="w-56">Прогрес</TableHead>
                <TableHead className="text-right">Переглянуто</TableHead>
                <TableHead className="text-right">Збережено</TableHead>
                <TableHead className="pr-5 text-right">Помилок</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(jobs ?? []).map((j) => {
                const d = Math.round((Date.parse(j.date_to) - Date.parse(j.date_from)) / DAY_MS) + 1
                const pctDone = j.status === 'done' ? 100 : Math.min(99, Math.round((100 * j.scanned) / (d * FEED_PER_DAY)))
                const s = REQUEST_STATUS[j.status]
                return (
                  <TableRow key={j.id}>
                    <TableCell className="pl-5 font-mono text-xs text-muted-foreground">{j.id}</TableCell>
                    <TableCell className="whitespace-nowrap tabular">
                      {date(j.date_from)} – {date(j.date_to)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{j.cpv_prefixes.length ? j.cpv_prefixes.join(', ') : 'усі'}</TableCell>
                    <TableCell>
                      {j.message ? (
                        <Tooltip>
                          <TooltipTrigger>
                            <Pill tone={s.tone} icon={s.icon} spin={s.spin}>{STATUS_LABEL[j.status]}</Pill>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-sm">{j.message}</TooltipContent>
                        </Tooltip>
                      ) : (
                        <Pill tone={s.tone} icon={s.icon} spin={s.spin}>{STATUS_LABEL[j.status]}</Pill>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={pctDone} className={cn('h-1.5', j.status === 'failed' && '[&>div]:bg-critical')} />
                        <span className="w-9 text-right text-xs tabular text-muted-foreground">{pctDone}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular">{int(j.scanned)}</TableCell>
                    <TableCell className="text-right tabular">{int(j.saved)}</TableCell>
                    <TableCell className={cn('pr-5 text-right tabular', j.errors > 0 && 'text-warning')}>{int(j.errors)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </Panel>
    </Page>
  )
}
