import { FileWarning, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { REQUEST_STATUS, riskLevel, type RequestStatus, type Tone } from './status-meta'

const TONE: Record<Tone, string> = {
  critical: 'bg-critical-soft text-critical ring-critical/20',
  warning: 'bg-warning-soft text-warning ring-warning/20',
  success: 'bg-success-soft text-success ring-success/20',
  info: 'bg-info-soft text-info ring-info/20',
  neutral: 'bg-muted text-muted-foreground ring-border',
}

export function Pill({
  tone,
  icon: Icon,
  children,
  className,
  spin,
}: {
  tone: Tone
  icon?: LucideIcon
  children: React.ReactNode
  className?: string
  spin?: boolean
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONE[tone],
        className,
      )}
    >
      {Icon && <Icon className={cn('size-3.5 shrink-0', spin && 'animate-spin')} aria-hidden />}
      {children}
    </span>
  )
}

// ---------------------------------------------------------------- ризик
export function RiskPill({ risk }: { risk: number | null }) {
  const l = riskLevel(risk)
  if (!l) return <span className="text-muted-foreground">—</span>
  return (
    <Pill tone={l.tone} icon={l.icon}>
      <span className="tabular">{l.r}</span> · {l.label}
    </Pill>
  )
}

/** Шкала ризику 0–100: смуга заповнюється, число поруч. */
export function RiskMeter({ risk }: { risk: number | null }) {
  const l = riskLevel(risk)
  if (!l) return <span className="text-muted-foreground">—</span>
  const bar = l.tone === 'critical' ? 'bg-critical' : l.tone === 'warning' ? 'bg-warning' : 'bg-muted-foreground/50'
  return (
    <div className="flex items-center gap-2" title={`Ризик ${l.r} з 100 — ${l.label}`}>
      <span className="w-7 text-right text-sm font-semibold tabular">{l.r}</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full', bar)} style={{ width: `${l.r}%` }} />
      </div>
    </div>
  )
}

/** Другий сигнал: ціна поза межами групи настільки, що це швидше помилка даних (одиниця, фасовка, сума лоту). */
export function DataErrorPill() {
  return (
    <Pill tone="warning" icon={FileWarning}>
      ймовірна помилка даних
    </Pill>
  )
}

// ---------------------------------------------------------------- запит аналізу
export function RequestStatusPill({ status }: { status: RequestStatus }) {
  const s = REQUEST_STATUS[status]
  return (
    <Pill tone={s.tone} icon={s.icon} spin={s.spin}>
      {s.label}
    </Pill>
  )
}

