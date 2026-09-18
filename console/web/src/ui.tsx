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

export function Card({ title, hint, children, className, bare }: {
  title: ReactNode; hint?: ReactNode; children: ReactNode; className?: string; bare?: boolean;
}) {
  // A plain-text hint is a subtitle under the title; anything interactive (a
  // toggle) sits on the right of the header instead of crowding the title line.
  // `bare` drops the title and subtitle when the page already shows them.
  const subtitle = typeof hint === "string";
  const tools = !!hint && !subtitle;
  return (
    <section className={`card ${className ?? ""}`}>
      {(!bare || tools) && (
        <div className="card-head">
          {!bare && (
            <div>
              <h2>{title}</h2>
              {subtitle && <p className="hint">{hint}</p>}
            </div>
          )}
          {tools && <div className="card-tools">{hint}</div>}
        </div>
      )}
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
/** Name only, for tight spots; the id stays available as a tooltip. */
export const techniqueLabel = (t: string) => TECHNIQUE[t] ?? t;

/** One event with its reasons always visible (kit rule 2). `compact` stacks the
 * row for a narrow feed and drops the fields that never vary there (layer, type, node). */
export function EventRow({ e, compact }: { e: SmEvent; compact?: boolean }) {
  const isGate = e.type === "gate_decision";
  const action = isGate ? String(e.details?.action ?? "") : "";
  const chip = action && ACTION[action] ? <Chip spec={ACTION[action]} /> : <SeverityChip s={e.severity} />;
  const prob = e.score !== null && e.score !== undefined && (
    <>{isGate ? "P(real)" : "score"} <span className="prob">{e.score.toFixed(2)}</span></>
  );
  const body = (
    <div className="body">
      <div className="sum">{compact ? e.summary : <>{LAYER_TAG[e.layer] ?? e.layer} &middot; {e.summary}</>}</div>
      <div className="meta">
        {compact ? prob : (
          <>
            {e.type}
            {e.node && <> &middot; {e.node}</>}
            {prob && <> &middot; {prob}</>}
            {e.technique && <> &middot; <span className="tag">{techniqueName(e.technique)}</span></>}
          </>
        )}
      </div>
      {e.reasons?.length > 0 && (
        <ul className="reasons">{e.reasons.slice(0, 3).map((r, i) => <li key={i}>{r}</li>)}</ul>
      )}
    </div>
  );
  if (compact) {
    return (
      <div className="ev compact">
        <div className="lead">{chip}<span className="t">{fmtTime(e.ts)}</span></div>
        {body}
      </div>
    );
  }
  return (
    <div className="ev">
      <div className="t">{fmtTime(e.ts)}</div>
      <div>{chip}</div>
      {body}
    </div>
  );
}
