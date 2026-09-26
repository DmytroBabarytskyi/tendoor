import { motion } from 'motion/react'

/** Горизонтальні смуги для частки категорій (один колір — одна величина; підписи й значення — текстом). */
export default function BarList({ rows }: { rows: { key: string; label: string; value: number; hint?: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  const total = rows.reduce((a, r) => a + r.value, 0) || 1
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={r.key}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate">
              {r.label}
              {r.hint && <span className="ml-1.5 font-mono text-xs text-muted-foreground">{r.hint}</span>}
            </span>
            <span className="shrink-0 tabular text-muted-foreground">
              <span className="font-medium text-foreground">{r.value.toLocaleString('uk-UA')}</span> · {Math.round((100 * r.value) / total)} %
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full bg-primary/80"
              initial={{ width: 0 }}
              animate={{ width: `${(100 * r.value) / max}%` }}
              transition={{ duration: 0.7, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
