import { useState } from "react";
import { api } from "./api";
import type { AttackProfile, Incident, Mode, SmEvent, Stage, Status } from "./types";
import { ACTION, Card, Chip, EventRow, fmtNum, fmtTime, LINK, NODE, SeverityChip, techniqueLabel } from "./ui";

// -- status bar ---------------------------------------------------------------

export function StatusBar({ s }: { s: Status | null }) {
  if (!s) return <div className="statusbar"><div className="stat"><div className="k">status</div><div className="v">&mdash;</div></div></div>;
  const multiple = s.power_mw !== null && s.baseline_mw ? s.power_mw / s.baseline_mw : null;
  const budgetPct = s.budget_j !== null && s.budget_max_j ? Math.max(0, Math.min(100, (100 * s.budget_j) / s.budget_max_j)) : null;
  const life = s.projected_days;
  return (
    <div className="statusbar">
      <div className="stat">
        <div className="k">Field link</div>
        <div style={{ marginTop: 10 }}><Chip spec={LINK[s.link]} big /></div>
        <div className="nodes">
          {s.nodes.map(n => (
            <Chip key={n.id} spec={NODE[n.state]}>
              {n.id}{n.last_seen_ms !== null && n.state !== "offline" ? ` · ${Math.round(n.last_seen_ms / 1000)}s` : ""}
            </Chip>
          ))}
        </div>
      </div>
      <div className="stat" title={`Estimate: measured draw against an assumed ${s.projection_assumes_wh ?? "?"} Wh cell`}>
        <div className="k">Battery</div>
        <div className="v">{fmtNum(s.battery_pct, 1, "%")}</div>
        <div className="m">
          {life !== null ? <>about <b>{life.toFixed(life < 10 ? 1 : 0)} days</b> left at this draw (est.)</> : "no draw reading yet"}
        </div>
      </div>
      <div className="stat">
        <div className="k">Draw now</div>
        <div className="v">{fmtNum(s.power_mw, 0, "mW")}</div>
        <div className="m">
          {multiple !== null ? <><b>{multiple.toFixed(1)}&times;</b> idle ({s.baseline_mw?.toFixed(0)} mW)</> : "no idle baseline yet"}
        </div>
      </div>
      <div className="stat">
        <div className="k">EnergyGate budget</div>
        <div className="v">{fmtNum(s.budget_j, 1, s.budget_max_j ? `/ ${s.budget_max_j} J` : "J")}</div>
        {budgetPct !== null ? <div className="budget"><div style={{ width: `${budgetPct}%` }} /></div>
          : <div className="m">reported by field-1 (via the gateway) once EnergyGate runs</div>}
      </div>
    </div>
  );
}

// -- demo controls -------------------------------------------------------------

const MODE_LABEL: Record<Mode, string> = { none: "No defence", ratelimit: "Rate limit", cookie: "Cookie", gate: "EnergyGate" };
const ATTACK_LABEL: Record<AttackProfile, string> = {
  none: "None", loud: "Loud flood", slow_drip: "Slow drip", replay: "Replay", impersonate: "Impersonate", weak_link: "Weak link",
};
const MODES: Mode[] = ["none", "ratelimit", "cookie", "gate"];
const ATTACKS: AttackProfile[] = ["none", "loud", "slow_drip", "replay", "impersonate"];

export function Controls({ s, onChange }: { s: Status | null; onChange: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); setErr(null); onChange(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <div className="card">
      <div className="controls">
        <div className="ctl">
          <span className="ctl-label">Defence</span>
          <span className="seg">
            {MODES.map(m => (
              <button key={m} className={s?.mode === m ? "on" : ""} onClick={() => act(() => api.setMode(m))}>{MODE_LABEL[m]}</button>
            ))}
          </span>
        </div>
        <div className="ctl">
          <span className="ctl-label">Attack</span>
          <span className="seg">
            {ATTACKS.map(a => (
              <button key={a} className={s?.attack_profile === a ? "on" : ""} onClick={() => act(() => api.setAttack(a))}>{ATTACK_LABEL[a]}</button>
            ))}
          </span>
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn ghost" title="Controls reach the boards over serial as DEFENSE / MODE lines (about 1 s)"
          onClick={() => { if (confirm("Clear events and energy samples, and switch the controls off? Finished experiment rows are kept.")) act(api.reset); }}>
          Reset demo
        </button>
      </div>
      {err && <div className="err" style={{ marginTop: 14 }}>{err}</div>}
    </div>
  );
}

// -- incidents + attack chain ---------------------------------------------------

const STAGES: { key: Stage; label: string }[] = [
  { key: "inbox", label: "Inbox" }, { key: "endpoint", label: "Endpoint" },
  { key: "field", label: "Field network" }, { key: "physical", label: "Physical" },
];

export function Incidents({ incidents, error, bare }: { incidents: Incident[] | null; error: string | null; bare?: boolean }) {
  return (
    <Card title="Incidents" hint="correlation is rules, not ML — the ML is in the detectors" bare={bare}>
      {error && <div className="err">{error}</div>}
      {!incidents?.length ? (
        <div className="empty">No incidents. Clean scans, rekeys and EnergyGate decisions never form one.</div>
      ) : incidents.slice(0, 3).map(inc => (
        <div className="incident" key={inc.id}>
          <div className="inc-head">
            <SeverityChip s={inc.severity} />
            <span className="inc-title">{inc.title}</span>
            <span className="inc-meta">{fmtTime(inc.started_ts)}&ndash;{fmtTime(inc.last_ts)} &middot; {inc.event_ids.length} alerts</span>
          </div>
          <div className="chain">
            {STAGES.map((st, i) => {
              const hit = inc.stages[st.key] === "hit";
              return [
                <div key={st.key} className={`stage${hit ? " hit" : ""}`}>
                  <span className="ico" aria-hidden>{hit ? "✖" : "○"}</span>{st.label}
                  <div style={{ fontSize: "0.72rem", fontWeight: 600 }}>{hit ? "HIT" : "clear"}</div>
                </div>,
                i < STAGES.length - 1 ? <span key={`${st.key}-a`} className="arrow">&rarr;</span> : null,
              ];
            })}
          </div>
          {inc.escalated_by?.length ? (
            <div className="why"><b>Why {inc.severity}:</b> base {inc.base_severity} &rarr; {inc.severity} &mdash; {inc.escalated_by.join("; ")}</div>
          ) : null}
          <div>{inc.techniques.map(t => <span key={t} className="tag" title={t}>{techniqueLabel(t)}</span>)}</div>
        </div>
      ))}
    </Card>
  );
}

// -- EnergyGate decision feed ------------------------------------------------------

export function GateFeed({ events }: { events: SmEvent[] }) {
  const gate = events.filter(e => e.type === "gate_decision");
  const counts = gate.reduce<Record<string, number>>((c, e) => {
    const a = String(e.details?.action ?? "?"); c[a] = (c[a] ?? 0) + 1; return c;
  }, {});
  return (
    <Card title="EnergyGate decisions" hint="one per admission decision · P(real) is the model's probability the sender is genuine">
      <div className="legend" style={{ marginBottom: 10 }}>
        {(["spend", "challenge", "drop"] as const).map(a => (
          <span key={a}><Chip spec={ACTION[a]} /> <b>{counts[a] ?? 0}</b></span>
        ))}
      </div>
      <div className="feed short">
        {gate.length ? gate.slice(0, 60).map(e => <EventRow key={e.id} e={e} compact />)
          : <div className="empty">No decisions yet. Switch the defence to EnergyGate while an attack runs.</div>}
      </div>
    </Card>
  );
}

// -- timeline -----------------------------------------------------------------------

export function Timeline({ events, error, bare }: { events: SmEvent[]; error: string | null; bare?: boolean }) {
  const [showGate, setShowGate] = useState(false);
  const shown = showGate ? events : events.filter(e => e.type !== "gate_decision");
  return (
    <Card title="Timeline" bare={bare} hint={
      <label className="toggle"><input type="checkbox" checked={showGate} onChange={e => setShowGate(e.target.checked)} />
        include EnergyGate decisions</label>}>
      {error && <div className="err">{error}</div>}
      <div className="feed">
        {shown.length ? shown.slice(0, 120).map(e => <EventRow key={e.id} e={e} />)
          : <div className="empty">No events yet. Run <code>python tools/mock_events.py</code> to replay the demo story.</div>}
      </div>
    </Card>
  );
}
