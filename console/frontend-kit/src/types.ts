// SentinelMesh console — shared types. Mirrors contracts/CONTRACT.md (v1 + v2-energy + v4 serial).
// The live copy the app compiles is console/web/src/types.ts; keep the two identical.
//
// v4 changes from the kit as delivered (see contracts/CHANGELOG.md, 2026-09-18 "v4 endpoints"):
//   - Status numbers are `| null` where the console has no data yet. The UI shows a dash; it
//     never substitutes a plausible number (kit rule 1).
//   - Status.link gains "offline": with no boards connected, "secure" would be a lie.
//   - attack_profile gains replay | impersonate | weak_link, so the v3 field-network beat can be
//     driven from the same screen as the v4 drain beat.
//   - `simulated` / `source` flags mark numbers that came from tools/mock_rig.py, not the rig.
export type Layer = "mail" | "file" | "field" | "tamper";
export type Severity = "info" | "low" | "medium" | "high" | "critical";

export type EventType =
  | "email_malicious" | "email_suspicious" | "email_clean"
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
  score: number | null;       // 0..1 where a model produced one; for gate_decision, P(sender is real)
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
  base_severity?: Severity;   // before escalation
  escalated_by?: string[];    // why the severity is what it is (correlation rules R4/R5)
  coordinated?: boolean;      // mail + file + field in one window
}

export interface NodeStatus {
  id: string; state: "secure" | "degraded" | "attack" | "tamper" | "offline";
  rssi: number | null; battery_pct: number | null;
  last_seen_ms: number | null;  // ms since last heard from; null = never
}
export type Mode = "none" | "ratelimit" | "cookie" | "gate";
export type AttackProfile = "none" | "loud" | "slow_drip" | "replay" | "impersonate" | "weak_link";
export interface Status {
  ts: number;
  link: "secure" | "degraded" | "attack" | "tamper" | "offline";
  crypto_level: 512 | 768 | 1024 | null;
  battery_pct: number | null;
  power_mw: number | null;            // current draw (mean of the last few seconds)
  baseline_mw: number | null;         // idle draw, for the "x times normal" line
  baseline_source?: string;           // where the baseline came from
  projected_days: number | null;      // ESTIMATE: measured draw vs an assumed cell capacity
  projected_days_idle: number | null;
  projection_assumes_wh?: number;
  mode: Mode;
  attack_profile: AttackProfile;
  budget_j: number | null; budget_max_j: number | null;   // EnergyGate's joule budget, as last reported
  simulated?: boolean;                // latest energy sample came from tools/mock_rig.py
  nodes: NodeStatus[];
}

export interface EnergySample {
  ts: number; power_mw: number; battery_pct: number | null; volts: number; amps: number;
  source?: "ina219" | "sim";
}
export interface EnergySeries {
  samples: EnergySample[]; markers: { ts: number; label: string }[];
  simulated?: boolean;
}

export type Condition = "no_attack" | "undefended" | "ratelimit" | "cookie" | "gate";
export interface ExperimentRow {
  condition: Condition;
  label: string;
  energy_j_per_hour: number | null;
  projected_days: number | null;
  legit_connect_pct: number | null;      // firmware-measured; null until posted
  legit_extra_delay_ms: number | null;
  status: "pending" | "running" | "done";
  source?: "measured" | "simulated" | null;
  started_ts?: number; ended_ts?: number; duration_s?: number; samples?: number;
}
export interface Experiment {
  profiles: string[];
  profile?: string;                      // which profile `rows` belong to
  rows: ExperimentRow[];
  running?: { condition: Condition; profile: string; ends_ts: number } | null;
  note?: string;
}

// -- Detection Channels (channels/*/manifest.json, api/channels.py) ----------
// Proves the architecture is extensible to a channel beyond email/file without
// touching MailGuard or FileGuard. Only SMS is a real, trained classifier;
// everything else is a clearly-labeled dummy with no live classification.
export interface Channel {
  id: string;
  display_name: string;
  description?: string;
  status: "active" | "dummy";
  enabled: boolean;
  model_path: string | null;
  vectorizer_path: string | null;
  metrics: Record<string, unknown>;
  live_classify: boolean;
  test_endpoint?: string;   // set on email/file: they use the existing Scan tab, not /classify
}
export interface ChannelsResponse { channels: Channel[]; count: number }
export interface ClassifyResult {
  channel: string;
  label: "smishing" | "legitimate";
  confidence: number;
  reasons: string[];
}
