import { ChevronDown, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'

export type Overrides = Record<string, number | boolean>
type ParamsInfo = { defaults: Record<string, unknown>; bounds: Record<string, [number, number]>; calibrator_threshold: number | null }

type NumField = { key: string; label: string; hint: string; step: number; percent?: boolean }
const NUMBERS: NumField[] = [
  { key: 'min_group_size', label: 'Мінімальний розмір групи', hint: 'позицій; менші групи об\'єднуються на вищому рівні ДК 021', step: 1 },
  { key: 'text_split_min', label: 'Ділити групу за описами від', hint: 'позицій; великі групи розбиваються на схожі товари', step: 1 },
  { key: 'extreme_iqr_factor', label: 'Межа екстремальної ціни', hint: 'множник міжквартильного розмаху', step: 0.5 },
  { key: 'z_strong', label: 'Сильне відхилення від медіани', hint: 'у робастних стандартних відхиленнях', step: 0.5 },
  { key: 'min_price_z', label: 'Відхилення для нетипового поєднання', hint: 'ціни, обсягу й дати', step: 0.5 },
  { key: 'anomaly_threshold', label: 'Поріг ризику для позначення', hint: 'ризик від 0 до 100', step: 5, percent: true },
]
const SWITCHES = [
  { key: 'pack_normalize', label: 'Перераховувати фасовку «штук» у ціну за кг або л' },
  { key: 'calibrate', label: 'Уточнювати ризик за вердиктами аудиторів' },
]

/** Перевизначення параметрів виявлення для окремого запиту (аналітик, адміністратор). */
export default function AdvancedParams({ value, onChange }: { value: Overrides; onChange: (v: Overrides) => void }) {
  const [open, setOpen] = useState(false)
  const [info, setInfo] = useState<ParamsInfo | null>(null)

  useEffect(() => {
    if (open && !info) api<ParamsInfo>('/analysis/params').then(setInfo)
  }, [open, info])

  const changed = Object.keys(value).length
  const set = (key: string, v: number | boolean | undefined) => {
    const next = { ...value }
    const base = key === 'anomaly_threshold' ? info?.defaults[key] ?? info?.calibrator_threshold : info?.defaults[key]
    if (v === undefined || v === base) delete next[key]
    else next[key] = v
    onChange(next)
  }

  return (
    <div className="rounded-lg border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm"
      >
        <span className="font-medium">
          Розширені параметри
          {changed > 0 && <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">змінено: {changed}</span>}
        </span>
        <ChevronDown className={cn('size-4 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="space-y-5 border-t px-4 py-4">
          <p className="text-xs text-muted-foreground">
            Діють лише для цього аналізу; значення за замовчуванням задає адміністратор. Змінені параметри означають новий розрахунок,
            а не готовий результат.
          </p>
          {!info ? (
            <div className="text-sm text-muted-foreground">Завантаження…</div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                {NUMBERS.map((f) => {
                  const [lo, hi] = info.bounds[f.key] ?? [0, 1e6]
                  const base = (f.key === 'anomaly_threshold' ? info.defaults[f.key] ?? info.calibrator_threshold : info.defaults[f.key]) as number | null
                  const scale = f.percent ? 100 : 1
                  const current = (value[f.key] as number | undefined) ?? base
                  return (
                    <div key={f.key} className="space-y-1.5">
                      <Label htmlFor={`p-${f.key}`} className="justify-between">
                        {f.label}
                        {value[f.key] !== undefined && (
                          <button type="button" onClick={() => set(f.key, undefined)} className="text-muted-foreground hover:text-foreground" aria-label="Скинути">
                            <RotateCcw className="size-3.5" />
                          </button>
                        )}
                      </Label>
                      <Input
                        id={`p-${f.key}`}
                        type="number"
                        min={lo * scale}
                        max={hi * scale}
                        step={f.step}
                        value={current == null ? '' : Math.round(current * scale * 100) / 100}
                        onChange={(e) => {
                          const n = e.target.valueAsNumber
                          if (Number.isNaN(n)) return set(f.key, undefined)
                          set(f.key, Math.min(hi, Math.max(lo, n / scale)))
                        }}
                        className={cn(value[f.key] !== undefined && 'border-primary')}
                      />
                      <p className="text-xs text-muted-foreground">
                        {f.hint}; за замовчуванням {base == null ? '—' : Math.round(base * scale * 100) / 100}, межі {lo * scale}–{hi * scale}
                      </p>
                    </div>
                  )
                })}
              </div>
              <div className="space-y-3">
                {SWITCHES.map((s) => {
                  const current = (value[s.key] as boolean | undefined) ?? (info.defaults[s.key] as boolean)
                  return (
                    <label key={s.key} className="flex cursor-pointer items-center gap-3 text-sm">
                      <Switch checked={current} onCheckedChange={(v) => set(s.key, v)} />
                      {s.label}
                    </label>
                  )
                })}
              </div>
              {changed > 0 && (
                <Button type="button" variant="ghost" size="sm" onClick={() => onChange({})}>
                  <RotateCcw /> Усі за замовчуванням
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
