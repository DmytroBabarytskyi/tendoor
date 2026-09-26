import { BadgeCheck, ChevronDown, ChevronUp, ExternalLink, LoaderCircle, PenLine, Send, Undo2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { useAuth } from '@/auth/context'
import Contributions, { type Contribution } from '@/components/Contributions'
import { Kbd } from '@/components/page'
import { Pill, RiskMeter } from '@/components/status'
import { VERDICT_TONE } from '@/components/status-meta'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { date, dateTime, money } from '@/lib/format'
import { cn } from '@/lib/utils'
import { refreshBadges } from '@/layout/badges'
import { StatePill } from './VerdictPill'
import { VERDICT_REASON, VERDICT_STATUS, type Verdict, type VerdictHistory, type VerdictReason, type VerdictStatus } from './verdicts'

type Card = {
  item: {
    item_id: number
    description: string
    quantity: number
    unit_name: string | null
    unit_code: string
    unit_price: number | null
    unit_price_base: number
    base_unit_code: string
    price_source: string
    cpv_code: string
    cpv_description: string | null
    tender_code: string
    tender_title: string | null
    method_type: string
    date_published: string
    entity_name: string
    entity_edrpou: string
    entity_region: string | null
    supplier_name: string | null
    contract_amount: number | null
  }
  result: {
    result_id: number
    risk_score: number | null
    median_price: number | null
    explanation: string
    is_anomaly: boolean
    model_price: number | null
    model_unit: string | null
    contributions: Contribution[] | null
  } | null
  analogs: { item_id: number; description: string; unit_price_base: number; quantity_base: number; entity_name: string; entity_region: string | null }[]
  verdict: Verdict | null
}

const SOURCE: Record<string, string> = { unit_value: 'явна ціна за одиницю', contract: 'з договору', expected: 'з очікуваної вартості' }
const STATUSES = Object.keys(VERDICT_STATUS) as VerdictStatus[]

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  )
}

export default function ItemDrawer({
  itemId,
  runId,
  onClose,
  onSaved,
  onNext,
  onPrev,
}: {
  itemId: number | null
  runId?: number | null
  onClose: () => void
  onSaved?: (v: Verdict) => void
  onNext?: () => void
  onPrev?: () => void
}) {
  const { user, hasRole } = useAuth()
  const [card, setCard] = useState<{ id: number; data: Card } | null>(null)
  const [history, setHistory] = useState<VerdictHistory[]>([])
  const [status, setStatus] = useState<VerdictStatus | null>(null)
  const [reason, setReason] = useState<VerdictReason | null>(null)
  const [comment, setComment] = useState('')
  const [reviewComment, setReviewComment] = useState('')
  const [saving, setSaving] = useState(false)
  const canAct = hasRole('admin', 'auditor')

  const load = useCallback(
    (id: number) =>
      Promise.all([
        api<Card>(`/items/${id}${runId ? `?run_id=${runId}` : ''}`),
        api<VerdictHistory[]>(`/items/${id}/verdict-history`),
      ]),
    [runId],
  )

  useEffect(() => {
    if (itemId == null) return
    let alive = true
    load(itemId).then(([c, h]) => {
      if (!alive) return
      setCard({ id: itemId, data: c })
      setHistory(h)
      setStatus(c.verdict?.status ?? null)
      setReason(c.verdict?.reason ?? null)
      setComment(c.verdict?.comment ?? '')
      setReviewComment('')
    })
    return () => {
      alive = false
    }
  }, [itemId, load])

  const data = card && card.id === itemId ? card.data : null
  const verdict = data?.verdict ?? null
  const mine = !!verdict && verdict.user_id === user?.id
  // режим картки: хто дивиться і в якому стані перевірка
  const mode: 'free' | 'editing' | 'busy' | 'awaiting' | 'review' | 'approved' | 'readonly' = !canAct
    ? 'readonly'
    : !verdict
      ? 'free'
      : verdict.state === 'approved'
        ? 'approved'
        : verdict.state === 'submitted'
          ? mine
            ? 'awaiting'
            : 'review'
          : mine
            ? 'editing'
            : 'busy'
  const editable = mode === 'free' || mode === 'editing' || mode === 'awaiting'

  const act = async (path: string, method: string, body: object | undefined, done: string) => {
    if (itemId == null) return
    setSaving(true)
    try {
      const v = await api<Verdict>(`/items/${itemId}/${path}`, { method, body: body ? JSON.stringify(body) : undefined })
      toast.success(done)
      const [c, h] = await load(itemId)
      setCard({ id: itemId, data: c })
      setHistory(h)
      setReviewComment('')
      refreshBadges()
      onSaved?.(v)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const submit = () => {
    if (!status || !reason) {
      toast.error('Оберіть висновок і причину')
      return
    }
    const body = { status, reason, comment: comment || null, result_id: data?.result?.result_id ?? null }
    void act('verdict', 'PUT', body, 'Висновок надіслано на погодження')
  }
  const take = () => act('take', 'POST', { result_id: data?.result?.result_id ?? null }, 'Позицію взято в роботу')
  const review = (decision: 'approve' | 'return') =>
    act('review', 'POST', { decision, comment: reviewComment || null }, decision === 'approve' ? 'Висновок погоджено' : 'Повернено на доопрацювання')

  // клавіші аудитора: 1/2/3 — висновок, Ctrl+Enter — надіслати, J/K — наступна/попередня позиція
  useEffect(() => {
    if (itemId == null) return
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest('textarea, input, [role="combobox"], [role="listbox"]')
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && editable) {
        e.preventDefault()
        submit()
        return
      }
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return
      const s = STATUSES.find((x) => VERDICT_STATUS[x].key === e.key)
      if (s && editable) setStatus(s)
      else if (e.key.toLowerCase() === 'j') onNext?.()
      else if (e.key.toLowerCase() === 'k') onPrev?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const it = data?.item
  const r = data?.result
  const price = r?.model_price ?? it?.unit_price_base
  const unit = r?.model_unit ?? it?.base_unit_code
  return (
    <Sheet open={itemId != null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full gap-0 overflow-y-auto p-0 sm:max-w-2xl">
        <SheetHeader className="sticky top-0 z-10 border-b bg-background/90 px-6 py-4 backdrop-blur">
          <div className="flex items-center justify-between gap-3 pr-8">
            <div className="min-w-0">
              <SheetTitle className="font-serif text-xl">Розгляд позиції</SheetTitle>
              <SheetDescription className="truncate">{it ? it.tender_code : 'Завантаження…'}</SheetDescription>
            </div>
            {(onPrev || onNext) && (
              <div className="flex items-center gap-1">
                <Button variant="outline" size="icon" className="size-8" onClick={onPrev} disabled={!onPrev} aria-label="Попередня позиція (K)">
                  <ChevronUp />
                </Button>
                <Button variant="outline" size="icon" className="size-8" onClick={onNext} disabled={!onNext} aria-label="Наступна позиція (J)">
                  <ChevronDown />
                </Button>
              </div>
            )}
          </div>
        </SheetHeader>

        {!data || !it ? (
          <div className="space-y-4 p-6">
            <Skeleton className="h-24" />
            <Skeleton className="h-48" />
            <Skeleton className="h-32" />
          </div>
        ) : (
          <div className="space-y-7 p-6">
            {r && (
              <div className={cn('rounded-xl border p-4', r.is_anomaly ? 'border-critical/30 bg-critical-soft/50' : 'bg-muted/40')}>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">{r.is_anomaly ? 'Позначено як аномальну ціну' : 'Звичайна ціна'}</div>
                  <RiskMeter risk={r.risk_score} />
                </div>
                <p className="mt-2 text-sm text-pretty">{r.explanation}</p>
              </div>
            )}

            {r?.contributions && r.contributions.length > 0 && (
              <section>
                <h4 className="mb-1 font-sans text-sm font-semibold">Що вплинуло на ризик</h4>
                <p className="mb-3 text-xs text-muted-foreground">
                  Внесок кожної ознаки в пунктах ризику: червоне підвищує, зелене знижує відносно звичайної позиції.
                </p>
                <Contributions items={r.contributions} />
              </section>
            )}

            <section>
              <h3 className="mb-1 text-lg leading-snug font-semibold">{it.description}</h3>
              <div className="font-serif text-2xl font-semibold tabular">
                {money(price)} <span className="text-base font-normal text-muted-foreground">грн/{unit}</span>
              </div>
              <dl className="mt-3 divide-y border-y">
                <Field label="У документі">
                  {money(it.unit_price)} грн/{it.unit_name ?? it.unit_code} · <span className="text-muted-foreground">{SOURCE[it.price_source] ?? it.price_source}</span>
                </Field>
                <Field label="Обсяг">
                  {money(it.quantity)} {it.unit_name ?? it.unit_code}
                </Field>
                <Field label="Код ДК 021">
                  <span className="font-mono text-xs">{it.cpv_code}</span> {it.cpv_description}
                </Field>
                <Field label="Замовник">
                  {it.entity_name} <span className="text-muted-foreground">· ЄДРПОУ {it.entity_edrpou}</span>
                  {it.entity_region && <span className="text-muted-foreground"> · {it.entity_region}</span>}
                </Field>
                {it.supplier_name && (
                  <Field label="Постачальник">
                    {it.supplier_name}, договір {money(it.contract_amount)} грн
                  </Field>
                )}
                <Field label="Закупівля">
                  <a
                    href={`https://prozorro.gov.ua/tender/${it.tender_code}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
                  >
                    {it.tender_code} <ExternalLink className="size-3" />
                  </a>{' '}
                  <span className="text-muted-foreground">
                    · {it.method_type} · {date(it.date_published)}
                  </span>
                </Field>
              </dl>
            </section>

            <section>
              <h4 className="mb-2 font-sans text-sm font-semibold">
                Аналоги з тієї ж групи <span className="font-normal text-muted-foreground">· найближчі до медіани {money(r?.median_price)} грн</span>
              </h4>
              {data.analogs.length ? (
                <ul className="divide-y rounded-lg border text-sm">
                  {data.analogs.map((a) => (
                    <li key={a.item_id} className="flex items-center gap-3 px-3 py-2">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">{a.description}</span>
                        <span className="block truncate text-xs text-muted-foreground">{a.entity_name}</span>
                      </span>
                      <span className="shrink-0 font-medium tabular">{money(a.unit_price_base)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Позиція поза аналізом — немає даних про групу.</p>
              )}
            </section>

            <section className="rounded-xl border bg-card p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h4 className="flex items-center gap-2 font-sans text-sm font-semibold">
                  Перевірка {verdict && <StatePill state={verdict.state} />}
                </h4>
                {editable && (
                  <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                    <Kbd>1</Kbd>
                    <Kbd>2</Kbd>
                    <Kbd>3</Kbd> висновок · <Kbd>Ctrl</Kbd>+<Kbd>Enter</Kbd> надіслати
                  </span>
                )}
              </div>

              {verdict && (
                <p className="mb-3 text-xs text-muted-foreground">
                  Автор: {verdict.user_name ?? verdict.user_email ?? '—'}
                  {verdict.reviewer_name && ` · погоджувач: ${verdict.reviewer_name}`}
                  {verdict.reviewed_at && `, ${dateTime(verdict.reviewed_at)}`}
                </p>
              )}
              {verdict?.state === 'returned' && verdict.review_comment && (
                <div className="mb-3 flex gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm">
                  <Undo2 className="mt-0.5 size-4 shrink-0 text-warning" />
                  <div>
                    <div className="font-medium">Повернено на доопрацювання{verdict.reviewer_name && `: ${verdict.reviewer_name}`}</div>
                    <div className="mt-0.5">{verdict.review_comment}</div>
                  </div>
                </div>
              )}
              {mode === 'busy' && (
                <p className="mb-3 rounded-lg bg-muted px-3 py-2.5 text-sm">
                  Позицію перевіряє {verdict?.user_name ?? 'інший аудитор'}. Коли висновок надішлють, ви зможете його погодити.
                </p>
              )}
              {mode === 'awaiting' && (
                <p className="mb-3 rounded-lg bg-info-soft px-3 py-2.5 text-sm">
                  Висновок очікує погодження іншим аудитором. До погодження його ще можна виправити.
                </p>
              )}

              <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Висновок">
                {STATUSES.map((s) => {
                  const t = VERDICT_TONE[s]
                  const on = status === s
                  return (
                    <button
                      key={s}
                      type="button"
                      role="radio"
                      aria-checked={on}
                      disabled={!editable}
                      onClick={() => setStatus(s)}
                      className={cn(
                        'flex flex-col items-start gap-1 rounded-lg border p-3 text-left text-sm transition-all disabled:cursor-default',
                        !on && !editable && 'opacity-50',
                        on ? 'border-transparent ring-2 ring-offset-1 ring-offset-card' : editable && 'hover:bg-accent/50',
                        on && t.tone === 'critical' && 'bg-critical-soft ring-critical',
                        on && t.tone === 'success' && 'bg-success-soft ring-success',
                        on && t.tone === 'warning' && 'bg-warning-soft ring-warning',
                      )}
                    >
                      <span className="flex w-full items-center justify-between">
                        <t.icon className="size-4" />
                        {editable && <Kbd>{VERDICT_STATUS[s].key}</Kbd>}
                      </span>
                      <span className="font-medium">{VERDICT_STATUS[s].short}</span>
                    </button>
                  )
                })}
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_1.4fr]">
                <div className="space-y-1.5">
                  <Label>Причина</Label>
                  <Select value={reason ?? ''} onValueChange={(v) => setReason(v as VerdictReason)} disabled={!editable}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Оберіть причину" />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(VERDICT_REASON) as VerdictReason[]).map((x) => (
                        <SelectItem key={x} value={x}>
                          {VERDICT_REASON[x]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="comment">Коментар аудитора</Label>
                  <Textarea
                    id="comment"
                    value={comment}
                    maxLength={2000}
                    disabled={!editable}
                    onChange={(e) => setComment(e.target.value)}
                    className="min-h-9"
                    placeholder="Що побачили в договорі, чим пояснюється ціна…"
                  />
                </div>
              </div>

              {editable && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button onClick={submit} disabled={saving}>
                    {saving ? <LoaderCircle className="animate-spin" /> : <Send />}
                    {mode === 'awaiting' ? 'Оновити висновок' : 'Надіслати на погодження'}
                  </Button>
                  {mode === 'free' && (
                    <Button variant="outline" onClick={take} disabled={saving}>
                      <PenLine /> Взяти в роботу
                    </Button>
                  )}
                </div>
              )}

              {mode === 'review' && (
                <div className="mt-4 space-y-3 border-t pt-4">
                  <Label htmlFor="review-comment">Рішення погоджувача</Label>
                  <Textarea
                    id="review-comment"
                    value={reviewComment}
                    maxLength={2000}
                    onChange={(e) => setReviewComment(e.target.value)}
                    className="min-h-9"
                    placeholder="Для повернення — що саме доопрацювати; для погодження — необов'язково"
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => review('approve')} disabled={saving}>
                      <BadgeCheck /> Погодити
                    </Button>
                    <Button variant="outline" onClick={() => review('return')} disabled={saving || !reviewComment.trim()}>
                      <Undo2 /> Повернути на доопрацювання
                    </Button>
                  </div>
                </div>
              )}
            </section>

            {history.length > 0 && (
              <section>
                <h4 className="mb-3 font-sans text-sm font-semibold">Історія змін</h4>
                <ol className="relative space-y-4 border-l pl-5">
                  {history.map((h) => (
                    <li key={h.id} className="relative">
                      <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full border-2 border-card bg-primary" />
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        {h.new_state && h.new_state !== h.old_state && <StatePill state={h.new_state} />}
                        {h.new_status && (h.new_status !== h.old_status || h.new_reason !== h.old_reason) && (
                          <>
                            <Pill tone={VERDICT_TONE[h.new_status].tone} icon={VERDICT_TONE[h.new_status].icon}>
                              {VERDICT_STATUS[h.new_status].label}
                            </Pill>
                            {h.new_reason && <span>{VERDICT_REASON[h.new_reason]}</span>}
                          </>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {h.user_name ?? h.user_email ?? 'система'} · {dateTime(h.changed_at)}
                      </div>
                      {h.comment && <p className="mt-1 text-sm text-muted-foreground">{h.comment}</p>}
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
