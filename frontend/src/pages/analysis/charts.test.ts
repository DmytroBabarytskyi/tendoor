import { describe, expect, it } from 'vitest'
import { pcaOption, priceVolumeOption, type Point } from './charts'

const point = (id: number, price: number, anomaly = false, pc: number | null = 0.1): Point => ({
  item_id: id,
  pc1: pc,
  pc2: pc,
  is_anomaly: anomaly,
  is_extreme: false,
  risk_score: anomaly ? 97 : 10,
  price,
  quantity: 100,
})

type Series = { name: string; symbol: string; data: { value: number[]; point: Point }[]; markLine?: unknown }

describe('chart options', () => {
  const points = [point(1, 50), point(2, 52), point(3, 500, true)]

  it('splits anomalies into their own series with a distinct marker shape', () => {
    const [normal, anomaly] = priceVolumeOption(points, 'KGM', 51).series as Series[]
    expect(normal.data.map((d) => d.point.item_id)).toEqual([1, 2])
    expect(anomaly.data.map((d) => d.value)).toEqual([[100, 500]])
    expect(normal.symbol).not.toBe(anomaly.symbol) // колір не єдиний носій відмінності
  })

  it('draws the group median only once, on the normal series', () => {
    const [normal, anomaly] = priceVolumeOption(points, 'KGM', 51).series as Series[]
    expect(normal.markLine).toBeDefined()
    expect(anomaly.markLine).toBeUndefined()
    expect((priceVolumeOption(points, 'KGM').series as Series[])[0].markLine).toBeUndefined()
  })

  it('uses log axes for price/volume and skips points without a PCA projection', () => {
    const pv = priceVolumeOption(points, 'LTR') as { xAxis: { type: string; name: string } }
    expect(pv.xAxis.type).toBe('log')
    expect(pv.xAxis.name).toBe('Обсяг, LTR')
    const pca = pcaOption([...points, point(4, 60, false, null)], 'KGM').series as Series[]
    expect(pca.flatMap((s) => s.data).length).toBe(3)
  })
})
