import { motion } from 'motion/react'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

// підписи ознак мовою аудитора (у збережених аналізах можуть лишатися старі назви)
const LABELS: Record<string, string> = {
  abs_z: 'Наскільки ціна відхиляється від типової в групі',
  z: 'Напрям відхилення (дорожче чи дешевше)',
  log_ratio: 'У скільки разів ціна відрізняється від медіани',
  is_noise: 'Незвичне поєднання ціни, обсягу й дати',
}

export type Contribution = { feature: string; label: string; value: number; points: number }

// значення ознаки людською мовою (логарифмічні ознаки — назад у звичайні одиниці)
function valueText(c: Contribution): string {
  const v = c.value
  switch (c.feature) {
    case 'abs_z':
      return `у ${num(Math.abs(v))} раза більше за звичайний розкид`
    case 'z':
      return v >= 0 ? 'дорожче за типові ціни групи' : 'дешевше за типові ціни групи'
    case 'log_ratio': {
      const r = Math.exp(v)
      return r >= 1 ? `×${num(r)} вище медіани` : `×${num(1 / r)} нижче медіани`
    }
    case 'log_group_size':
      return `${Math.round(Math.exp(v))} поз.`
    case 'log_qty':
      return `${Math.round(Math.exp(v)).toLocaleString('uk-UA')} од.`
    case 'group_spread':
      return `±${Math.round(v * 100)} %`
    case 'text_dist':
      return v < 0.35 ? 'типовий опис' : v < 0.65 ? 'помітно відрізняється' : 'сильно відрізняється'
    case 'pack_mismatch':
      return v >= 9 ? 'не застосовно' : v < 0.3 ? 'так' : 'ні'
    default:
      return v >= 0.5 ? 'так' : 'ні'
  }
}

/**
 * Внески ознак у ризик позиції (значення Шеплі): смуга праворуч — підвищує ризик, ліворуч — знижує.
 * Сума внесків ≈ ризик позиції мінус середній ризик звичайних позицій.
 */
export default function Contributions({ items }: { items: Contribution[] }) {
  const max = Math.max(1, ...items.map((c) => Math.abs(c.points)))
  return (
    <ul className="space-y-2.5">
      {items.map((c, i) => {
        const up = c.points > 0
        const w = `${(50 * Math.abs(c.points)) / max}%`
        return (
          <li key={c.feature} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm">
            <div className="min-w-0">
              <div className="truncate">{LABELS[c.feature] ?? c.label}</div>
              <div className="truncate text-xs text-muted-foreground">{valueText(c)}</div>
            </div>
            <div className="relative h-2.5 rounded-full bg-muted">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <motion.span
                className={cn('absolute inset-y-0 rounded-full', up ? 'left-1/2 bg-critical/80' : 'right-1/2 bg-success/80')}
                initial={{ width: 0 }}
                animate={{ width: w }}
                transition={{ duration: 0.5, delay: i * 0.03 }}
              />
            </div>
            <span
              className={cn('text-right text-xs font-medium tabular', up ? 'text-critical' : 'text-success')}
              title={`${up ? 'Підвищує' : 'Знижує'} ризик на ${Math.abs(c.points).toFixed(0)} пунктів зі 100`}
            >
              {up ? '+' : '−'}
              {Math.abs(c.points).toFixed(0)}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
