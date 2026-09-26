import { subDays, startOfMonth, subMonths, endOfMonth } from 'date-fns'
import { CalendarDays } from 'lucide-react'
import { useState } from 'react'
import type { DateRange } from 'react-day-picker'
import { uk } from 'react-day-picker/locale'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { date } from '@/lib/format'
import { cn } from '@/lib/utils'

export type Range = { from: Date; to: Date }

const PRESETS: { label: string; range: () => Range }[] = [
  { label: 'Вчора', range: () => ({ from: subDays(new Date(), 1), to: subDays(new Date(), 1) }) },
  { label: '7 днів', range: () => ({ from: subDays(new Date(), 6), to: new Date() }) },
  { label: '30 днів', range: () => ({ from: subDays(new Date(), 29), to: new Date() }) },
  { label: 'Цей місяць', range: () => ({ from: startOfMonth(new Date()), to: new Date() }) },
  {
    label: 'Минулий місяць',
    range: () => ({ from: startOfMonth(subMonths(new Date(), 1)), to: endOfMonth(subMonths(new Date(), 1)) }),
  },
  { label: '2 місяці', range: () => ({ from: startOfMonth(subMonths(new Date(), 1)), to: new Date() }) },
]

export default function DateRangePicker({
  value,
  onChange,
  disableFuture = true,
  className,
  id,
}: {
  value: Range | null
  onChange: (r: Range) => void
  disableFuture?: boolean
  className?: string
  id?: string
}) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<DateRange | undefined>(value ?? undefined)

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (o) setDraft(value ?? undefined)
      }}
    >
      <PopoverTrigger asChild>
        <Button id={id} variant="outline" className={cn('w-full justify-start font-normal', !value && 'text-muted-foreground', className)}>
          <CalendarDays className="text-muted-foreground" />
          <span className="tabular">{value ? `${date(value.from)} – ${date(value.to)}` : 'Оберіть період'}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="flex flex-col sm:flex-row">
          <div className="flex flex-row flex-wrap gap-1 border-b p-2 sm:w-36 sm:flex-col sm:border-r sm:border-b-0">
            {PRESETS.map((p) => (
              <Button
                key={p.label}
                variant="ghost"
                size="sm"
                className="justify-start"
                onClick={() => {
                  onChange(p.range())
                  setOpen(false)
                }}
              >
                {p.label}
              </Button>
            ))}
          </div>
          <div>
            <Calendar
              mode="range"
              locale={uk}
              numberOfMonths={2}
              defaultMonth={draft?.from ?? subMonths(new Date(), 1)}
              selected={draft}
              onSelect={(r) => {
                setDraft(r)
                if (r?.from && r.to && r.from.getTime() !== r.to.getTime()) {
                  onChange({ from: r.from, to: r.to })
                  setOpen(false)
                }
              }}
              disabled={disableFuture ? { after: new Date() } : undefined}
            />
            <div className="flex justify-end gap-2 border-t p-2">
              <Button
                size="sm"
                disabled={!draft?.from}
                onClick={() => {
                  if (draft?.from) onChange({ from: draft.from, to: draft.to ?? draft.from })
                  setOpen(false)
                }}
              >
                Застосувати
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
