export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type Layer = 'mail' | 'file' | 'field' | 'tamper'

export interface SmEvent {
  id: string
  ts: number
  layer: Layer
  type: string
  severity: Severity
  score: number | null
  node: string | null
  technique: string | null
  summary: string
  reasons: string[]
  details: Record<string, unknown>
}

export interface Incident {
  id: string
  title: string
  severity: Severity
  started_ts: number
  last_ts: number
  layers: Layer[]
  stages: Record<string, string>
  event_ids: string[]
  techniques: string[]
}

export interface NodeStatus {
  id: string
  state: string
  rssi: number
  battery_pct: number | null
  last_seen_ms: number
}

export interface Status {
  ts: number
  link: string
  crypto_level: number
  battery_pct: number
  power_mw: number
  baseline_mw: number
  projected_days: number
  projected_days_idle: number
  mode: string
  attack_profile: string
  budget_j: number
  budget_max_j: number
  nodes: NodeStatus[]
}

export interface EnergySample {
  ts: number
  power_mw: number
  battery_pct: number
  volts: number
  amps: number
}

export interface EnergySeries {
  samples: EnergySample[]
}

export interface ExperimentRow {
  condition: string
  label: string
  energy_j_per_hour: number | null
  projected_days: number | null
  legit_connect_pct: number | null
  legit_extra_delay_ms: number | null
  status: 'done' | 'running' | 'pending'
}

export interface Experiment {
  profiles: string[]
  rows: ExperimentRow[]
  note: string
}

export interface ScanResult {
  id: string
  ts: number
  layer: Layer
  type: string
  severity: Severity
  score: number | null
  node: string | null
  technique: string | null
  summary: string
  reasons: string[]
  details: Record<string, unknown>
}

export interface ScanExamples {
  email: ScanResult[]
  file: ScanResult[]
}
