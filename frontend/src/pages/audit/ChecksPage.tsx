import { Checkbox, Select, Space, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import ItemDrawer from './ItemDrawer'
import { VERDICT_REASON, VERDICT_STATUS, type Verdict, type VerdictReason, type VerdictStatus } from './verdicts'

const PAGE = 20

/** A3.3: історія перевірок — усі вердикти з фільтрами. */
export default function ChecksPage() {
  const [status, setStatus] = useState<VerdictStatus | undefined>()
  const [reason, setReason] = useState<VerdictReason | undefined>()
  const [mine, setMine] = useState(false)
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<{ key: string; total: number; items: Verdict[] } | null>(null)
  const [opened, setOpened] = useState<number | null>(null)
  const key = `${status}|${reason}|${mine}|${page}|${reload}`

  useEffect(() => {
    let alive = true
    const p = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE), mine: String(mine) })
    if (status) p.set('status_', status)
    if (reason) p.set('reason', reason)
    api<{ total: number; items: Verdict[] }>(`/verdicts?${p}`).then((r) => alive && setData({ key, ...r }))
    return () => {
      alive = false
    }
  }, [status, reason, mine, page, key])

  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v)
    setPage(1)
  }

  return (
    <>
      <Space style={{ width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <Typography.Title level={3}>Історія перевірок</Typography.Title>
        <Space wrap>
          <Select
            allowClear
            placeholder="Висновок"
            style={{ width: 210 }}
            value={status}
            onChange={reset(setStatus)}
            options={(Object.keys(VERDICT_STATUS) as VerdictStatus[]).map((s) => ({ value: s, label: VERDICT_STATUS[s].label }))}
          />
          <Select
            allowClear
            placeholder="Причина"
            style={{ width: 220 }}
            value={reason}
            onChange={reset(setReason)}
            options={(Object.keys(VERDICT_REASON) as VerdictReason[]).map((r) => ({ value: r, label: VERDICT_REASON[r] }))}
          />
          <Checkbox checked={mine} onChange={(e) => reset(setMine)(e.target.checked)}>
            лише мої
          </Checkbox>
        </Space>
      </Space>
      <Table<Verdict>
        rowKey="id"
        size="small"
        loading={data?.key !== key}
        dataSource={data?.items ?? []}
        scroll={{ x: 1000 }}
        onRow={(v) => ({ onClick: () => setOpened(v.item_id), style: { cursor: 'pointer' } })}
        pagination={{ current: page, pageSize: PAGE, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: 'Змінено', dataIndex: 'updated_at', width: 130, render: (d: string) => dayjs(d).format('DD.MM.YY HH:mm') },
          { title: 'Висновок', dataIndex: 'status', width: 190, render: (s: VerdictStatus) => <Tag color={VERDICT_STATUS[s].color}>{VERDICT_STATUS[s].label}</Tag> },
          { title: 'Причина', dataIndex: 'reason', width: 190, render: (r: VerdictReason) => VERDICT_REASON[r] },
          { title: 'Предмет', dataIndex: 'description', ellipsis: true },
          { title: 'Ціна', width: 130, render: (_, v) => `${Number(v.unit_price_base).toLocaleString('uk-UA')} грн/${v.base_unit_code}` },
          { title: 'Замовник', dataIndex: 'entity_name', ellipsis: true },
          { title: 'Аудитор', dataIndex: 'user_name', width: 170, ellipsis: true },
        ]}
      />
      <ItemDrawer itemId={opened} onClose={() => setOpened(null)} onSaved={() => setReload((n) => n + 1)} />
    </>
  )
}
