import { format as fmt, parseISO } from 'date-fns'
import { uk } from 'date-fns/locale'

const toDate = (d: string | Date) => (typeof d === 'string' ? parseISO(d) : d)

export const money = (v: number | null | undefined) =>
  v == null ? '—' : Number(v).toLocaleString('uk-UA', { maximumFractionDigits: 2 })
export const int = (v: number | null | undefined) => (v == null ? '—' : Math.round(v).toLocaleString('uk-UA'))
export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)} %`
export const date = (d: string | Date) => fmt(toDate(d), 'dd.MM.yyyy', { locale: uk })
export const shortDate = (d: string | Date) => fmt(toDate(d), 'dd.MM.yy', { locale: uk })
export const dateTime = (d: string | Date) => fmt(toDate(d), 'dd.MM.yyyy HH:mm', { locale: uk })
export const isoDay = (d: Date) => fmt(d, 'yyyy-MM-dd')
export const ratio = (v: number | null) => (v == null ? '—' : v >= 1 ? `×${v.toFixed(1)} вище` : `×${(1 / v).toFixed(1)} нижче`)
