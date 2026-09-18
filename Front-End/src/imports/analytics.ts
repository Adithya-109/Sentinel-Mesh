import type { SmEvent, Incident, Status, Layer, Severity, ExperimentRow } from './types'
import { LAYER_LABEL } from './api'

export interface StageMetric {
  id: string
  name: string
  status: string
  eventCount: number
  layer: Layer
  description: string
}

export interface SeverityCount {
  name: string
  key: Severity
  value: number
  color: string
}

export interface MitreTechniqueMetric {
  technique: string
  name: string
  tactic: string
  count: number
  severity: Severity
}

export interface DefenseComparisonItem {
  condition: string
  label: string
  energyPerHour: number | null
  projectedDays: number | null
  legitConnectPct: number | null
  extraDelayMs: number | null
  status: string
}

export interface LayerStat {
  layer: Layer
  label: string
  count: number
  color: string
}

export interface AggregatedDashboardMetrics {
  totalIncidents: number
  activeIncidentsCount: number
  criticalIncidentsCount: number
  mttrSeconds: number
  attackDurationFormatted: string
  totalEvents: number
  eventsPerMinute: number
  peakPowerMw: number
  baselinePowerMw: number
  powerAnomalyMultiplier: number
  batteryCurrentPct: number
  projectedDaysCurrent: number
  projectedDaysIdle: number
  batteryDegradationPct: number
  stages: StageMetric[]
  severityDistribution: SeverityCount[]
  mitreTechniques: MitreTechniqueMetric[]
  defenseComparisons: DefenseComparisonItem[]
  layerBreakdown: LayerStat[]
  highestConfidenceEvent: SmEvent | null
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  critical: '#ef4444',
  high: '#e04c1e',
  medium: '#f59e0b',
  low: '#38bdf8',
  info: '#10b981',
}

export const LAYER_COLORS: Record<Layer, string> = {
  mail: '#f43f5e',
  file: '#e04c1e',
  field: '#38bdf8',
  tamper: '#a855f7',
}

export const MITRE_DETAILS: Record<string, { name: string; tactic: string; severity: Severity }> = {
  'T1566.001': { name: 'Spearphishing Attachment', tactic: 'Initial Access', severity: 'high' },
  'T1204.002': { name: 'Malicious File Execution', tactic: 'Execution', severity: 'high' },
  'T1692.002': { name: 'Radio / Frame Replay Attack', tactic: 'Impair Defenses', severity: 'high' },
  'T0830': { name: 'Field Impostor / Identity Spoofing', tactic: 'Infiltration', severity: 'critical' },
}

export function computeIncidentMetrics(
  incidents: Incident[],
  events: SmEvent[],
  status: Status | null,
  experiment: ExperimentRow[]
): AggregatedDashboardMetrics {
  const totalIncidents = incidents.length
  const activeIncidentsCount = incidents.length
  const criticalIncidentsCount = incidents.filter((i) => i.severity === 'critical').length

  // Calculate MTTR / Duration from primary incident (or sum/avg across incidents)
  let mttrSeconds = 0
  if (incidents.length > 0) {
    const primary = incidents[0]
    mttrSeconds = Math.max(0, Math.round((primary.last_ts - primary.started_ts) / 1000))
  }
  const mins = Math.floor(mttrSeconds / 60)
  const secs = mttrSeconds % 60
  const attackDurationFormatted = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

  // Total telemetry events
  const totalEvents = events.length
  const durationInMinutes = mttrSeconds > 0 ? mttrSeconds / 60 : 1
  const eventsPerMinute = totalEvents > 0 ? Math.round((totalEvents / durationInMinutes) * 10) / 10 : 0

  // Power & Battery Metrics
  const peakPowerMw = status?.power_mw ?? 512
  const baselinePowerMw = status?.baseline_mw ?? 84
  const powerAnomalyMultiplier =
    baselinePowerMw > 0 ? Math.round((peakPowerMw / baselinePowerMw) * 10) / 10 : 1
  const batteryCurrentPct = status?.battery_pct ?? 78.4
  const projectedDaysCurrent = status?.projected_days ?? 1.2
  const projectedDaysIdle = status?.projected_days_idle ?? 41.0
  const batteryDegradationPct =
    projectedDaysIdle > 0
      ? Math.round(((projectedDaysIdle - projectedDaysCurrent) / projectedDaysIdle) * 100)
      : 0

  // Severity Distribution
  const severityMap: Record<Severity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  }
  for (const ev of events) {
    if (severityMap[ev.severity] !== undefined) {
      severityMap[ev.severity] += 1
    }
  }
  const severityDistribution: SeverityCount[] = [
    { name: 'Critical', key: 'critical' as Severity, value: severityMap.critical, color: SEVERITY_COLORS.critical },
    { name: 'High', key: 'high' as Severity, value: severityMap.high, color: SEVERITY_COLORS.high },
    { name: 'Medium', key: 'medium' as Severity, value: severityMap.medium, color: SEVERITY_COLORS.medium },
    { name: 'Low', key: 'low' as Severity, value: severityMap.low, color: SEVERITY_COLORS.low },
    { name: 'Info', key: 'info' as Severity, value: severityMap.info, color: SEVERITY_COLORS.info },
  ].filter((s) => s.value > 0)

  // Layer Breakdown
  const layerCountMap: Record<Layer, number> = {
    mail: 0,
    file: 0,
    field: 0,
    tamper: 0,
  }
  for (const ev of events) {
    if (layerCountMap[ev.layer] !== undefined) {
      layerCountMap[ev.layer] += 1
    }
  }
  const layerBreakdown: LayerStat[] = (['mail', 'file', 'field', 'tamper'] as Layer[]).map(
    (layer) => ({
      layer,
      label: LAYER_LABEL[layer] || layer,
      count: layerCountMap[layer],
      color: LAYER_COLORS[layer],
    })
  )

  // Attack Stages Funnel
  const STAGE_CONFIGS: { id: string; name: string; layer: Layer; description: string }[] = [
    {
      id: 'inbox',
      name: '1. Infiltration Gate',
      layer: 'mail',
      description: 'Phishing delivery & lure attachment',
    },
    {
      id: 'endpoint',
      name: '2. Workstation Execution',
      layer: 'file',
      description: 'Host attachment execution & binary detonation',
    },
    {
      id: 'field',
      name: '3. Field Mesh Link',
      layer: 'field',
      description: 'Radio replay burst, spoofing & battery exhaustion',
    },
    {
      id: 'physical',
      name: '4. Physical Enclosure',
      layer: 'tamper',
      description: 'Hardware tamper switch trip & automated zero-key wipe',
    },
  ]

  const stages: StageMetric[] = STAGE_CONFIGS.map((cfg) => {
    const stageHit = incidents.some((inc) => inc.stages[cfg.id] === 'hit')
    return {
      id: cfg.id,
      name: cfg.name,
      status: stageHit ? 'hit' : 'clear',
      eventCount: layerCountMap[cfg.layer],
      layer: cfg.layer,
      description: cfg.description,
    }
  })

  // MITRE Techniques Counts
  const mitreCountMap: Record<string, number> = {}
  for (const ev of events) {
    if (ev.technique) {
      mitreCountMap[ev.technique] = (mitreCountMap[ev.technique] || 0) + 1
    }
  }
  // Also cross-reference incident techniques
  for (const inc of incidents) {
    for (const tech of inc.techniques) {
      if (!mitreCountMap[tech]) {
        mitreCountMap[tech] = 1
      }
    }
  }

  const mitreTechniques: MitreTechniqueMetric[] = Object.entries(mitreCountMap).map(
    ([technique, count]) => {
      const meta = MITRE_DETAILS[technique] || {
        name: 'Unmapped TTP',
        tactic: 'Adversary Action',
        severity: 'medium',
      }
      return {
        technique,
        name: meta.name,
        tactic: meta.tactic,
        count,
        severity: meta.severity,
      }
    }
  )

  // Defense Comparisons
  const defenseComparisons: DefenseComparisonItem[] = experiment.map((row) => ({
    condition: row.condition,
    label: row.label,
    energyPerHour: row.energy_j_per_hour,
    projectedDays: row.projected_days,
    legitConnectPct: row.legit_connect_pct,
    extraDelayMs: row.legit_extra_delay_ms,
    status: row.status,
  }))

  // Highest confidence anomaly score event
  let highestConfidenceEvent: SmEvent | null = null
  let maxScore = -1
  for (const ev of events) {
    if (ev.score !== null && ev.score > maxScore) {
      maxScore = ev.score
      highestConfidenceEvent = ev
    }
  }

  return {
    totalIncidents,
    activeIncidentsCount,
    criticalIncidentsCount,
    mttrSeconds,
    attackDurationFormatted,
    totalEvents,
    eventsPerMinute,
    peakPowerMw,
    baselinePowerMw,
    powerAnomalyMultiplier,
    batteryCurrentPct,
    projectedDaysCurrent,
    projectedDaysIdle,
    batteryDegradationPct,
    stages,
    severityDistribution,
    mitreTechniques,
    defenseComparisons,
    layerBreakdown,
    highestConfidenceEvent,
  }
}
