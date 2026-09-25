import { Alert, Card, Col, Row, Statistic, Table, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Stats = {
  tenders: number
  items: number
  items_priced: number
  entities: number
  raw_documents: number
  date_min: string | null
  date_max: string | null
  by_price_source: Record<string, number>
  top_units: { code: string; name: string | null; n: number }[]
}

const SOURCE_NAMES: Record<string, string> = {
  unit_value: 'явна ціна за одиницю',
  contract: 'з договору',
  expected: 'з очікуваної вартості',
  None: 'не визначено',
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Stats>('/procurement/stats').then(setStats, (e: Error) => setError(e.message))
  }, [])

  if (error) return <Alert type="error" message={error} />
  const period =
    stats?.date_min && stats.date_max
      ? `${dayjs(stats.date_min).format('DD.MM.YYYY')} – ${dayjs(stats.date_max).format('DD.MM.YYYY')}`
      : '—'

  return (
    <>
      <Typography.Title level={3}>Огляд бази закупівель</Typography.Title>
      <Row gutter={[16, 16]}>
        {[
          ['Тендерів', stats?.tenders],
          ['Позицій', stats?.items],
          ['Позицій з ціною', stats?.items_priced],
          ['Замовників', stats?.entities],
        ].map(([title, value]) => (
          <Col xs={12} md={6} key={title as string}>
            <Card loading={!stats}>
              <Statistic title={title as string} value={value as number} groupSeparator=" " />
            </Card>
          </Col>
        ))}
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="Джерело ціни за одиницю" loading={!stats} extra={`Період оголошення: ${period}`}>
            <Table
              size="small"
              pagination={false}
              rowKey="source"
              dataSource={Object.entries(stats?.by_price_source ?? {}).map(([source, n]) => ({ source, n }))}
              columns={[
                { title: 'Джерело', dataIndex: 'source', render: (s: string) => SOURCE_NAMES[s] ?? s },
                { title: 'Позицій', dataIndex: 'n', align: 'right' },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Базові одиниці виміру (позиції з ціною)" loading={!stats}>
            <Table
              size="small"
              pagination={false}
              rowKey="code"
              dataSource={stats?.top_units ?? []}
              columns={[
                { title: 'Код', dataIndex: 'code' },
                { title: 'Назва', dataIndex: 'name' },
                { title: 'Позицій', dataIndex: 'n', align: 'right' },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </>
  )
}
