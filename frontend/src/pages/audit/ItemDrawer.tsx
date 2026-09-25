import { LinkOutlined } from '@ant-design/icons'
import { Alert, App, Button, Descriptions, Drawer, Empty, Form, Input, Radio, Select, Spin, Table, Tag, Timeline, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/context'
import { VERDICT_REASON, VERDICT_STATUS, type Verdict, type VerdictHistory, type VerdictReason, type VerdictStatus } from './verdicts'

type Card = {
  item: {
    item_id: number
    description: string
    quantity: number
    unit_name: string | null
    unit_code: string
    unit_price: number | null
    unit_price_base: number
    base_unit_code: string
    price_source: string
    cpv_code: string
    cpv_description: string | null
    tender_code: string
    tender_title: string | null
    method_type: string
    date_published: string
    entity_name: string
    entity_edrpou: string
    entity_region: string | null
    supplier_name: string | null
    contract_amount: number | null
  }
  result: { result_id: number; risk_score: number | null; median_price: number | null; explanation: string; is_anomaly: boolean } | null
  analogs: { item_id: number; description: string; unit_price_base: number; quantity_base: number; entity_name: string; entity_region: string | null }[]
  verdict: Verdict | null
}

type Values = { status: VerdictStatus; reason: VerdictReason; comment?: string }

const money = (v: number | null | undefined) => (v == null ? '—' : Number(v).toLocaleString('uk-UA', { maximumFractionDigits: 2 }))
const SOURCE: Record<string, string> = { unit_value: 'явна ціна за одиницю', contract: 'з договору', expected: 'з очікуваної вартості' }

export default function ItemDrawer({ itemId, runId, onClose, onSaved }: {
  itemId: number | null
  runId?: number | null
  onClose: () => void
  onSaved?: (v: Verdict) => void
}) {
  const { message } = App.useApp()
  const { hasRole } = useAuth()
  const [card, setCard] = useState<{ id: number; data: Card } | null>(null)
  const [history, setHistory] = useState<VerdictHistory[]>([])
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm<Values>()
  const canJudge = hasRole('admin', 'auditor')

  useEffect(() => {
    if (itemId == null) return
    let alive = true
    const q = runId ? `?run_id=${runId}` : ''
    Promise.all([api<Card>(`/items/${itemId}${q}`), api<VerdictHistory[]>(`/items/${itemId}/verdict-history`)]).then(
      ([c, h]) => {
        if (!alive) return
        setCard({ id: itemId, data: c })
        setHistory(h)
        form.setFieldsValue(
          c.verdict
            ? { status: c.verdict.status, reason: c.verdict.reason, comment: c.verdict.comment ?? undefined }
            : { status: undefined, reason: undefined, comment: undefined },
        )
      },
    )
    return () => {
      alive = false
    }
  }, [itemId, runId, form])

  const data = card && card.id === itemId ? card.data : null

  const save = async (values: Values) => {
    if (itemId == null) return
    setSaving(true)
    try {
      const v = await api<Verdict>(`/items/${itemId}/verdict`, {
        method: 'PUT',
        body: JSON.stringify({ ...values, result_id: data?.result?.result_id ?? null }),
      })
      message.success('Вердикт збережено')
      setHistory(await api<VerdictHistory[]>(`/items/${itemId}/verdict-history`))
      onSaved?.(v)
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const it = data?.item
  return (
    <Drawer open={itemId != null} onClose={onClose} width={720} title="Розгляд лоту" destroyOnHidden>
      {!data || !it ? (
        <Spin />
      ) : (
        <>
          {data.result && (
            <Alert
              type={data.result.is_anomaly ? 'error' : 'info'}
              showIcon
              style={{ marginBottom: 16 }}
              message={data.result.is_anomaly ? `Аномалія, ризик ${Math.round(data.result.risk_score ?? 0)}` : 'Звичайна ціна'}
              description={data.result.explanation}
            />
          )}
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="Предмет">{it.description}</Descriptions.Item>
            <Descriptions.Item label="Ціна">
              {money(it.unit_price_base)} грн/{it.base_unit_code}
              {it.unit_code !== it.base_unit_code && ` (у документі: ${money(it.unit_price)} грн/${it.unit_name ?? it.unit_code})`}
              <Typography.Text type="secondary"> · {SOURCE[it.price_source] ?? it.price_source}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Обсяг">{money(it.quantity)} {it.unit_name ?? it.unit_code}</Descriptions.Item>
            <Descriptions.Item label="Код ДК 021">{it.cpv_code} {it.cpv_description}</Descriptions.Item>
            <Descriptions.Item label="Замовник">
              {it.entity_name} ({it.entity_edrpou}){it.entity_region && `, ${it.entity_region}`}
            </Descriptions.Item>
            {it.supplier_name && (
              <Descriptions.Item label="Постачальник">
                {it.supplier_name}, договір {money(it.contract_amount)} грн
              </Descriptions.Item>
            )}
            <Descriptions.Item label="Закупівля">
              <a href={`https://prozorro.gov.ua/tender/${it.tender_code}`} target="_blank" rel="noreferrer">
                {it.tender_code} <LinkOutlined />
              </a>{' '}
              · {it.method_type} · {dayjs(it.date_published).format('DD.MM.YYYY')}
            </Descriptions.Item>
          </Descriptions>

          <Typography.Title level={5} style={{ marginTop: 20 }}>
            Аналоги з тієї ж групи (найближчі до медіани {money(data.result?.median_price)} грн)
          </Typography.Title>
          {data.analogs.length ? (
            <Table
              size="small"
              rowKey="item_id"
              pagination={false}
              dataSource={data.analogs}
              columns={[
                { title: 'Предмет', dataIndex: 'description', ellipsis: true },
                { title: 'Ціна', dataIndex: 'unit_price_base', align: 'right', render: money, width: 100 },
                { title: 'Замовник', dataIndex: 'entity_name', ellipsis: true },
              ]}
            />
          ) : (
            <Empty description="Немає даних про групу" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}

          <Typography.Title level={5} style={{ marginTop: 20 }}>
            Вердикт
          </Typography.Title>
          <Form form={form} layout="vertical" onFinish={save} disabled={!canJudge}>
            <Form.Item name="status" rules={[{ required: true, message: 'Оберіть висновок' }]}>
              <Radio.Group optionType="button" buttonStyle="solid">
                {(Object.keys(VERDICT_STATUS) as VerdictStatus[]).map((s) => (
                  <Radio.Button key={s} value={s}>
                    {VERDICT_STATUS[s].label}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>
            <Form.Item name="reason" label="Причина" rules={[{ required: true, message: 'Оберіть причину' }]}>
              <Select options={(Object.keys(VERDICT_REASON) as VerdictReason[]).map((r) => ({ value: r, label: VERDICT_REASON[r] }))} />
            </Form.Item>
            <Form.Item name="comment" label="Коментар">
              <Input.TextArea autoSize={{ minRows: 2 }} maxLength={2000} showCount />
            </Form.Item>
            {canJudge && (
              <Button type="primary" htmlType="submit" loading={saving}>
                Зберегти вердикт
              </Button>
            )}
          </Form>

          {history.length > 0 && (
            <>
              <Typography.Title level={5} style={{ marginTop: 20 }}>
                Історія
              </Typography.Title>
              <Timeline
                items={history.map((h) => ({
                  children: (
                    <>
                      <Tag color={VERDICT_STATUS[h.new_status].color}>{VERDICT_STATUS[h.new_status].label}</Tag>
                      {VERDICT_REASON[h.new_reason]} · {h.user_name ?? h.user_email ?? 'система'} ·{' '}
                      {dayjs(h.changed_at).format('DD.MM.YYYY HH:mm')}
                      {h.comment && <div style={{ color: '#52514e' }}>{h.comment}</div>}
                    </>
                  ),
                }))}
              />
            </>
          )}
        </>
      )}
    </Drawer>
  )
}
