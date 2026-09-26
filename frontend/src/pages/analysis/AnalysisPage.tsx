import { subDays } from 'date-fns'
import { FlaskConical, LoaderCircle, SlidersHorizontal, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { api } from '@/api/client'
import CpvPicker, { type CpvOption } from '@/components/CpvPicker'
import DateRangePicker, { type Range } from '@/components/DateRangePicker'
import { EmptyState, Page, PageHeader, Panel } from '@/components/page'
import { RequestStatusPill } from '@/components/status'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { dateTime, isoDay, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import HomogeneityCard from './HomogeneityCard'
import type { AnalysisRequest, Preview } from './types'

const prefix = (code: string) => code.replace(/0+$/, '').padEnd(2, '0')

export default function AnalysisPage() {
  const navigate = useNavigate()
  const [cpv, setCpv] = useState<CpvOption[]>([])
  const [period, setPeriod] = useState<Range | null>({ from: subDays(new Date(), 29), to: new Date() })
  const [units, setUnits] = useState<string[]>([])
  const [preview, setPreview] = useState<{ key: string; data: Preview } | null>(null)
  const [requests, setRequests] = useState<AnalysisRequest[] | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const load = () => api<AnalysisRequest[]>('/analysis/requests').then(setRequests)
    load()
    const timer = setInterval(load, 4000)
    return () => clearInterval(timer)
  }, [])

  const selection = useMemo(() => {
    if (!cpv.length || !period) return null
    return {
      cpv_prefixes: cpv.map((c) => prefix(c.code)),
      date_from: isoDay(period.from),
      date_to: isoDay(period.to),
      unit_codes: units,
    }
  }, [cpv, period, units])
  const selectionKey = selection ? JSON.stringify(selection) : ''

  // A2.1: оцінка однорідності одразу під час вибору категорій
  useEffect(() => {
    if (!selection) return
    let alive = true
    const t = setTimeout(() => {
      api<Preview>('/analysis/preview', { method: 'POST', body: JSON.stringify(selection) })
        .then((data) => alive && setPreview({ key: selectionKey, data }))
        .catch((e: Error) => alive && toast.error(e.message))
    }, 350)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [selection, selectionKey])

  const current = preview && preview.key === selectionKey ? preview.data : null
  // одиниці для вибору — з останньої оцінки без фільтра одиниць, щоб список не звужувався сам собою
  const [unitOptions, setUnitOptions] = useState<{ code: string; n: number }[]>([])
  if (current && units.length === 0 && current.units !== unitOptions) setUnitOptions(current.units)
  const loadingPreview = !!selection && !current
  const blocked = !current || current.n_items === 0 || current.too_large

  const submit = async () => {
    if (!selection) return
    setSubmitting(true)
    try {
      const r = await api<AnalysisRequest>('/analysis/requests', { method: 'POST', body: JSON.stringify(selection) })
      toast.success(r.from_cache ? 'Результат для цих умов уже є — відкрито одразу' : 'Аналіз запущено')
      navigate(`/analysis/${r.id}`)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Виявлення аномалій"
        title="Нова вибірка для аналізу"
        description="Оберіть товари за класифікатором ДК 021 і період. Чим вужча й однорідніша вибірка, тим точніше система відрізнить аномальну ціну від звичайного розкиду ринку."
      />
      <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <Panel title="Умови вибірки">
          <div className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="cpv">Товари (коди ДК 021)</Label>
              <CpvPicker id="cpv" value={cpv} onChange={setCpv} />
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="period">Період оголошення закупівлі</Label>
                <DateRangePicker id="period" value={period} onChange={setPeriod} />
              </div>
              <div className="space-y-1.5">
                <Label>Одиниці виміру</Label>
                {unitOptions.length === 0 ? (
                  <div className="flex h-9 items-center text-sm text-muted-foreground">усі — з'являться після вибору товарів</div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {unitOptions.map((u) => {
                      const on = units.includes(u.code)
                      return (
                        <button
                          key={u.code}
                          type="button"
                          aria-pressed={on}
                          onClick={() => setUnits(on ? units.filter((x) => x !== u.code) : [...units, u.code])}
                          className={cn(
                            'rounded-md border px-2 py-1 text-xs transition-colors',
                            on ? 'border-primary bg-primary/10 text-foreground' : 'text-muted-foreground hover:bg-accent/60',
                          )}
                        >
                          <span className="font-mono">{u.code}</span> <span className="tabular opacity-70">{u.n.toLocaleString('uk-UA')}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t pt-5">
              <Button size="lg" disabled={blocked || submitting} onClick={submit}>
                {submitting ? <LoaderCircle className="animate-spin" /> : <FlaskConical />}
                Знайти аномальні ціни
              </Button>
              <span className="text-xs text-muted-foreground">
                {current?.too_large
                  ? 'Вибірка завелика — звузьте період або коди'
                  : current?.n_items === 0
                    ? 'За цими умовами немає позицій з ціною'
                    : 'Зазвичай займає до хвилини; повторний запит з тими самими умовами — миттєво'}
              </span>
            </div>
          </div>
        </Panel>

        <Panel title="Оцінка вибірки" actions={loadingPreview ? <LoaderCircle className="size-4 animate-spin text-muted-foreground" /> : undefined}>
          {!selection ? (
            <EmptyState icon={SlidersHorizontal} title="Оберіть товари й період">
              Одразу покажемо, наскільки порівнянні ціни у вибірці.
            </EmptyState>
          ) : current ? (
            <HomogeneityCard h={current.homogeneity} nItems={current.n_items} />
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-5">
                <Skeleton className="size-28 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-6 w-32" />
                </div>
              </div>
              <Skeleton className="h-12" />
              <Skeleton className="h-20" />
            </div>
          )}
        </Panel>
      </div>

      <Panel className="mt-4" title="Мої аналізи" bodyClassName="p-0">
        {requests === null ? (
          <div className="space-y-2 p-5">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : requests.length === 0 ? (
          <EmptyState icon={Sparkles} title="Ще жодного аналізу">
            Перший результат з'явиться тут.
          </EmptyState>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16 pl-5">№</TableHead>
                <TableHead>ДК 021</TableHead>
                <TableHead>Період</TableHead>
                <TableHead className="text-right">Однорідність</TableHead>
                <TableHead>Стан</TableHead>
                <TableHead className="pr-5 text-right">Створено</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {requests.map((r) => (
                <TableRow key={r.id} className="cursor-pointer" onClick={() => navigate(`/analysis/${r.id}`)}>
                  <TableCell className="pl-5 font-mono text-xs text-muted-foreground">{r.id}</TableCell>
                  <TableCell className="font-medium">{r.cpv_prefixes.join(', ')}</TableCell>
                  <TableCell className="tabular">
                    {shortDate(r.date_from)} – {shortDate(r.date_to)}
                  </TableCell>
                  <TableCell className="text-right tabular">{r.homogeneity == null ? '—' : `${Math.round(r.homogeneity * 100)}`}</TableCell>
                  <TableCell>
                    <span className="flex items-center gap-1.5">
                      <RequestStatusPill status={r.status} />
                      {r.from_cache && <span className="text-xs text-muted-foreground">готовий результат</span>}
                    </span>
                  </TableCell>
                  <TableCell className="pr-5 text-right text-muted-foreground tabular">{dateTime(r.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </Page>
  )
}
