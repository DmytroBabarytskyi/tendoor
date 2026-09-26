import { BadgeCheck, CircleDashed, Clock, PenLine, Undo2 } from 'lucide-react'
import { Pill } from '@/components/status'
import { VERDICT_TONE } from '@/components/status-meta'
import { VERDICT_STATE, VERDICT_STATUS, type VerdictState, type VerdictStatus } from './verdicts'

const STATE_ICON = { in_progress: PenLine, submitted: Clock, returned: Undo2, approved: BadgeCheck } as const

/** Стан перевірки: «в роботі», «на погодженні», «повернено», «погоджено». */
export function StatePill({ state }: { state: VerdictState }) {
  const tone = state === 'approved' ? 'success' : state === 'returned' ? 'warning' : state === 'submitted' ? 'info' : 'neutral'
  return (
    <Pill tone={tone} icon={STATE_ICON[state]}>
      {VERDICT_STATE[state]}
    </Pill>
  )
}

/** Висновок перевірки разом зі станом; без висновку — лише стан або «не розглянуто». */
export default function VerdictPill({
  status,
  state,
}: {
  status: VerdictStatus | null | undefined
  state?: VerdictState | null
}) {
  if (!status && !state)
    return (
      <Pill tone="neutral" icon={CircleDashed}>
        не розглянуто
      </Pill>
    )
  if (!status) return <StatePill state={state!} />
  const t = VERDICT_TONE[status]
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <Pill tone={t.tone} icon={t.icon}>
        {VERDICT_STATUS[status].label}
      </Pill>
      {state && state !== 'approved' && <span className="text-xs text-muted-foreground">· {VERDICT_STATE[state]}</span>}
      {state === 'approved' && <BadgeCheck className="size-4 text-success" aria-label="погоджено" />}
    </span>
  )
}
