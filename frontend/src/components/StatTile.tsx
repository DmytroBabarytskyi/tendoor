import { animate, useMotionValue, useTransform, motion } from 'motion/react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/** Число, що «докручується» до значення під час появи. */
export function CountUp({ value, format }: { value: number; format?: (v: number) => string }) {
  const mv = useMotionValue(0)
  const text = useTransform(mv, (v) => (format ? format(v) : Math.round(v).toLocaleString('uk-UA')))
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.9, ease: [0.22, 1, 0.36, 1] })
    return () => controls.stop()
  }, [mv, value])
  return <motion.span className="tabular">{text}</motion.span>
}

export default function StatTile({
  label,
  value,
  format,
  hint,
  icon: Icon,
  className,
  children,
}: {
  label: string
  value: number | null | undefined
  format?: (v: number) => string
  hint?: ReactNode
  icon?: LucideIcon
  className?: string
  children?: ReactNode
}) {
  return (
    <div className={cn('rounded-xl border bg-card p-4 shadow-[0_1px_2px_rgba(60,40,20,0.04)]', className)}>
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
        <span>{label}</span>
        {Icon && <Icon className="size-4 text-muted-foreground/70" aria-hidden />}
      </div>
      <div className="mt-2 font-serif text-3xl font-semibold tracking-tight">
        {value == null ? <Skeleton className="h-8 w-24" /> : <CountUp value={value} format={format} />}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      {children}
    </div>
  )
}
