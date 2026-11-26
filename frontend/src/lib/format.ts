import { format as fmt, parseISO } from 'date-fns'
import { uk } from 'date-fns/locale'

const toDate = (d: string | Date) => (typeof d === 'string' ? parseISO(d) : d)

export const money = (v: number | null | undefined) =>
  v == null ? '—' : Number(v).toLocaleString('uk-UA', { maximumFractionDigits: 2 })
export const int = (v: number | null | undefined) => (v == null ? '—' : Math.round(v).toLocaleString('uk-UA'))
/** Число з фіксованою кількістю знаків в українському записі (десяткова кома). */
export const num = (v: number, digits = 1) =>
  v.toLocaleString('uk-UA', { minimumFractionDigits: digits, maximumFractionDigits: digits })
export const pct = (v: number, digits = 0) => `${num(v * 100, digits)} %`
export const date = (d: string | Date) => fmt(toDate(d), 'dd.MM.yyyy', { locale: uk })
export const shortDate = (d: string | Date) => fmt(toDate(d), 'dd.MM.yy', { locale: uk })
export const dateTime = (d: string | Date) => fmt(toDate(d), 'dd.MM.yyyy HH:mm', { locale: uk })
export const isoDay = (d: Date) => fmt(d, 'yyyy-MM-dd')
export const ratio = (v: number | null) => (v == null ? '—' : v >= 1 ? `▲ ×${num(v)} вище` : `▼ ×${num(1 / v)} нижче`)
