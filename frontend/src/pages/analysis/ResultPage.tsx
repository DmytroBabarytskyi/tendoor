import { motion } from 'motion/react'
import { ArrowLeft, Archive, Download, ExternalLink, LoaderCircle, OctagonX, RotateCw, Search, SearchX } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { api, download } from '@/api/client'
import BarList from '@/components/BarList'
import Chart from '@/components/Chart'
import { EmptyState, Kbd, Page, PageHeader, Panel } from '@/components/page'
import Pagination from '@/components/Pagination'
import StatTile from '@/components/StatTile'
import { DataErrorPill, RequestStatusPill, RiskMeter } from '@/components/status'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { date, groupName, money, pct, ratio, unitShort } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useTheme } from '@/theme/context'
import ItemDrawer from '../audit/ItemDrawer'
import VerdictPill from '../audit/VerdictPill'
import { pcaOption, priceVolumeOption, type Point } from './charts'
import HomogeneityCard from './HomogeneityCard'
import type { AnalysisRequest, AnomalyRow, Category } from './types'
import InfoHint from '@/components/InfoHint'

const PAGE = 20

type Signal = 'flagged' | 'risk' | 'data_error'

function Training() {
  return (
    <Panel>
      <div className="flex flex-col items-center gap-4 py-10 text-center">
        <div className="relative size-16">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="absolute inset-0 rounded-full border-2 border-primary/50"
              initial={{ scale: 0.4, opacity: 0.9 }}
              animate={{ scale: 1.4, opacity: 0 }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.66, ease: 'easeOut' }}
            />
          ))}
          <LoaderCircle className="absolute inset-0 m-auto size-7 animate-spin text-primary" />
        </div>
        <div>
          <div className="font-serif text-xl font-semibold">Система вивчає ціни у вибірці</div>
          <p className="mt-1 text-sm text-muted-foreground">
            Групує однорідні товари, оцінює розкид цін і відбирає підозрілі — зазвичай до хвилини. Сторінку можна не оновлювати.
          </p>
        </div>
      </div>
    </Panel>
  )
}

export default function ResultPage() {
  const { id } = useParams()
  const { resolved } = useTheme()
  const navigate = useNavigate()
  const [rerunning, setRerunning] = useState(false)
  const [req, setReq] = useState<AnalysisRequest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cats, setCats] = useState<Category[]>([])
  const [catId, setCatId] = useState<number | null>(null)
  const [catQuery, setCatQuery] = useState('')
  const [points, setPoints] = useState<{ cat: number; data: Point[] } | null>(null)
  const [view, setView] = useState<'price' | 'pca'>('price')
  const [signal, setSignal] = useState<Signal>('flagged')
  const [page, setPage] = useState(1)
  const [onlyGroup, setOnlyGroup] = useState(false)
  const [rows, setRows] = useState<{ key: string; total: number; items: AnomalyRow[] } | null>(null)
  const [opened, setOpened] = useState<number | null>(null)
  const [reloadRows, setReloadRows] = useState(0)
  const [downloading, setDownloading] = useState(false)

  // поки модель навчається — опитування статусу
  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const load = () =>
      api<AnalysisRequest>(`/analysis/requests/${id}`).then(
        (r) => {
          if (!alive) return
          setReq(r)
          if (r.status === 'queued' || r.status === 'running') timer = setTimeout(load, 2000)
        },
        (e: Error) => alive && setError(e.message),
      )
    load()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [id])

  const done = req?.status === 'done'

  useEffect(() => {
    if (!done) return
    api<Category[]>(`/analysis/requests/${id}/categories`).then((c) => {
      setCats(c)
      const first = c.filter((x) => x.analysed).sort((a, b) => b.n_anomalies - a.n_anomalies)[0]
      setCatId(first?.id ?? null)
    })
  }, [done, id])

  useEffect(() => {
    if (!done || catId == null) return
    let alive = true
    api<Point[]>(`/analysis/requests/${id}/points?category_id=${catId}`).then((d) => alive && setPoints({ cat: catId, data: d }))
    return () => {
      alive = false
    }
  }, [done, id, catId])

  const rowsKey = `${page}|${onlyGroup ? catId : ''}|${signal}|${reloadRows}`
  useEffect(() => {
    if (!done) return
    let alive = true
    const params = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE), signal })
    if (onlyGroup && catId != null) params.set('category_id', String(catId))
    api<{ total: number; items: AnomalyRow[] }>(`/analysis/requests/${id}/anomalies?${params}`).then((r) => alive && setRows({ key: rowsKey, ...r }))
    return () => {
      alive = false
    }
  }, [done, id, page, rowsKey, onlyGroup, catId, signal])

  const cat = cats.find((c) => c.id === catId)
  const option = useMemo(() => {
    if (!cat || !points || points.cat !== cat.id) return null
    void resolved // перебудувати кольори діаграми після зміни теми
    return view === 'price' ? priceVolumeOption(points.data, unitShort(cat.base_unit_code), cat.median_price ?? undefined) : pcaOption(points.data, unitShort(cat.base_unit_code))
  }, [cat, points, view, resolved])

  const groups = useMemo(() => {
    const q = catQuery.trim().toLowerCase()
    return cats
      .filter((c) => c.analysed)
      .filter((c) => !q || c.top_terms.join(' ').toLowerCase().includes(q) || (c.cpv_code ?? '').startsWith(q))
      .sort((a, b) => b.n_anomalies - a.n_anomalies || b.size - a.size)
  }, [cats, catQuery])

  if (error) return <EmptyState icon={SearchX} title={error} className="min-h-[50vh]" />
  if (!req)
    return (
      <Page>
        <Skeleton className="mb-6 h-10 w-96" />
        <Skeleton className="h-64" />
      </Page>
    )

  const m = req.run?.metrics
  const items = rows?.items ?? []
  const idx = items.findIndex((r) => r.item_id === opened)
  return (
    <Page>
      <Link to="/analysis" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> До вибірки
      </Link>
      <PageHeader
        eyebrow={`Аналіз №${req.id}`}
        title={`ДК 021: ${req.cpv_prefixes.join(', ')}`}
        description={
          <>
            Закупівлі, оголошені {date(req.date_from)} – {date(req.date_to)}
            {req.unit_codes.length > 0 && `, одиниці ${req.unit_codes.join(', ')}`}
            {req.from_cache && ' · результат для цих умов уже був — показано без повторного розрахунку'}
          </>
        }
        actions={
          <>
            <RequestStatusPill status={req.status} />
            {done && (
              <Button
                variant="outline"
                disabled={downloading}
                onClick={() => {
                  setDownloading(true)
                  download(`/analysis/requests/${req.id}/report.xlsx`, `tendoor-analysis-${req.id}.xlsx`)
                    .catch((e: Error) => toast.error(e.message))
                    .finally(() => setDownloading(false))
                }}
              >
                {downloading ? <LoaderCircle className="animate-spin" /> : <Download />}
                Звіт XLSX
              </Button>
            )}
          </>
        }
      />

      {(req.status === 'queued' || req.status === 'running') && <Training />}
      {req.status === 'failed' && (
        <div className="flex items-start gap-3 rounded-xl border border-critical/30 bg-critical-soft p-4 text-sm text-critical">
          <OctagonX className="mt-0.5 size-4 shrink-0" />
          <div>
            <div className="font-medium">Аналіз завершився помилкою</div>
            <div className="mt-1 opacity-90">{req.message}</div>
          </div>
        </div>
      )}

      {done && !req.run && (
        <Panel>
          <EmptyState icon={Archive} title="Результат більше не зберігається">
            {req.message ?? 'Дані цього аналізу видалено за терміном зберігання.'}
            <div className="mt-4">
              <Button
                disabled={rerunning}
                onClick={async () => {
                  setRerunning(true)
                  try {
                    const r = await api<AnalysisRequest>('/analysis/requests', {
                      method: 'POST',
                      body: JSON.stringify({
                        cpv_prefixes: req.cpv_prefixes,
                        date_from: req.date_from,
                        date_to: req.date_to,
                        unit_codes: req.unit_codes,
                        params: req.params ?? {},
                      }),
                    })
                    navigate(`/analysis/${r.id}`)
                  } catch (e) {
                    toast.error((e as Error).message)
                  } finally {
                    setRerunning(false)
                  }
                }}
              >
                {rerunning ? <LoaderCircle className="animate-spin" /> : <RotateCw />}
                Повторити аналіз з тими самими умовами
              </Button>
            </div>
          </EmptyState>
        </Panel>
      )}

      {done && m && (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatTile label="Проаналізовано позицій" value={m.n_analysed} hint={`з ${m.n_items.toLocaleString('uk-UA')} у вибірці`} />
            <StatTile label="Високий ризик" value={m.n_anomalies} hint={`${pct(m.anomaly_share, 1)} проаналізованих`} />
            <StatTile label="Ймовірні помилки даних" value={m.n_extreme} hint="ціна далеко поза межами групи" />
            <StatTile
              label={
                <>
                  Однорідних груп
                  <InfoHint>Групи схожих товарів (за кодом ДК 021 і текстом опису), всередині яких ціни можна порівнювати між собою.</InfoHint>
                </>
              } value={m.n_groups} hint={`розрахунок ${Math.round(m.seconds)} с`} />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(320px,2fr)_3fr]">
            <Panel
              title="Групи порівнюваних товарів"
              description="Ціни порівнюються лише всередині групи"
              bodyClassName="p-0"
            >
              <div className="border-b p-3">
                <div className="relative">
                  <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
                  <Input value={catQuery} onChange={(e) => setCatQuery(e.target.value)} placeholder="Пошук групи або коду" className="pl-8" />
                </div>
              </div>
              <ul className="max-h-[420px] overflow-y-auto p-1.5">
                {groups.map((c) => (
                  <li key={c.id}>
                    <button
                      onClick={() => setCatId(c.id)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors',
                        c.id === catId ? 'bg-accent' : 'hover:bg-accent/50',
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{groupName(c.top_terms)}</span>
                        <span className="block text-xs text-muted-foreground">
                          <span className="font-mono">{c.cpv_code}</span> · медіана {money(c.median_price)} грн/{unitShort(c.base_unit_code)}
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-xs tabular">
                        <span className={cn('block font-semibold', c.n_anomalies ? 'text-critical' : 'text-muted-foreground')}>
                          {c.n_anomalies} аном.
                        </span>
                        <span className="block text-muted-foreground">{c.size} поз.</span>
                      </span>
                    </button>
                  </li>
                ))}
                {groups.length === 0 && <li className="p-6 text-center text-sm text-muted-foreground">Нічого не знайдено</li>}
              </ul>
            </Panel>
            <Panel
              title={cat ? groupName(cat.top_terms) : 'Група'}
              description={cat ? `${cat.size} позицій · ${cat.n_anomalies} аномальних · ▲ аномалія, ● звичайна ціна` : undefined}
              actions={
                <ToggleGroup type="single" variant="outline" size="sm" value={view} onValueChange={(v) => v && setView(v as 'price' | 'pca')}>
                  <ToggleGroupItem value="price">Ціна × обсяг</ToggleGroupItem>
                  <ToggleGroupItem value="pca" title="Карта схожості позицій: близькі точки мають схожі ціну, обсяг, дату й опис; віддалені точки – нетипові">
                    Простір ознак
                  </ToggleGroupItem>
                </ToggleGroup>
              }
            >
              {option ? <Chart option={option} height={400} /> : <Skeleton className="h-[400px]" />}
            </Panel>
          </div>

          <Panel
            className="mt-4"
            title="Позиції для перевірки"
            description="Два сигнали: високий ризик і ймовірна помилка даних (одиниця, фасовка, сума лоту замість ціни). Натисніть рядок, щоб розглянути позицію й винести вердикт."
            actions={
              <div className="flex flex-wrap items-center gap-4">
              <ToggleGroup
                type="single"
                variant="outline"
                size="sm"
                value={signal}
                onValueChange={(v) => {
                  if (!v) return
                  setSignal(v as Signal)
                  setPage(1)
                }}
              >
                <ToggleGroupItem value="flagged">Усі</ToggleGroupItem>
                <ToggleGroupItem value="risk">Високий ризик</ToggleGroupItem>
                <ToggleGroupItem value="data_error">Помилки даних</ToggleGroupItem>
              </ToggleGroup>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <Switch
                  checked={onlyGroup}
                  onCheckedChange={(v) => {
                    setOnlyGroup(v)
                    setPage(1)
                  }}
                />
                лише обрана група
              </label>
              </div>
            }
            bodyClassName="p-0"
          >
            <div className={cn('transition-opacity', rows?.key !== rowsKey && 'opacity-60')}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-32 pl-5">
                      Ризик
                      <InfoHint>Оцінка 0–100: наскільки ймовірно, що аудитор підтвердить аномалію. 80+ – високий, 50–79 – середній. Позиції з однаковою оцінкою впорядковано за силою відхилення ціни.</InfoHint>
                    </TableHead>
                    <TableHead className="text-right">Ціна</TableHead>
                    <TableHead>Відхилення</TableHead>
                    <TableHead>Предмет закупівлі</TableHead>
                    <TableHead>Вердикт</TableHead>
                    <TableHead className="pr-5">Замовник · закупівля</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((r) => (
                    <TableRow
                      key={r.result_id}
                      className={cn('cursor-pointer', opened === r.item_id && 'bg-accent/60')}
                      onClick={() => setOpened(r.item_id)}
                    >
                      <TableCell className="pl-5">
                        <div className="flex flex-col items-start gap-1">
                          <RiskMeter risk={r.risk_score} />
                          {r.is_extreme && <DataErrorPill />}
                        </div>
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular">
                        {r.pack_size ? (
                          <Tooltip>
                            <TooltipTrigger className="underline decoration-dotted underline-offset-4">
                              {money(r.model_price ?? r.unit_price_base)} грн/{r.model_unit}
                            </TooltipTrigger>
                            <TooltipContent>
                              Перераховано з фасовки {r.pack_size}: у документі {money(r.unit_price_base)} грн/{unitShort(r.base_unit_code)}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          `${money(r.model_price ?? r.unit_price_base)} грн/${unitShort(r.model_unit ?? r.base_unit_code)}`
                        )}
                      </TableCell>
                      <TableCell
                        className={cn('whitespace-nowrap tabular', r.price_ratio != null && (r.price_ratio >= 1 ? 'text-critical' : 'text-warning'))}
                      >
                        {ratio(r.price_ratio)}
                      </TableCell>
                      <TableCell className="max-w-[260px]">
                        <span className="line-clamp-2">{r.description}</span>
                      </TableCell>
                      <TableCell>
                        <VerdictPill status={r.verdict_status} state={r.verdict_state} />
                      </TableCell>
                      <TableCell className="max-w-[220px] pr-5">
                        <span className="line-clamp-2" title={r.entity_name}>{r.entity_name}</span>
                        <a
                          href={`https://prozorro.gov.ua/tender/${r.tender_code}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-primary"
                        >
                          {r.tender_code} <ExternalLink className="size-3" />
                        </a>
                      </TableCell>
                    </TableRow>
                  ))}
                  {rows && items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                        У цій групі аномальних цін не знайдено
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t px-5 pb-3">
              <span className="pt-3 text-xs text-muted-foreground">
                У картці: <Kbd>J</Kbd> / <Kbd>K</Kbd> — наступна / попередня позиція
              </span>
              <Pagination page={page} pageSize={PAGE} total={rows?.total ?? 0} onChange={setPage} />
            </div>
          </Panel>
          <ItemDrawer
            itemId={opened}
            runId={req.model_run_id}
            onClose={() => setOpened(null)}
            onSaved={() => setReloadRows((n) => n + 1)}
            onNext={idx >= 0 && idx < items.length - 1 ? () => setOpened(items[idx + 1].item_id) : undefined}
            onPrev={idx > 0 ? () => setOpened(items[idx - 1].item_id) : undefined}
            position={idx >= 0 ? { index: (page - 1) * PAGE + idx + 1, total: rows?.total ?? items.length } : undefined}
          />
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {m.importance && m.importance.length > 0 && (
              <Panel
                title="Що найбільше впливає на ризик у цьому аналізі"
                description="Середній внесок ознаки в ризик підозрілих позицій, пунктів (значення Шеплі)"
              >
                <BarList
                  rows={m.importance.slice(0, 8).map((f) => ({ key: f.feature, label: f.label, value: Math.round(f.points * 10) / 10 }))}
                />
              </Panel>
            )}
            {req.homogeneity_details && (
              <Panel title="Однорідність вибірки">
                <HomogeneityCard h={req.homogeneity_details} nItems={req.homogeneity_details.n_items} />
              </Panel>
            )}
          </div>
        </>
      )}
    </Page>
  )
}
