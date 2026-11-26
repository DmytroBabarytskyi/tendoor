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

// Кольори беруться з токенів теми (--chart-*), перевірених валідатором палітри для обох тем
// (дальтонізм, насиченість, контраст); форма маркера й легенда дублюють колір.
type Colors = { normal: string; anomaly: string; grid: string; axis: string; text: string; surface: string }
const FALLBACK: Colors = { normal: '#2f6fb0', anomaly: '#c2412d', grid: '#e8e1d5', axis: '#8a8074', text: '#6b6257', surface: '#fffdf9' }

export function chartColors(): Colors {
  if (typeof document === 'undefined') return FALLBACK
  const css = getComputedStyle(document.documentElement)
  const v = (name: string, fb: string) => css.getPropertyValue(name).trim() || fb
  return {
    normal: v('--chart-normal', FALLBACK.normal),
    anomaly: v('--chart-anomaly', FALLBACK.anomaly),
    grid: v('--chart-grid', FALLBACK.grid),
    axis: v('--chart-axis', FALLBACK.axis),
    text: v('--muted-foreground', FALLBACK.text),
    surface: v('--card', FALLBACK.surface),
  }
}

const fmt = (v: number) => v.toLocaleString('uk-UA', { maximumFractionDigits: 2 })

function base(xName: string, yName: string, log: boolean, c: Colors): ChartOption {
  const axis = (name: string) => ({
    name: log ? `${name} (логарифмічна шкала)` : name,
    nameLocation: 'middle',
    nameGap: 32,
    type: log ? 'log' : 'value',
    scale: true,
    axisLine: { lineStyle: { color: c.grid } },
    axisLabel: { color: c.axis, formatter: (v: number) => fmt(v) },
    splitLine: { lineStyle: { color: c.grid, width: 1 } },
    nameTextStyle: { color: c.text },
  })
  return {
    grid: { left: 70, right: 24, top: 40, bottom: 52 },
    legend: { top: 0, right: 0, textStyle: { color: c.text } },
    tooltip: { trigger: 'item', confine: true, backgroundColor: c.surface, borderColor: c.grid, textStyle: { color: c.text } },
    xAxis: axis(xName),
    yAxis: { ...axis(yName), nameGap: 56 },
  }
}

function series(points: Point[], xy: (p: Point) => [number, number], c: Colors, median?: number, unit?: string) {
  const make = (anomaly: boolean) => ({
    name: anomaly ? 'Аномалія' : 'Звичайна ціна',
    type: 'scatter',
    symbol: anomaly ? 'triangle' : 'circle',
    symbolSize: anomaly ? 12 : 8,
    itemStyle: { color: anomaly ? c.anomaly : c.normal, opacity: anomaly ? 0.95 : 0.55, borderColor: c.surface, borderWidth: 1 },
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
            lineStyle: { color: c.axis, type: 'dashed', width: 1 },
            label: { formatter: `медіана ${fmt(median)}`, color: c.text, position: 'insideEndTop' },
            data: [{ yAxis: median }],
          },
        }
      : {}),
  })
  return [make(false), make(true)]
}

/** Ціна за одиницю проти обсягу (логарифмічні осі): видно і завищення, і демпінг. */
export function priceVolumeOption(points: Point[], unit: string, median?: number, c: Colors = chartColors()): ChartOption {
  return { ...base(`Обсяг, ${unit}`, `Ціна, грн/${unit}`, true, c), series: series(points, (p) => [p.quantity, p.price], c, median, unit) }
}

/** Проєкція групи на перші дві головні компоненти (як у тезі, рис. 1а). */
export function pcaOption(points: Point[], unit: string, c: Colors = chartColors()): ChartOption {
  const valid = points.filter((p) => p.pc1 != null && p.pc2 != null)
  return { ...base('PC1', 'PC2', false, c), series: series(valid, (p) => [p.pc1 as number, p.pc2 as number], c, undefined, unit) }
}
