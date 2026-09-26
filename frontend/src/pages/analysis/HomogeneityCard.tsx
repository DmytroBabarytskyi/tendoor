import { motion } from 'motion/react'
import { CircleCheck, CircleX, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Homogeneity } from './types'

// рівень = іконка + підпис + колір: колір ніколи не несе значення сам
const LEVEL = {
  good: { icon: CircleCheck, label: 'однорідна', text: 'text-success', stroke: 'stroke-success', bg: 'bg-success-soft' },
  warn: { icon: TriangleAlert, label: 'змішана', text: 'text-warning', stroke: 'stroke-warning', bg: 'bg-warning-soft' },
  bad: { icon: CircleX, label: 'неоднорідна', text: 'text-critical', stroke: 'stroke-critical', bg: 'bg-critical-soft' },
} as const

function Gauge({ value, className }: { value: number; className: string }) {
  const r = 42
  const c = 2 * Math.PI * r
  return (
    <svg viewBox="0 0 100 100" className="size-28 -rotate-90">
      <circle cx="50" cy="50" r={r} className="fill-none stroke-muted" strokeWidth="9" />
      <motion.circle
        cx="50"
        cy="50"
        r={r}
        className={cn('fill-none', className)}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={c}
        initial={{ strokeDashoffset: c }}
        animate={{ strokeDashoffset: c * (1 - value) }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      />
    </svg>
  )
}

function Part({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-muted-foreground">
          {label} <span className="text-muted-foreground/70">· {hint}</span>
        </span>
        <span className="font-medium tabular">{Math.round(value * 100)} %</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <motion.div className="h-full rounded-full bg-foreground/60" initial={{ width: 0 }} animate={{ width: `${value * 100}%` }} transition={{ duration: 0.6 }} />
      </div>
    </div>
  )
}

export default function HomogeneityCard({ h, nItems }: { h: Homogeneity; nItems: number }) {
  const level = LEVEL[h.level]
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-5">
        <div className="relative">
          <Gauge value={h.index} className={level.stroke} />
          <div className="absolute inset-0 grid place-items-center">
            <span className="font-serif text-2xl font-semibold tabular">{Math.round(h.index * 100)}</span>
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">Однорідність вибірки</div>
          <div className={cn('mt-0.5 flex items-center gap-1.5 font-serif text-xl font-semibold', level.text)}>
            <level.icon className="size-5" />
            {level.label}
          </div>
          <div className="mt-1 text-sm">
            <span className="font-medium tabular">{nItems.toLocaleString('uk-UA')}</span>{' '}
            <span className="text-muted-foreground">позицій з ціною</span>
          </div>
        </div>
      </div>
      <p className={cn('rounded-lg px-3 py-2.5 text-sm', level.bg)}>{h.message}</p>
      <div className="space-y-3">
        <Part label="Категорії ДК 021" hint={`${h.cpv_classes} кл.`} value={h.cpv_concentration} />
        <Part label="Одиниці виміру" hint={`${h.units} од.`} value={h.unit_purity} />
        <Part label="Компактність цін" hint="розкид" value={h.price_compactness} />
      </div>
    </div>
  )
}
