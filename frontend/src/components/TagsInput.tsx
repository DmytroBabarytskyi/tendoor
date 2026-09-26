import { X } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

/** Поле-теги: значення розділяються Enter, комою або пробілом; Backspace прибирає останнє. */
export default function TagsInput({
  value,
  onChange,
  placeholder,
  validate,
  id,
  className,
}: {
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
  validate?: (s: string) => boolean
  id?: string
  className?: string
}) {
  const [text, setText] = useState('')
  const commit = (raw: string) => {
    const parts = raw.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean)
    const next = parts.filter((p) => !value.includes(p) && (!validate || validate(p)))
    if (next.length) onChange([...value, ...next])
    setText('')
  }
  return (
    <div
      className={cn(
        'flex min-h-9 w-full flex-wrap items-center gap-1 rounded-md border border-input bg-transparent px-2 py-1 text-sm shadow-xs focus-within:ring-[3px] focus-within:ring-ring/50',
        className,
      )}
    >
      {value.map((v) => (
        <span key={v} className="inline-flex items-center gap-1 rounded bg-secondary py-0.5 pr-0.5 pl-1.5 font-mono text-xs">
          {v}
          <button type="button" className="rounded p-0.5 text-muted-foreground hover:text-foreground" onClick={() => onChange(value.filter((x) => x !== v))} aria-label={`Прибрати ${v}`}>
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={text}
        onChange={(e) => (/[\s,;]$/.test(e.target.value) ? commit(e.target.value) : setText(e.target.value))}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            commit(text)
          } else if (e.key === 'Backspace' && !text && value.length) onChange(value.slice(0, -1))
        }}
        onBlur={() => text && commit(text)}
        placeholder={value.length ? '' : placeholder}
        className="min-w-24 flex-1 bg-transparent py-0.5 outline-none placeholder:text-muted-foreground"
      />
    </div>
  )
}
