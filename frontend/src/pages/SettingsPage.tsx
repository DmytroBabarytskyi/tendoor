import { App, Button, Card, Input, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Config = { key: string; value: Record<string, unknown>; description: string | null; updated_at: string }

function ConfigCard({ cfg, onSaved }: { cfg: Config; onSaved: (c: Config) => void }) {
  const { message } = App.useApp()
  const [text, setText] = useState(JSON.stringify(cfg.value, null, 2))
  const [saving, setSaving] = useState(false)

  const save = async () => {
    let value: unknown
    try {
      value = JSON.parse(text)
    } catch {
      message.error('Некоректний JSON')
      return
    }
    setSaving(true)
    try {
      onSaved(await api<Config>(`/settings/${cfg.key}`, { method: 'PUT', body: JSON.stringify({ value }) }))
      message.success('Параметри збережено')
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card
      title={<code>{cfg.key}</code>}
      extra={<Typography.Text type="secondary">змінено {dayjs(cfg.updated_at).format('DD.MM.YYYY HH:mm')}</Typography.Text>}
    >
      <Typography.Paragraph>{cfg.description}</Typography.Paragraph>
      <Input.TextArea
        value={text}
        onChange={(e) => setText(e.target.value)}
        autoSize={{ minRows: 3 }}
        style={{ fontFamily: 'Consolas, monospace' }}
      />
      <Button type="primary" onClick={save} loading={saving} style={{ marginTop: 12 }}>
        Зберегти
      </Button>
    </Card>
  )
}

export default function SettingsPage() {
  const [items, setItems] = useState<Config[]>([])

  useEffect(() => {
    api<Config[]>('/settings').then(setItems)
  }, [])

  return (
    <>
      <Typography.Title level={3}>Параметри аналізу</Typography.Title>
      <Typography.Paragraph type="secondary">
        Значення за замовчуванням для конвеєра виявлення аномалій. Кожна зміна фіксується в журналі аудиту.
      </Typography.Paragraph>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {items.map((c) => (
          <ConfigCard key={c.key} cfg={c} onSaved={(n) => setItems((l) => l.map((x) => (x.key === n.key ? n : x)))} />
        ))}
      </Space>
    </>
  )
}
