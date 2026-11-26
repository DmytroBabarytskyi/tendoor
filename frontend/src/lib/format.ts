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
// коди одиниць виміру (UN/ECE Rec. 20) -> звичні скорочення
const UNIT_SHORT: Record<string, string> = {
  KGM: 'кг', GRM: 'г', TNE: 'т', LTR: 'л', MLT: 'мл', MTQ: 'м³', MTR: 'м', MTK: 'м²', H87: 'шт', PR: 'пара', SET: 'набір',
}
export const unitShort = (code: string | null | undefined) => (code ? (UNIT_SHORT[code] ?? code) : 'од.')

/** Назва групи товарів з ключових слів без повторів: «вироби, макаронний вироби» -> «вироби макаронний». */
export const groupName = (terms: string[]) => {
  const words = [...new Set(terms.flatMap((t) => t.split(/[\s,;]+/)).filter(Boolean))]
  return words.slice(0, 5).join(' ') || 'без назви'
}
export const ratio = (v: number | null) => (v == null ? '—' : v >= 1 ? `▲ ×${num(v)} вище` : `▼ ×${num(1 / v)} нижче`)
