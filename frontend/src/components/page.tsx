import { motion } from 'motion/react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-xs font-medium uppercase tracking-wider text-primary">{eyebrow}</div>}
        <h1 className="text-3xl font-semibold text-balance">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground text-pretty">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

/** Поява сторінки: легке підняття й проявлення. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className={cn('mx-auto w-full max-w-[1400px]', className)}
    >
      {children}
    </motion.div>
  )
}

export function Panel({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={cn('rounded-xl border bg-card text-card-foreground shadow-[0_1px_2px_rgba(60,40,20,0.04)]', className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-3.5">
          <div className="min-w-0">
            {title && <h2 className="font-sans text-sm font-semibold tracking-normal">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={cn('p-5', bodyClassName)}>{children}</div>
    </section>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon: LucideIcon
  title: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-2 px-6 py-10 text-center', className)}>
      <div className="grid size-11 place-items-center rounded-full bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </div>
      <div className="text-sm font-medium">{title}</div>
      {children && <div className="max-w-sm text-sm text-muted-foreground">{children}</div>}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border bg-muted px-1 font-mono text-[10px] font-medium text-muted-foreground">
      {children}
    </kbd>
  )
}
