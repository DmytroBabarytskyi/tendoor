import { ArrowLeftOutlined, DownloadOutlined, LinkOutlined } from '@ant-design/icons'
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Result,
  Row,
  Segmented,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
  Tooltip,
} from 'antd'
import dayjs from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { api, download } from '../../api/client'
import Chart from '../../components/Chart'
import ItemDrawer from '../audit/ItemDrawer'
import { VERDICT_STATUS, type VerdictStatus } from '../audit/verdicts'
import { pcaOption, priceVolumeOption, type Point } from './charts'
import HomogeneityCard from './HomogeneityCard'
import { STATUS, type AnalysisRequest, type AnomalyRow, type Category } from './types'

const PAGE = 20
const money = (v: number | null) => (v == null ? '—' : Number(v).toLocaleString('uk-UA', { maximumFractionDigits: 2 }))

function riskTag(risk: number | null) {
  if (risk == null) return '—'
  const r = Math.round(risk)
  const [color, label] = r >= 80 ? ['red', 'високий'] : r >= 50 ? ['orange', 'середній'] : ['default', 'низький']
  return <Tag color={color}>{`${r} · ${label}`}</Tag>
}

export default function ResultPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [req, setReq] = useState<AnalysisRequest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cats, setCats] = useState<Category[]>([])
  const [catId, setCatId] = useState<number | null>(null)
  const [points, setPoints] = useState<{ cat: number; data: Point[] } | null>(null)
  const [view, setView] = useState<'price' | 'pca'>('price')
  const [page, setPage] = useState(1)
  const [rows, setRows] = useState<{ key: string; total: number; items: AnomalyRow[] } | null>(null)
  const [opened, setOpened] = useState<number | null>(null)
  const [reloadRows, setReloadRows] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const { message } = App.useApp()

  // поки модель навчається — опитування статусу
  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const load = () =>
      api<AnalysisRequest>(`/analysis/requests/${id}`).then(
        (r) => {
          if (!alive) return
          setReq(r)
          if (r.status === 'queued' || r.status === 'running') timer = setTimeout(load, 2000)
        },
        (e: Error) => alive && setError(e.message),
      )
    load()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [id])

  const done = req?.status === 'done'

  useEffect(() => {
    if (!done) return
    api<Category[]>(`/analysis/requests/${id}/categories`).then((c) => {
      setCats(c)
      const first = c.filter((x) => x.analysed).sort((a, b) => b.n_anomalies - a.n_anomalies)[0]
      setCatId(first?.id ?? null)
    })
  }, [done, id])

  useEffect(() => {
    if (!done || catId == null) return
    let alive = true
    api<Point[]>(`/analysis/requests/${id}/points?category_id=${catId}`).then((d) => alive && setPoints({ cat: catId, data: d }))
    return () => {
      alive = false
    }
  }, [done, id, catId])

  const rowsKey = `${page}|${catId ?? ''}|${reloadRows}`
  useEffect(() => {
    if (!done) return
    let alive = true
    const params = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE) })
    api<{ total: number; items: AnomalyRow[] }>(`/analysis/requests/${id}/anomalies?${params}`).then(
      (r) => alive && setRows({ key: rowsKey, ...r }),
    )
    return () => {
      alive = false
    }
  }, [done, id, page, rowsKey])

  const cat = cats.find((c) => c.id === catId)
  const option = useMemo(() => {
    if (!cat || !points || points.cat !== cat.id) return null
    return view === 'price'
      ? priceVolumeOption(points.data, cat.base_unit_code, cat.median_price ?? undefined)
      : pcaOption(points.data, cat.base_unit_code)
  }, [cat, points, view])

  if (error) return <Result status="404" title={error} />
  if (!req) return <Spin />

  const m = req.run?.metrics
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analysis')}>
          До вибірки
        </Button>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Аналіз №{req.id}: ДК 021 {req.cpv_prefixes.join(', ')}
        </Typography.Title>
        <Tag color={STATUS[req.status].color}>{STATUS[req.status].label}</Tag>
        {req.from_cache && <Tag>з кешу</Tag>}
        {done && (
          <Button
            icon={<DownloadOutlined />}
            loading={downloading}
            onClick={() => {
              setDownloading(true)
              download(`/analysis/requests/${req.id}/report.xlsx`, `tendoor-analysis-${req.id}.xlsx`)
                .catch((e: Error) => message.error(e.message))
                .finally(() => setDownloading(false))
            }}
          >
            Звіт XLSX
          </Button>
        )}
      </Space>
      <Typography.Paragraph type="secondary">
        Період оголошення {dayjs(req.date_from).format('DD.MM.YYYY')} – {dayjs(req.date_to).format('DD.MM.YYYY')}
        {req.unit_codes.length > 0 && `, одиниці: ${req.unit_codes.join(', ')}`}
      </Typography.Paragraph>

      {(req.status === 'queued' || req.status === 'running') && (
        <Card>
          <Spin /> <Typography.Text style={{ marginLeft: 12 }}>Модель навчається на вибірці — зазвичай до хвилини…</Typography.Text>
        </Card>
      )}
      {req.status === 'failed' && <Alert type="error" showIcon message="Аналіз завершився помилкою" description={req.message} />}

      {done && m && (
        <>
          <Row gutter={[16, 16]}>
            {[
              ['Проаналізовано позицій', m.n_analysed],
              ['Аномалій', m.n_anomalies],
              ['Частка аномалій', `${(m.anomaly_share * 100).toFixed(1)} %`],
              ['Однорідних груп', m.n_groups],
            ].map(([title, value]) => (
              <Col xs={12} md={6} key={title}>
                <Card size="small">
                  <Statistic title={title} value={value} groupSeparator=" " />
                </Card>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} xl={9}>
              <Card title="Групи" size="small" styles={{ body: { padding: 0 } }}>
                <Table<Category>
                  rowKey="id"
                  size="small"
                  dataSource={cats.filter((c) => c.analysed)}
                  pagination={{ pageSize: 8, size: 'small' }}
                  rowClassName={(c) => (c.id === catId ? 'ant-table-row-selected' : '')}
                  onRow={(c) => ({ onClick: () => setCatId(c.id), style: { cursor: 'pointer' } })}
                  columns={[
                    {
                      title: 'Група',
                      render: (_, c) => (
                        <>
                          <div>{c.top_terms.slice(0, 3).join(', ') || '—'}</div>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {c.cpv_code} · {c.base_unit_code}
                          </Typography.Text>
                        </>
                      ),
                    },
                    { title: 'Позицій', dataIndex: 'size', align: 'right' },
                    { title: 'Медіана', dataIndex: 'median_price', align: 'right', render: money },
                    { title: 'Аном.', dataIndex: 'n_anomalies', align: 'right' },
                  ]}
                />
              </Card>
            </Col>
            <Col xs={24} xl={15}>
              <Card
                size="small"
                title={cat ? `Група: ${cat.top_terms.slice(0, 3).join(', ')} (${cat.size} поз.)` : 'Група'}
                extra={
                  <Segmented
                    value={view}
                    onChange={(v) => setView(v as 'price' | 'pca')}
                    options={[
                      { value: 'price', label: 'Ціна × обсяг' },
                      { value: 'pca', label: 'Простір PCA' },
                    ]}
                  />
                }
              >
                {option ? <Chart option={option} height={380} /> : <Spin />}
              </Card>
            </Col>
          </Row>

          <Card title="Аномальні цінові пропозиції (за ризиком)" style={{ marginTop: 16 }}>
            <Table<AnomalyRow>
              rowKey="result_id"
              size="small"
              loading={rows?.key !== rowsKey}
              dataSource={rows?.items ?? []}
              scroll={{ x: 1100 }}
              pagination={{ current: page, pageSize: PAGE, total: rows?.total ?? 0, onChange: setPage, showSizeChanger: false }}
              expandable={{ expandedRowRender: (r) => <Typography.Text>{r.explanation}</Typography.Text> }}
              onRow={(r) => ({ onClick: () => setOpened(r.item_id), style: { cursor: 'pointer' } })}
              columns={[
                { title: 'Ризик', dataIndex: 'risk_score', width: 130, render: riskTag },
                {
                  title: 'Ціна',
                  width: 150,
                  render: (_, r) =>
                    r.pack_size ? (
                      <Tooltip title={`У документі: ${money(r.unit_price_base)} грн/${r.base_unit_code}, фасовка ${r.pack_size}`}>
                        {money(r.model_price ?? r.unit_price_base)} грн/{r.model_unit}*
                      </Tooltip>
                    ) : (
                      `${money(r.model_price ?? r.unit_price_base)} грн/${r.model_unit ?? r.base_unit_code}`
                    ),
                },
                {
                  title: 'Відхилення',
                  dataIndex: 'price_ratio',
                  width: 110,
                  render: (v: number | null) =>
                    v == null ? '—' : v >= 1 ? `×${v.toFixed(1)} вище` : `×${(1 / v).toFixed(1)} нижче`,
                },
                { title: 'Предмет закупівлі', dataIndex: 'description', ellipsis: true },
                {
                  title: 'Вердикт',
                  dataIndex: 'verdict_status',
                  width: 170,
                  render: (s: VerdictStatus | null) =>
                    s ? <Tag color={VERDICT_STATUS[s].color}>{VERDICT_STATUS[s].label}</Tag> : <Tag>не розглянуто</Tag>,
                },
                { title: 'Замовник', dataIndex: 'entity_name', ellipsis: true },
                {
                  title: 'Закупівля',
                  dataIndex: 'tender_code',
                  width: 220,
                  render: (code: string) => (
                    <a
                      href={`https://prozorro.gov.ua/tender/${code}`}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {code} <LinkOutlined />
                    </a>
                  ),
                },
              ]}
            />
          </Card>
          <ItemDrawer
            itemId={opened}
            runId={req.model_run_id}
            onClose={() => setOpened(null)}
            onSaved={() => setReloadRows((n) => n + 1)}
          />
          {req.homogeneity_details && (
            <Card title="Однорідність вибірки" style={{ marginTop: 16, maxWidth: 560 }}>
              <HomogeneityCard h={req.homogeneity_details} nItems={req.homogeneity_details.n_items} />
            </Card>
          )}
        </>
      )}
    </>
  )
}
