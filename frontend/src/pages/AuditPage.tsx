import { Select, Space, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Entry = {
  id: number
  user_email: string | null
  action: string
  entity: string
  entity_key: string | null
  payload: Record<string, unknown> | null
  ip: string | null
  created_at: string
}

const ACTION_COLORS: Record<string, string> = {
  LOGIN: 'green',
  LOGOUT: 'default',
  LOGIN_FAILED: 'red',
  INSERT: 'blue',
  UPDATE: 'gold',
  DELETE: 'volcano',
}

const PAGE = 20

export default function AuditPage() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState<string | undefined>()
  const [data, setData] = useState<{ key: string; total: number; items: Entry[] } | null>(null)
  const key = `${page}|${action ?? ''}`

  useEffect(() => {
    let alive = true
    const params = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE) })
    if (action) params.set('action', action)
    api<{ total: number; items: Entry[] }>(`/audit-log?${params}`).then((r) => alive && setData({ key, ...r }))
    return () => {
      alive = false
    }
  }, [page, action, key])

  return (
    <>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3}>Журнал аудиту</Typography.Title>
        <Select
          allowClear
          placeholder="Усі дії"
          style={{ width: 200 }}
          value={action}
          onChange={(v) => {
            setAction(v)
            setPage(1)
          }}
          options={Object.keys(ACTION_COLORS).map((a) => ({ value: a, label: a }))}
        />
      </Space>
      <Table<Entry>
        rowKey="id"
        size="small"
        loading={data?.key !== key}
        dataSource={data?.items ?? []}
        scroll={{ x: 900 }}
        pagination={{ current: page, pageSize: PAGE, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: 'Час', dataIndex: 'created_at', width: 150, render: (d: string) => dayjs(d).format('DD.MM.YY HH:mm:ss') },
          { title: 'Користувач', dataIndex: 'user_email', render: (e: string | null) => e ?? <Tag>система</Tag> },
          { title: 'Дія', dataIndex: 'action', render: (a: string) => <Tag color={ACTION_COLORS[a]}>{a}</Tag> },
          { title: "Об'єкт", render: (_, e) => `${e.entity}${e.entity_key ? ` #${e.entity_key}` : ''}` },
          {
            title: 'Зміни',
            dataIndex: 'payload',
            render: (p: Entry['payload']) =>
              p ? <code style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{JSON.stringify(p)}</code> : null,
          },
          { title: 'IP', dataIndex: 'ip', width: 120 },
        ]}
      />
    </>
  )
}
