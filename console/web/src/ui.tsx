// Shared display pieces. Severity, link state and gate actions are the only
// places status colour is used, and every one carries an icon and a word too
// (kit rule 5), so nothing is read from colour alone.
import type { ReactNode } from "react";
import type { NodeStatus, Severity, SmEvent, Status } from "./types";

type ChipSpec = { color: string; icon: string; label: string; filled?: boolean };

export const SEVERITY: Record<Severity, ChipSpec> = {
  info:     { color: "var(--muted)",    icon: "•",   label: "info" },
  low:      { color: "var(--warning)",  icon: "!",        label: "low" },
  medium:   { color: "var(--serious)",  icon: "!!",       label: "medium" },
  high:     { color: "var(--critical)", icon: "!!!",      label: "high" },
  critical: { color: "var(--critical)", icon: "■",   label: "critical", filled: true },
};

export const LINK: Record<Status["link"], ChipSpec> = {
  secure:   { color: "var(--good)",     icon: "✔", label: "secure" },
  degraded: { color: "var(--warning)",  icon: "⚠", label: "degraded" },
  attack:   { color: "var(--critical)", icon: "✖", label: "under attack" },
  tamper:   { color: "var(--critical)", icon: "⛔", label: "tamper", filled: true },
  offline:  { color: "var(--muted)",    icon: "○", label: "offline" },
};

export const NODE: Record<NodeStatus["state"], ChipSpec> = { ...LINK, attack: LINK.attack };

export const ACTION: Record<string, ChipSpec> = {
  spend:     { color: "var(--good)",     icon: "✔", label: "spend" },
  challenge: { color: "var(--warning)",  icon: "?",      label: "challenge" },
  drop:      { color: "var(--critical)", icon: "✖", label: "drop" },
};

export function Chip({ spec, big, children }: { spec: ChipSpec; big?: boolean; children?: ReactNode }) {
  const style = spec.filled ? { background: spec.color } : { color: spec.color };
  return (
    <span className={`chip${spec.filled ? " filled" : ""}${big ? " big" : ""}`} style={style}>
      <span aria-hidden>{spec.icon}</span> {children ?? spec.label}
    </span>
  );
}

export const SeverityChip = ({ s }: { s: Severity }) => <Chip spec={SEVERITY[s] ?? SEVERITY.info} />;

export function Card({ title, hint, children, className }: {
  title: ReactNode; hint?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className ?? ""}`}>
      <h2>{title}{hint && <span className="hint">{hint}</span>}</h2>
      {children}
    </section>
  );
}

export const fmtTime = (ts: number) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

export const fmtNum = (v: number | null | undefined, digits = 0, unit = "") =>
  v === null || v === undefined || Number.isNaN(v)
    ? <span className="dash">&mdash;</span>
    : <>{v.toFixed(digits)}{unit && <small> {unit}</small>}</>;

const LAYER_TAG: Record<string, string> = { mail: "MAIL", file: "FILE", field: "FIELD", tamper: "TAMPER" };

const TECHNIQUE: Record<string, string> = {
  "T1566.001": "Spearphishing Attachment",
  "T1204.002": "User Execution: Malicious File",
  "T0830": "Adversary-in-the-Middle (ICS)",
  "T1692.002": "Unauthorized Message: Reporting Message (ICS)",
};
export const techniqueName = (t: string) => (TECHNIQUE[t] ? `${t} ${TECHNIQUE[t]}` : t);

/** One event with its reasons always visible (kit rule 2). */
export function EventRow({ e }: { e: SmEvent }) {
  const action = e.type === "gate_decision" ? String(e.details?.action ?? "") : "";
  return (
    <div className="ev">
      <div className="t">{fmtTime(e.ts)}</div>
      <div>{action && ACTION[action] ? <Chip spec={ACTION[action]} /> : <SeverityChip s={e.severity} />}</div>
      <div className="body">
        <div className="sum">{LAYER_TAG[e.layer] ?? e.layer} &middot; {e.summary}</div>
        <div className="meta">
          {e.type}
          {e.node && <> &middot; {e.node}</>}
          {e.score !== null && e.score !== undefined && (
            <> &middot; {e.type === "gate_decision" ? "P(real)" : "score"}{" "}
              <span className="prob">{e.score.toFixed(2)}</span></>
          )}
          {e.technique && <> &middot; <span className="tag">{techniqueName(e.technique)}</span></>}
        </div>
        {e.reasons?.length > 0 && (
          <ul className="reasons">{e.reasons.slice(0, 3).map((r, i) => <li key={i}>{r}</li>)}</ul>
        )}
      </div>
    </div>
  );
}
