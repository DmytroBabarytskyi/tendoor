export type Homogeneity = {
  index: number
  level: 'good' | 'warn' | 'bad'
  n_items: number
  cpv_concentration: number
  unit_purity: number
  price_compactness: number
  cpv_classes: number
  units: number
  message: string
}

export type Preview = {
  n_items: number
  too_large: boolean
  homogeneity: Homogeneity
  units: { code: string; n: number }[]
  cpv_classes: { code: string; n: number }[]
}

export type RunInfo = {
  id: number
  status: string
  pipeline_version: string
  params: Record<string, unknown>
  metrics: {
    n_items: number
    n_analysed: number
    n_anomalies: number
    n_extreme: number
    anomaly_share: number
    n_groups: number
    seconds: number
    importance?: { feature: string; label: string; points: number }[]
  } | null
  error: string | null
}

export type AnalysisRequest = {
  id: number
  status: 'queued' | 'running' | 'done' | 'failed'
  cpv_prefixes: string[]
  unit_codes: string[]
  params?: Record<string, unknown>
  date_from: string
  date_to: string
  homogeneity: number | null
  homogeneity_details: Homogeneity | null
  model_run_id: number | null
  from_cache: boolean
  message: string | null
  created_at: string
  finished_at: string | null
  run?: RunInfo | null
}

export type Category = {
  id: number
  label: number
  base_unit_code: string
  cpv_code: string | null
  top_terms: string[]
  size: number
  median_price: number | null
  analysed: boolean
  n_anomalies: number
}

export type AnomalyRow = {
  result_id: number
  item_id: number
  is_anomaly: boolean
  // ймовірна помилка даних: екстремум першого етапу, позначається незалежно від ризику
  is_extreme: boolean
  risk_score: number | null
  price_ratio: number | null
  description: string
  unit_price_base: number
  base_unit_code: string
  // ціна в одиниці моделі (v2 перераховує фасовку «штук» у грн/кг, грн/л); null — результати v1
  model_price: number | null
  model_unit: string | null
  pack_size: number | null
  quantity_base: number
  price_source: string
  cpv_code: string
  cpv_description: string | null
  tender_code: string
  tender_title: string | null
  date_published: string
  entity_name: string
  entity_region: string | null
  category_id: number
  explanation: string
  verdict_status: 'confirmed' | 'not_anomaly' | 'needs_review' | null
  verdict_state: 'in_progress' | 'submitted' | 'returned' | 'approved' | null
}

export const STATUS = {
  queued: { color: 'default', label: 'у черзі' },
  running: { color: 'processing', label: 'навчання моделі' },
  done: { color: 'success', label: 'готово' },
  failed: { color: 'error', label: 'помилка' },
} as const
