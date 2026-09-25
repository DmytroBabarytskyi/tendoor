import { App, Button, Card, DatePicker, Form, Progress, Select, Table, Tag, Typography } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'

type Job = {
  id: number
  status: 'queued' | 'running' | 'done' | 'failed'
  date_from: string
  date_to: string
  cpv_prefixes: string[]
  categories: string[]
  scanned: number
  saved: number
  normalized: number
  errors: number
  message: string | null
  created_at: string
  finished_at: string | null
}

type Values = { period: [Dayjs, Dayjs]; cpv_prefixes: string[]; categories: string[] }

const STATUS: Record<Job['status'], { color: string; label: string }> = {
  queued: { color: 'default', label: 'у черзі' },
  running: { color: 'processing', label: 'виконується' },
  done: { color: 'success', label: 'завершено' },
  failed: { color: 'error', label: 'помилка' },
}

const CATEGORIES = [
  { value: 'goods', label: 'Товари' },
  { value: 'services', label: 'Послуги' },
  { value: 'works', label: 'Роботи' },
]

// приблизно 25 тис. змін у фіді Prozorro за добу — для оцінки прогресу
const FEED_PER_DAY = 25000

export default function SyncPage() {
  const { message } = App.useApp()
  const [jobs, setJobs] = useState<Job[]>([])
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(() => {
    api<Job[]>('/sync/jobs').then(setJobs)
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [load])

  const submit = async ({ period, cpv_prefixes, categories }: Values) => {
    setSubmitting(true)
    try {
      await api('/sync/jobs', {
        method: 'POST',
        body: JSON.stringify({
          date_from: period[0].format('YYYY-MM-DD'),
          date_to: period[1].format('YYYY-MM-DD'),
          cpv_prefixes,
          categories,
        }),
      })
      message.success('Завдання поставлено в чергу')
      load()
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Typography.Title level={3}>Синхронізація з Prozorro</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Form<Values>
          layout="inline"
          onFinish={submit}
          initialValues={{ categories: ['goods'], cpv_prefixes: [], period: [dayjs().subtract(1, 'day'), dayjs().subtract(1, 'day')] }}
        >
          <Form.Item name="period" label="Період змін" rules={[{ required: true }]}>
            <DatePicker.RangePicker format="DD.MM.YYYY" disabledDate={(d) => d.isAfter(dayjs(), 'day')} />
          </Form.Item>
          <Form.Item name="cpv_prefixes" label="Коди ДК 021 (префікси)">
            <Select mode="tags" style={{ minWidth: 220 }} placeholder="напр. 15, 0322" tokenSeparators={[',', ' ']} />
          </Form.Item>
          <Form.Item name="categories" label="Категорії">
            <Select mode="multiple" options={CATEGORIES} style={{ minWidth: 200 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting}>
              Запустити
            </Button>
          </Form.Item>
        </Form>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          Період визначає дату зміни документа в Prozorro. Одна доба — близько 25 тис. змін і ~10 хвилин обробки.
        </Typography.Paragraph>
      </Card>
      <Table<Job>
        rowKey="id"
        dataSource={jobs}
        pagination={false}
        scroll={{ x: 900 }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          {
            title: 'Період',
            render: (_, j) => `${dayjs(j.date_from).format('DD.MM')} – ${dayjs(j.date_to).format('DD.MM.YYYY')}`,
          },
          { title: 'CPV', dataIndex: 'cpv_prefixes', render: (c: string[]) => (c.length ? c.join(', ') : 'усі') },
          {
            title: 'Статус',
            dataIndex: 'status',
            render: (s: Job['status'], j) => (
              <Tag color={STATUS[s].color} title={j.message ?? undefined}>
                {STATUS[s].label}
              </Tag>
            ),
          },
          {
            title: 'Прогрес',
            render: (_, j) => {
              const days = dayjs(j.date_to).diff(dayjs(j.date_from), 'day') + 1
              const pct = j.status === 'done' ? 100 : Math.min(99, Math.round((100 * j.scanned) / (days * FEED_PER_DAY)))
              return <Progress percent={pct} size="small" status={j.status === 'failed' ? 'exception' : undefined} />
            },
          },
          { title: 'Переглянуто', dataIndex: 'scanned', align: 'right' },
          { title: 'Збережено', dataIndex: 'saved', align: 'right' },
          { title: 'Помилок', dataIndex: 'errors', align: 'right' },
        ]}
      />
    </>
  )
}
