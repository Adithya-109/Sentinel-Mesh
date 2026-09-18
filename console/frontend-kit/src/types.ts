// SentinelMesh console — shared types. Mirrors contracts/CONTRACT.md (v1.1).
export type Layer = "mail" | "file" | "field" | "tamper";
export type Severity = "info" | "low" | "medium" | "high" | "critical";

export type EventType =
  | "email_malicious" | "email_clean"
  | "file_malicious" | "file_clean"
  | "replay_rejected" | "handshake_rejected" | "attack_detected" | "link_degraded" | "rekey"
  | "gate_decision" | "energy_alert" | "budget_exhausted"
  | "case_opened" | "moved" | "voltage_anomaly";

export interface SmEvent {
  id: string;
  ts: number;                 // epoch ms
  layer: Layer;
  type: EventType;
  severity: Severity;
  score: number | null;       // 0..1 where a model produced one
  node: string | null;        // "field-1" | "gateway" | "attacker" | null
  technique: string | null;   // MITRE ATT&CK id, e.g. "T1566.001"
  summary: string;            // one line for the timeline
  reasons: string[];          // up to 3, always show these
  details: Record<string, unknown>;
}

export type Stage = "inbox" | "endpoint" | "field" | "physical";
export interface Incident {
  id: string;
  title: string;
  severity: Severity;
  started_ts: number;
  last_ts: number;
  layers: Layer[];
  stages: Record<Stage, "clear" | "hit">;
  event_ids: string[];
  techniques: string[];
}

export interface NodeStatus {
  id: string; state: "secure" | "degraded" | "attack" | "tamper" | "offline";
  rssi: number | null; battery_pct: number | null; last_seen_ms: number;
}
export interface Status {
  ts: number;
  link: "secure" | "degraded" | "attack" | "tamper";
  crypto_level: 512 | 768 | 1024;
  battery_pct: number;
  power_mw: number;           // current draw right now
  baseline_mw: number;        // idle draw, for the "x times normal" line
  projected_days: number;     // at the current draw
  projected_days_idle: number;
  mode: "none" | "ratelimit" | "cookie" | "gate";
  attack_profile: "none" | "loud" | "slow_drip";
  budget_j: number; budget_max_j: number;   // EnergyGate's remaining joule budget
  nodes: NodeStatus[];
}

export interface EnergySample { ts: number; power_mw: number; battery_pct: number; volts: number; amps: number; }
export interface EnergySeries { samples: EnergySample[]; markers: { ts: number; label: string }[]; }

export interface ExperimentRow {
  condition: "no_attack" | "undefended" | "ratelimit" | "cookie" | "gate";
  label: string;
  energy_j_per_hour: number | null;
  projected_days: number | null;
  legit_connect_pct: number | null;
  legit_extra_delay_ms: number | null;
  status: "pending" | "running" | "done";
}
export interface Experiment { profiles: string[]; rows: ExperimentRow[]; note?: string }
