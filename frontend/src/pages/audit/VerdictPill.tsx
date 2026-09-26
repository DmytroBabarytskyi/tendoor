import { CircleDashed } from 'lucide-react'
import { Pill } from '@/components/status'
import { VERDICT_TONE } from '@/components/status-meta'
import { VERDICT_STATUS, type VerdictStatus } from './verdicts'

export default function VerdictPill({ status }: { status: VerdictStatus | null | undefined }) {
  if (!status)
    return (
      <Pill tone="neutral" icon={CircleDashed}>
        не розглянуто
      </Pill>
    )
  const t = VERDICT_TONE[status]
  return (
    <Pill tone={t.tone} icon={t.icon}>
      {VERDICT_STATUS[status].label}
    </Pill>
  )
}
