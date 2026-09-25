export type VerdictStatus = 'confirmed' | 'not_anomaly' | 'needs_review'
export type VerdictReason = 'overpriced' | 'underpriced' | 'unit_error' | 'data_error' | 'justified' | 'other'

// статусні кольори завжди в парі з текстом мітки
export const VERDICT_STATUS: Record<VerdictStatus, { label: string; color: string }> = {
  confirmed: { label: 'аномалію підтверджено', color: 'red' },
  not_anomaly: { label: 'аномалії немає', color: 'green' },
  needs_review: { label: 'потребує перевірки', color: 'gold' },
}

export const VERDICT_REASON: Record<VerdictReason, string> = {
  overpriced: 'завищена ціна',
  underpriced: 'занижена ціна (демпінг)',
  unit_error: 'помилка одиниці виміру',
  data_error: 'помилка в даних',
  justified: 'ціна обґрунтована',
  other: 'інше',
}

export type Verdict = {
  id: number
  item_id: number
  status: VerdictStatus
  reason: VerdictReason
  comment: string | null
  updated_at: string
  user_email: string | null
  user_name: string | null
  description?: string
  unit_price_base?: number
  base_unit_code?: string
  tender_code?: string
  entity_name?: string
}

export type VerdictHistory = {
  id: number
  old_status: VerdictStatus | null
  new_status: VerdictStatus
  old_reason: VerdictReason | null
  new_reason: VerdictReason
  comment: string | null
  changed_at: string
  user_email: string | null
  user_name: string | null
}
