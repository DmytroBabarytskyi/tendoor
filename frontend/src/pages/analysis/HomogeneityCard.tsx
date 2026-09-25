import { CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled } from '@ant-design/icons'
import { Alert, Descriptions, Progress, Space, Typography } from 'antd'
import type { Homogeneity } from './types'

// статусні кольори з іконкою та підписом — колір ніколи не несе значення сам
const LEVEL = {
  good: { color: '#0ca30c', icon: <CheckCircleFilled />, label: 'однорідна', alert: 'success' },
  warn: { color: '#fab219', icon: <ExclamationCircleFilled />, label: 'змішана', alert: 'warning' },
  bad: { color: '#d03b3b', icon: <CloseCircleFilled />, label: 'неоднорідна', alert: 'error' },
} as const

const pct = (v: number) => `${Math.round(v * 100)} %`

export default function HomogeneityCard({ h, nItems }: { h: Homogeneity; nItems: number }) {
  const level = LEVEL[h.level]
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space align="center" size="large">
        <Progress type="dashboard" size={96} percent={Math.round(h.index * 100)} strokeColor={level.color} />
        <div>
          <Typography.Text type="secondary">Індекс однорідності вибірки</Typography.Text>
          <Typography.Title level={4} style={{ margin: 0, color: level.color }}>
            {level.icon} {level.label}
          </Typography.Title>
          <Typography.Text>{nItems.toLocaleString('uk-UA')} позицій з ціною</Typography.Text>
        </div>
      </Space>
      <Alert type={level.alert} showIcon message={h.message} />
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label={`Концентрація класів ДК 021 (${h.cpv_classes} кл.)`}>
          {pct(h.cpv_concentration)}
        </Descriptions.Item>
        <Descriptions.Item label={`Єдність одиниць виміру (${h.units} од.)`}>{pct(h.unit_purity)}</Descriptions.Item>
        <Descriptions.Item label="Компактність цін">{pct(h.price_compactness)}</Descriptions.Item>
      </Descriptions>
    </Space>
  )
}
