import { LoaderCircle, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { Page, PageHeader, Panel } from '@/components/page'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { dateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

type Config = { key: string; value: Record<string, unknown>; description: string | null; updated_at: string }

function ConfigPanel({ cfg, onSaved }: { cfg: Config; onSaved: (c: Config) => void }) {
  const initial = JSON.stringify(cfg.value, null, 2)
  const [text, setText] = useState(initial)
  const [saving, setSaving] = useState(false)
  let parseError: string | null = null
  try {
    JSON.parse(text)
  } catch (e) {
    parseError = (e as Error).message
  }
  const dirty = text !== initial

  const save = async () => {
    setSaving(true)
    try {
      onSaved(await api<Config>(`/settings/${cfg.key}`, { method: 'PUT', body: JSON.stringify({ value: JSON.parse(text) }) }))
      toast.success('Параметри збережено')
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Panel title={<code className="font-mono text-sm">{cfg.key}</code>} description={`змінено ${dateTime(cfg.updated_at)}`}>
      {cfg.description && <p className="mb-3 text-sm text-muted-foreground">{cfg.description}</p>}
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        className={cn('min-h-40 font-mono text-xs leading-relaxed', parseError && 'border-critical focus-visible:ring-critical/30')}
      />
      {parseError && <p className="mt-2 text-xs text-critical">Некоректний JSON: {parseError}</p>}
      <div className="mt-3 flex gap-2">
        <Button onClick={save} disabled={!dirty || !!parseError || saving}>
          {saving && <LoaderCircle className="animate-spin" />}
          Зберегти
        </Button>
        {dirty && (
          <Button variant="ghost" onClick={() => setText(initial)}>
            <RotateCcw /> Скасувати зміни
          </Button>
        )}
      </div>
    </Panel>
  )
}

export default function SettingsPage() {
  const [items, setItems] = useState<Config[] | null>(null)

  useEffect(() => {
    api<Config[]>('/settings').then(setItems)
  }, [])

  return (
    <Page className="max-w-4xl">
      <PageHeader
        eyebrow="Адміністрування"
        title="Параметри аналізу"
        description="Значення за замовчуванням для виявлення аномалій. Кожна зміна фіксується в журналі аудиту; готові результати інших параметрів залишаються в кеші."
      />
      <div className="space-y-4">
        {items === null ? <Skeleton className="h-64" /> : items.map((c) => (
          <ConfigPanel key={`${c.key}|${c.updated_at}`} cfg={c} onSaved={(n) => setItems((l) => l?.map((x) => (x.key === n.key ? n : x)) ?? null)} />
        ))}
      </div>
    </Page>
  )
}
