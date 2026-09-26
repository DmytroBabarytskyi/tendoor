import { Check, ChevronsUpDown, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

export type CpvOption = { code: string; description: string; level: number; n: number }

/** Пошук кодів ДК 021 за назвою або кодом; вибрані коди — «жетони» з кнопкою видалення. */
export default function CpvPicker({
  value,
  onChange,
  id,
}: {
  value: CpvOption[]
  onChange: (v: CpvOption[]) => void
  id?: string
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState<CpvOption[] | null>(null)

  useEffect(() => {
    let alive = true
    const t = setTimeout(() => {
      api<CpvOption[]>(`/analysis/cpv?q=${encodeURIComponent(query)}`).then((o) => alive && setOptions(o))
    }, 200)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [query])

  const has = (code: string) => value.some((v) => v.code === code)
  const toggle = (o: CpvOption) => onChange(has(o.code) ? value.filter((v) => v.code !== o.code) : [...value, o])

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button id={id} variant="outline" role="combobox" aria-expanded={open} className="w-full justify-between font-normal">
            <span className="truncate text-muted-foreground">
              {value.length ? `Обрано кодів: ${value.length}` : 'Назва або код, напр. «молоко» чи 1551'}
            </span>
            <ChevronsUpDown className="opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[340px] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput placeholder="Шукати в ДК 021…" value={query} onValueChange={setQuery} />
            <CommandList>
              <CommandEmpty>{options === null ? 'Пошук…' : 'Нічого не знайдено'}</CommandEmpty>
              <CommandGroup heading="Коди з позиціями, що мають ціну">
                {(options ?? []).map((o) => (
                  <CommandItem key={o.code} value={o.code} onSelect={() => toggle(o)} className="gap-3">
                    <Check className={cn('size-4', has(o.code) ? 'opacity-100' : 'opacity-0')} />
                    <span className="font-mono text-xs text-muted-foreground">{o.code}</span>
                    <span className="min-w-0 flex-1 truncate">{o.description}</span>
                    <span className="text-xs text-muted-foreground tabular">{o.n.toLocaleString('uk-UA')}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((v) => (
            <span key={v.code} className="inline-flex max-w-full items-center gap-1.5 rounded-md border bg-secondary py-1 pr-1 pl-2 text-xs">
              <span className="font-mono text-muted-foreground">{v.code}</span>
              <span className="max-w-60 truncate">{v.description}</span>
              <button
                type="button"
                onClick={() => onChange(value.filter((x) => x.code !== v.code))}
                className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                aria-label={`Прибрати ${v.code}`}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
