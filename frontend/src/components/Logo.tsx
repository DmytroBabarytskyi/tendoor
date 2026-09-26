import { cn } from '@/lib/utils'

/** Знак Tendoor: прочинені двері (Ten + door), крізь щілину — світло акценту. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('size-7', className)} aria-hidden>
      <rect x="6" y="3.5" width="20" height="25" rx="3" className="fill-none stroke-foreground" strokeWidth="2" />
      <path d="M12 6.5 L22 8.5 V25 L12 26.5 Z" className="fill-primary" />
      <circle cx="19.2" cy="17" r="1.3" className="fill-primary-foreground" />
    </svg>
  )
}

export default function Logo({ className, subtitle = true }: { className?: string; subtitle?: boolean }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <LogoMark />
      <div className="leading-none">
        <div className="font-serif text-xl font-semibold tracking-tight">Tendoor</div>
        {subtitle && <div className="mt-1 text-[11px] text-muted-foreground">цінові аномалії закупівель</div>}
      </div>
    </div>
  )
}
