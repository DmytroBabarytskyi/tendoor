import {
  CircleCheck,
  CircleDashed,
  CircleHelp,
  CircleX,
  LoaderCircle,
  OctagonAlert,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'

// Статус завжди = іконка + підпис + колір: значення ніколи не передається лише кольором
export type Tone = 'critical' | 'warning' | 'success' | 'info' | 'neutral'

export function riskLevel(risk: number | null) {
  if (risk == null) return null
  const r = Math.round(risk)
  if (r >= 80) return { r, tone: 'critical' as const, label: 'високий', icon: OctagonAlert }
  if (r >= 50) return { r, tone: 'warning' as const, label: 'середній', icon: TriangleAlert }
  return { r, tone: 'neutral' as const, label: 'низький', icon: CircleDashed }
}

export type RequestStatus = 'queued' | 'running' | 'done' | 'failed'
export const REQUEST_STATUS: Record<RequestStatus, { tone: Tone; label: string; icon: LucideIcon; spin?: boolean }> = {
  queued: { tone: 'neutral', label: 'у черзі', icon: CircleDashed },
  running: { tone: 'info', label: 'навчання моделі', icon: LoaderCircle, spin: true },
  done: { tone: 'success', label: 'готово', icon: CircleCheck },
  failed: { tone: 'critical', label: 'помилка', icon: CircleX },
}

export type VerdictStatus = 'confirmed' | 'not_anomaly' | 'needs_review'
export const VERDICT_TONE: Record<VerdictStatus, { tone: Tone; icon: LucideIcon }> = {
  confirmed: { tone: 'critical', icon: OctagonAlert },
  not_anomaly: { tone: 'success', icon: CircleCheck },
  needs_review: { tone: 'warning', icon: CircleHelp },
}
