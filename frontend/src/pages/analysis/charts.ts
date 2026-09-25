import type { ChartOption } from '../../components/Chart'

export type Point = {
  item_id: number
  pc1: number | null
  pc2: number | null
  is_anomaly: boolean
  is_extreme: boolean
  risk_score: number | null
  price: number
  quantity: number
}

// Перевірено валідатором палітри (контраст, дальтонізм): синій — перший категорійний слот,
// червоний — статус «критично»; колір дублюється формою маркера та легендою.
const NORMAL = '#2a78d6'
const ANOMALY = '#d03b3b'
const INK_MUTED = '#898781'
const GRID = '#e1e0d9'

const fmt = (v: number) => v.toLocaleString('uk-UA', { maximumFractionDigits: 2 })

function base(xName: string, yName: string, log: boolean): ChartOption {
  const axis = (name: string) => ({
    name,
    nameLocation: 'middle',
    nameGap: 32,
    type: log ? 'log' : 'value',
    scale: true,
    axisLine: { lineStyle: { color: '#c3c2b7' } },
    axisLabel: { color: INK_MUTED, formatter: (v: number) => fmt(v) },
    splitLine: { lineStyle: { color: GRID, width: 1 } },
    nameTextStyle: { color: '#52514e' },
  })
  return {
    grid: { left: 70, right: 24, top: 40, bottom: 52 },
    legend: { top: 0, right: 0, textStyle: { color: '#52514e' } },
    tooltip: { trigger: 'item', confine: true },
    xAxis: axis(xName),
    yAxis: { ...axis(yName), nameGap: 56 },
  }
}

function series(points: Point[], xy: (p: Point) => [number, number], median?: number, unit?: string) {
  const make = (anomaly: boolean) => ({
    name: anomaly ? 'Аномалія' : 'Звичайна ціна',
    type: 'scatter',
    symbol: anomaly ? 'triangle' : 'circle',
    symbolSize: anomaly ? 12 : 8,
    itemStyle: { color: anomaly ? ANOMALY : NORMAL, opacity: anomaly ? 0.95 : 0.55, borderColor: '#fff', borderWidth: 1 },
    z: anomaly ? 3 : 2,
    data: points.filter((p) => p.is_anomaly === anomaly).map((p) => ({ value: xy(p), point: p })),
    tooltip: {
      formatter: ({ data }: { data: { point: Point } }) => {
        const p = data.point
        return [
          `<b>${fmt(p.price)} грн/${unit ?? 'од.'}</b>`,
          `обсяг: ${fmt(p.quantity)} ${unit ?? ''}`,
          p.risk_score != null ? `ризик: ${Math.round(p.risk_score)}` : '',
          p.is_extreme ? 'екстремальне значення' : '',
        ]
          .filter(Boolean)
          .join('<br/>')
      },
    },
    ...(median && !anomaly
      ? {
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: INK_MUTED, type: 'dashed', width: 1 },
            label: { formatter: `медіана ${fmt(median)}`, color: '#52514e', position: 'insideEndTop' },
            data: [{ yAxis: median }],
          },
        }
      : {}),
  })
  return [make(false), make(true)]
}

/** Ціна за одиницю проти обсягу (логарифмічні осі): видно і завищення, і демпінг. */
export function priceVolumeOption(points: Point[], unit: string, median?: number): ChartOption {
  return { ...base(`Обсяг, ${unit}`, `Ціна, грн/${unit}`, true), series: series(points, (p) => [p.quantity, p.price], median, unit) }
}

/** Проєкція групи на перші дві головні компоненти (як у тезі, рис. 1а). */
export function pcaOption(points: Point[], unit: string): ChartOption {
  const valid = points.filter((p) => p.pc1 != null && p.pc2 != null)
  return { ...base('PC1', 'PC2', false), series: series(valid, (p) => [p.pc1 as number, p.pc2 as number], undefined, unit) }
}
