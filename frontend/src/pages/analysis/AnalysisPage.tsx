import { ExperimentOutlined } from '@ant-design/icons'
import { App, Button, Card, Col, DatePicker, Empty, Form, Row, Select, Spin, Table, Tag, Typography } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../../api/client'
import HomogeneityCard from './HomogeneityCard'
import { STATUS, type AnalysisRequest, type Preview } from './types'

type CpvOption = { code: string; description: string; level: number; n: number }
type Values = { cpv: string[]; period: [Dayjs, Dayjs]; units: string[] }

const prefix = (code: string) => code.replace(/0+$/, '').padEnd(2, '0')

export default function AnalysisPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [form] = Form.useForm<Values>()
  const [cpvOptions, setCpvOptions] = useState<CpvOption[]>([])
  const [cpvQuery, setCpvQuery] = useState('')
  const [preview, setPreview] = useState<{ key: string; data: Preview } | null>(null)
  const [requests, setRequests] = useState<AnalysisRequest[]>([])
  const [submitting, setSubmitting] = useState(false)
  const values = Form.useWatch([], form)

  useEffect(() => {
    const t = setTimeout(() => {
      api<CpvOption[]>(`/analysis/cpv?q=${encodeURIComponent(cpvQuery)}`).then(setCpvOptions)
    }, 250)
    return () => clearTimeout(t)
  }, [cpvQuery])

  useEffect(() => {
    const load = () => api<AnalysisRequest[]>('/analysis/requests').then(setRequests)
    load()
    const timer = setInterval(load, 4000)
    return () => clearInterval(timer)
  }, [])

  const selection = useMemo(() => {
    if (!values?.cpv?.length || !values.period?.[0] || !values.period?.[1]) return null
    return {
      cpv_prefixes: values.cpv.map(prefix),
      date_from: values.period[0].format('YYYY-MM-DD'),
      date_to: values.period[1].format('YYYY-MM-DD'),
      unit_codes: values.units ?? [],
    }
  }, [values])
  const selectionKey = selection ? JSON.stringify(selection) : ''

  // A2.1: оцінка однорідності одразу під час вибору категорій
  useEffect(() => {
    if (!selection) return
    let alive = true
    const t = setTimeout(() => {
      api<Preview>('/analysis/preview', { method: 'POST', body: JSON.stringify(selection) })
        .then((data) => alive && setPreview({ key: selectionKey, data }))
        .catch((e: Error) => alive && message.error(e.message))
    }, 400)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [selection, selectionKey, message])

  const current = preview && preview.key === selectionKey ? preview.data : null
  const loadingPreview = !!selection && !current

  const submit = async () => {
    if (!selection) return
    setSubmitting(true)
    try {
      const r = await api<AnalysisRequest>('/analysis/requests', { method: 'POST', body: JSON.stringify(selection) })
      message.success(r.from_cache ? 'Результат уже є — відкрито з кешу' : 'Модель навчається на вибірці')
      navigate(`/analysis/${r.id}`)
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Typography.Title level={3}>Виявлення аномальних цінових пропозицій</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Вибірка для аналізу">
            <Form<Values>
              form={form}
              layout="vertical"
              initialValues={{ period: [dayjs().subtract(30, 'day'), dayjs()], units: [] }}
            >
              <Form.Item
                name="cpv"
                label="Категорії ДК 021"
                extra="Чим менший розкид категорій, тим точніша детекція."
                rules={[{ required: true, message: 'Оберіть хоча б одну категорію' }]}
              >
                <Select
                  mode="multiple"
                  showSearch
                  filterOption={false}
                  onSearch={setCpvQuery}
                  placeholder="Почніть вводити назву або код, напр. «картопля» чи 1531"
                  options={cpvOptions.map((o) => ({
                    value: o.code,
                    label: `${o.code} ${o.description} (${o.n})`,
                  }))}
                />
              </Form.Item>
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item name="period" label="Період оголошення">
                    <DatePicker.RangePicker format="DD.MM.YYYY" style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="units" label="Одиниці виміру">
                    <Select
                      mode="multiple"
                      placeholder="усі"
                      options={(current?.units ?? []).map((u) => ({ value: u.code, label: `${u.code} (${u.n})` }))}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Button
                type="primary"
                icon={<ExperimentOutlined />}
                disabled={!current || current.n_items === 0 || current.too_large}
                loading={submitting}
                onClick={submit}
              >
                Виявити аномалії
              </Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Оцінка вибірки">
            {!selection && <Empty description="Оберіть категорії та період" />}
            {loadingPreview && <Spin />}
            {current && <HomogeneityCard h={current.homogeneity} nItems={current.n_items} />}
          </Card>
        </Col>
      </Row>

      <Card title="Мої аналізи" style={{ marginTop: 16 }}>
        <Table<AnalysisRequest>
          rowKey="id"
          size="small"
          dataSource={requests}
          pagination={false}
          scroll={{ x: 700 }}
          onRow={(r) => ({ onClick: () => navigate(`/analysis/${r.id}`), style: { cursor: 'pointer' } })}
          columns={[
            { title: '№', dataIndex: 'id', width: 60 },
            { title: 'ДК 021', dataIndex: 'cpv_prefixes', render: (c: string[]) => c.join(', ') },
            {
              title: 'Період',
              render: (_, r) => `${dayjs(r.date_from).format('DD.MM.YY')} – ${dayjs(r.date_to).format('DD.MM.YY')}`,
            },
            {
              title: 'Однорідність',
              dataIndex: 'homogeneity',
              render: (h: number | null) => (h == null ? '—' : `${Math.round(h * 100)} %`),
            },
            {
              title: 'Статус',
              render: (_, r) => (
                <>
                  <Tag color={STATUS[r.status].color}>{STATUS[r.status].label}</Tag>
                  {r.from_cache && <Tag>з кешу</Tag>}
                </>
              ),
            },
            { title: 'Створено', dataIndex: 'created_at', render: (d: string) => dayjs(d).format('DD.MM HH:mm') },
          ]}
        />
      </Card>
    </>
  )
}
