import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragMoveEvent,
} from '@dnd-kit/core'
import { arrayMove, rectSortingStrategy, SortableContext, sortableKeyboardCoordinates, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ArrowRight, Building2, Database, FileStack, FlaskConical, GripVertical, PackageSearch, Tags } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '@/api/client'
import BarList from '@/components/BarList'
import GravityGrid from '@/components/gravity/GravityGrid'
import { gravity } from '@/components/gravity/store'
import { EmptyState, Page, PageHeader, Panel } from '@/components/page'
import StatTile from '@/components/StatTile'
import { RequestStatusPill } from '@/components/status'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { date, dateTime, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { AnalysisRequest } from './analysis/types'

type Stats = {
  tenders: number
  items: number
  items_priced: number
  entities: number
  raw_documents: number
  date_min: string | null
  date_max: string | null
  by_price_source: Record<string, number>
  top_units: { code: string; name: string | null; n: number }[]
}

const SOURCE_NAMES: Record<string, string> = {
  unit_value: 'Явна ціна за одиницю',
  contract: 'З договору',
  expected: 'З очікуваної вартості',
  None: 'Не визначено',
}

type TileId = 'tenders' | 'items' | 'priced' | 'entities'
const DEFAULT_ORDER: TileId[] = ['tenders', 'items', 'priced', 'entities']
const ORDER_KEY = 'tendoor-dashboard-order'

function loadOrder(): TileId[] {
  try {
    const v = JSON.parse(localStorage.getItem(ORDER_KEY) ?? 'null')
    if (Array.isArray(v) && v.length === DEFAULT_ORDER.length && DEFAULT_ORDER.every((t) => v.includes(t))) return v
  } catch {
    /* порядок за замовчуванням */
  }
  return DEFAULT_ORDER
}

function SortableTile({ id, children }: { id: string; children: ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn('group relative touch-none', isDragging && 'z-10')}
      data-no-ripple
    >
      <div
        className={cn(
          'transition-[transform,box-shadow] duration-200',
          isDragging && 'scale-[1.03] rotate-[0.6deg] rounded-xl shadow-[0_24px_50px_-18px_rgba(80,50,20,0.35)]',
        )}
      >
        {children}
      </div>
      <button
        {...attributes}
        {...listeners}
        className="absolute top-3 right-3 cursor-grab rounded p-1 text-muted-foreground/0 transition-colors group-hover:text-muted-foreground focus-visible:text-muted-foreground active:cursor-grabbing"
        aria-label="Перетягнути картку"
      >
        <GripVertical className="size-4" />
      </button>
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recent, setRecent] = useState<AnalysisRequest[] | null>(null)
  const [order, setOrder] = useState<TileId[]>(loadOrder)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  useEffect(() => {
    api<Stats>('/procurement/stats').then(setStats, (e: Error) => setError(e.message))
    api<AnalysisRequest[]>('/analysis/requests?limit=6').then(setRecent, () => setRecent([]))
  }, [])

  const tiles: Record<TileId, ReactNode> = {
    tenders: <StatTile label="Закупівель" value={stats?.tenders} icon={FileStack} hint="у базі системи" />,
    items: <StatTile label="Позицій (товарів)" value={stats?.items} icon={PackageSearch} hint="предметів закупівель" />,
    priced: (
      <StatTile
        label="Позицій з ціною"
        value={stats?.items_priced}
        icon={Tags}
        hint={stats ? `${Math.round((100 * stats.items_priced) / Math.max(1, stats.items))} % позицій придатні для аналізу` : ' '}
      />
    ),
    entities: <StatTile label="Замовників" value={stats?.entities} icon={Building2} hint="державних і комунальних" />,
  }

  // картка, яку тягнуть, — «маса» для сітки; після відпускання — хвиля
  const onDragMove = (e: DragMoveEvent) => {
    const r = e.active.rect.current.translated
    if (r) gravity.setMass('drag', { x: r.left + r.width / 2, y: r.top + r.height / 2, strength: 2.2 })
  }
  const onDragEnd = (e: DragEndEvent) => {
    const r = e.active.rect.current.translated
    gravity.removeMass('drag')
    if (r) gravity.ripple(r.left + r.width / 2, r.top + r.height / 2, 0.8)
    if (e.over && e.active.id !== e.over.id) {
      setOrder((o) => {
        const next = arrayMove(o, o.indexOf(e.active.id as TileId), o.indexOf(e.over!.id as TileId))
        try {
          localStorage.setItem(ORDER_KEY, JSON.stringify(next))
        } catch {
          /* порядок діє до перезавантаження */
        }
        return next
      })
    }
  }

  const period =
    stats?.date_min && stats.date_max ? `Оголошені ${date(stats.date_min)} – ${date(stats.date_max)}` : undefined

  return (
    <div className="relative -mx-4 -my-6 min-h-[calc(100svh-3.5rem)] overflow-hidden px-4 py-6 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-8 lg:py-8">
      <GravityGrid cursorStrength={0.8} spacing={44} />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,transparent_10%,var(--background)_75%)]" />
      <Page className="relative">
        <PageHeader
          title="Огляд бази закупівель"
          description={period}
          actions={
            <Button onClick={() => navigate('/analysis')}>
              <FlaskConical /> Новий аналіз
            </Button>
          }
        />
        {error && <div className="mb-4 rounded-lg bg-critical-soft px-4 py-3 text-sm text-critical">{error}</div>}

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragMove={onDragMove} onDragEnd={onDragEnd} onDragCancel={() => gravity.removeMass('drag')}>
          <SortableContext items={order} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              {order.map((id) => (
                <SortableTile key={id} id={id}>
                  {tiles[id]}
                </SortableTile>
              ))}
            </div>
          </SortableContext>
        </DndContext>

        <div className="mt-4 grid gap-4 lg:grid-cols-5">
          <Panel
            className="lg:col-span-3"
            title="Мої останні аналізи"
            actions={
              <Button asChild variant="ghost" size="sm">
                <Link to="/analysis">
                  Усі <ArrowRight />
                </Link>
              </Button>
            }
            bodyClassName="p-0"
          >
            {recent === null ? (
              <div className="space-y-2 p-5">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : recent.length === 0 ? (
              <EmptyState icon={FlaskConical} title="Ще немає аналізів">
                Оберіть товари й період — система знайде ціни, що вибиваються з ринку.
              </EmptyState>
            ) : (
              <ul className="divide-y">
                {recent.map((r) => (
                  <li key={r.id}>
                    <Link to={`/analysis/${r.id}`} className="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-accent/40">
                      <span className="w-10 font-mono text-xs text-muted-foreground">№{r.id}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">ДК 021: {r.cpv_prefixes.join(', ')}</span>
                        <span className="block text-xs text-muted-foreground">
                          {shortDate(r.date_from)} – {shortDate(r.date_to)} · {dateTime(r.created_at)}
                        </span>
                      </span>
                      <RequestStatusPill status={r.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel className="lg:col-span-2" title="Звідки береться ціна за одиницю" description="Позиції з ціною">
            {stats ? (
              <BarList
                rows={Object.entries(stats.by_price_source)
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => ({ key: k, label: SOURCE_NAMES[k] ?? k, value: v }))}
              />
            ) : (
              <Skeleton className="h-32" />
            )}
          </Panel>
          <Panel className="lg:col-span-5" title="Базові одиниці виміру" description="Ціни порівнюються лише в межах однієї одиниці">
            {stats ? (
              <div className="grid gap-x-10 md:grid-cols-2">
                <BarList
                  rows={stats.top_units.map((u) => ({ key: u.code, label: u.name ?? u.code, hint: u.code, value: u.n }))}
                />
                <div className="mt-6 flex items-start gap-3 rounded-lg bg-muted/60 p-4 text-sm text-muted-foreground md:mt-0">
                  <Database className="mt-0.5 size-4 shrink-0" />
                  <p>
                    Документів Prozorro у сховищі без змін:{' '}
                    <span className="font-medium text-foreground tabular">{stats.raw_documents.toLocaleString('uk-UA')}</span>. Кількість
                    у різних одиницях (упаковки, літри, кілограми) система зводить до базової одиниці, а «штуки» з фасовкою в назві —
                    до ціни за кілограм чи літр.
                  </p>
                </div>
              </div>
            ) : (
              <Skeleton className="h-40" />
            )}
          </Panel>
        </div>
      </Page>
    </div>
  )
}
