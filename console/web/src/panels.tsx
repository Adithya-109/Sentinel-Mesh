import { useState } from "react";
import { api } from "./api";
import TiltCard from "./components/TiltCard";
import type { AttackProfile, Channel, ClassifyResult, Incident, Mode, SmEvent, Stage, Status } from "./types";
import { ACTION, Card, Chip, EventRow, fmtNum, fmtTime, LINK, NODE, SeverityChip, techniqueName } from "./ui";

// -- status bar ---------------------------------------------------------------

export function StatusBar({ s }: { s: Status | null }) {
  if (!s) return <div className="statusbar"><div className="stat"><div className="k">status</div><div className="v">&mdash;</div></div></div>;
  const multiple = s.power_mw !== null && s.baseline_mw ? s.power_mw / s.baseline_mw : null;
  const budgetPct = s.budget_j !== null && s.budget_max_j ? Math.max(0, Math.min(100, (100 * s.budget_j) / s.budget_max_j)) : null;
  return (
    <div className="statusbar">
      <TiltCard maxTilt={3} glare={false}><div className="stat">
        <div className="k">Field link</div>
        <div style={{ marginTop: 6 }}><Chip spec={LINK[s.link]} big /></div>
        <div className="nodes">
          {s.nodes.map(n => (
            <Chip key={n.id} spec={NODE[n.state]}>
              {n.id}{n.last_seen_ms !== null && n.state !== "offline" ? ` · ${Math.round(n.last_seen_ms / 1000)}s` : ""}
            </Chip>
          ))}
        </div>
      </div></TiltCard>
      <TiltCard maxTilt={3} glare={false}><div className="stat">
        <div className="k">Battery</div>
        <div className="v">{fmtNum(s.battery_pct, 1, "%")}</div>
        <div className="m">crypto {s.crypto_level ? `ML-KEM-${s.crypto_level}` : "—"}</div>
      </div></TiltCard>
      <TiltCard maxTilt={3} glare={false}><div className="stat">
        <div className="k">Draw now</div>
        <div className="v">{fmtNum(s.power_mw, 0, "mW")}</div>
        <div className="m">
          {multiple !== null ? <><b>{multiple.toFixed(1)}&times;</b> idle ({s.baseline_mw?.toFixed(0)} mW)</> : "no idle baseline yet"}
        </div>
      </div></TiltCard>
      <TiltCard maxTilt={3} glare={false}><div className="stat" title={`Estimate: measured draw against an assumed ${s.projection_assumes_wh ?? "?"} Wh cell`}>
        <div className="k">Projected life (est.)</div>
        <div className="v">{fmtNum(s.projected_days, s.projected_days !== null && s.projected_days < 10 ? 1 : 0, "days")}</div>
        <div className="m">at idle: {s.projected_days_idle !== null ? `${s.projected_days_idle.toFixed(1)} days` : "—"}</div>
      </div></TiltCard>
      <TiltCard maxTilt={3} glare={false}><div className="stat">
        <div className="k">EnergyGate budget</div>
        <div className="v">{fmtNum(s.budget_j, 1, s.budget_max_j ? `/ ${s.budget_max_j} J` : "J")}</div>
        {budgetPct !== null ? <div className="budget"><div style={{ width: `${budgetPct}%` }} /></div>
          : <div className="m">reported by field-1 (via the gateway) once EnergyGate runs</div>}
      </div></TiltCard>
      <TiltCard maxTilt={3} glare={false}><div className="stat">
        <div className="k">Defence / attack</div>
        <div className="v" style={{ fontSize: "1.25rem", marginTop: 4 }}>{MODE_LABEL[s.mode]}</div>
        <div className="m">attack: <b>{ATTACK_LABEL[s.attack_profile]}</b></div>
      </div></TiltCard>
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
    <div className="card full">
      <div className="controls">
        <div>
          <span className="ctl-label">Defence</span>
          <span className="seg">
            {MODES.map(m => (
              <button key={m} className={s?.mode === m ? "on" : ""} onClick={() => act(() => api.setMode(m))}>{MODE_LABEL[m]}</button>
            ))}
          </span>
        </div>
        <div>
          <span className="ctl-label">Attack</span>
          <span className="seg">
            {ATTACKS.map(a => (
              <button key={a} className={s?.attack_profile === a ? "on" : ""} onClick={() => act(() => api.setAttack(a))}>{ATTACK_LABEL[a]}</button>
            ))}
          </span>
        </div>
        <span className="line">relayed to the boards over serial as DEFENSE / MODE lines (~1 s)</span>
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => { if (confirm("Clear events and energy samples, and switch the controls off? Finished experiment rows are kept.")) act(api.reset); }}>
          Reset demo
        </button>
      </div>
      {err && <div className="err" style={{ marginTop: 8 }}>{err}</div>}
    </div>
  );
}

// -- incidents + attack chain ---------------------------------------------------

const STAGES: { key: Stage; label: string }[] = [
  { key: "inbox", label: "Inbox" }, { key: "endpoint", label: "Endpoint" },
  { key: "field", label: "Field network" }, { key: "physical", label: "Physical" },
];

export function Incidents({ incidents, error }: { incidents: Incident[] | null; error: string | null }) {
  return (
    <Card title="Incidents" hint="correlation is rules, not ML — the ML is in the detectors">
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
          <div>{inc.techniques.map(t => <span key={t} className="tag">{techniqueName(t)}</span>)}</div>
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
      <div className="legend" style={{ marginBottom: 6 }}>
        {(["spend", "challenge", "drop"] as const).map(a => (
          <span key={a}><Chip spec={ACTION[a]} /> <b>{counts[a] ?? 0}</b></span>
        ))}
      </div>
      <div className="feed short">
        {gate.length ? gate.slice(0, 60).map(e => <EventRow key={e.id} e={e} />)
          : <div className="empty">No decisions yet. Switch the defence to EnergyGate while an attack runs.</div>}
      </div>
    </Card>
  );
}

// -- Detection Channels --------------------------------------------------------
// channels/*/manifest.json, api/channels.py. Proves the architecture scales to
// a channel beyond email/file without touching MailGuard or FileGuard: SMS is
// the one real, trained channel here; everything else is visibly a demo.

const fmtPct = (v: unknown) => (typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—");

function ChannelToggle({ c, busy, onToggle }: { c: Channel; busy: boolean; onToggle: () => void }) {
  return (
    <button className={`channel-toggle${c.enabled ? " on" : ""}`} disabled={busy} onClick={onToggle}
      title={c.enabled ? "Turn this channel off" : "Turn this channel on"}>
      {c.enabled ? "Enabled" : "Disabled"}
    </button>
  );
}

export function DetectionChannels({ channels, error, onChange }: {
  channels: Channel[] | null; error: string | null; onChange: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toggleErr, setToggleErr] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [result, setResult] = useState<ClassifyResult | null>(null);
  const [classifyErr, setClassifyErr] = useState<string | null>(null);

  const toggle = async (id: string) => {
    setBusyId(id); setToggleErr(null);
    try { await api.toggleChannel(id); onChange(); }
    catch (e) { setToggleErr(e instanceof Error ? e.message : String(e)); }
    setBusyId(null);
  };

  const runClassify = async () => {
    setClassifying(true); setClassifyErr(null); setResult(null);
    try { setResult(await api.classify("sms", text)); }
    catch (e) { setClassifyErr(e instanceof Error ? e.message : String(e)); }
    setClassifying(false);
  };

  const reference = channels?.filter(c => c.id === "email" || c.id === "file") ?? [];
  const sms = channels?.find(c => c.id === "sms");
  const dummy = channels?.filter(c => c.status === "dummy") ?? [];

  return (
    <Card title="Detection Channels" hint="pluggable registry (channels/*/manifest.json) — adding a channel is a folder, not a code change">
      {error && <div className="err">{error}</div>}
      {toggleErr && <div className="err">{toggleErr}</div>}
      {!channels && <div className="empty">Loading channels&hellip;</div>}
      <div className="channel-grid">
        {reference.map(c => (
          <div className="channel-card" key={c.id}>
            <div className="channel-head">
              <b>{c.display_name}</b>
              <span className="chip" style={{ color: "var(--good)" }}>always on</span>
            </div>
            <div className="small">{c.description}</div>
            <div className="small" style={{ marginTop: 6 }}>
              Live-tested on the <b>Scan</b> tab ({c.test_endpoint}) — not through this panel.
            </div>
          </div>
        ))}

        {sms && (
          <div className="channel-card wide">
            <div className="channel-head">
              <b>{sms.display_name}</b>
              <ChannelToggle c={sms} busy={busyId === sms.id} onToggle={() => toggle(sms.id)} />
            </div>
            <div className="small">{sms.description}</div>
            <div className="channel-metrics">
              <span>accuracy <b>{fmtPct(sms.metrics.accuracy)}</b></span>
              <span>precision <b>{fmtPct(sms.metrics.precision_smishing)}</b></span>
              <span>recall <b>{fmtPct(sms.metrics.recall_smishing)}</b></span>
            </div>
            <div className="small" style={{ marginTop: 4 }}>{String(sms.metrics.trained_on ?? "")}</div>

            <div style={{ marginTop: 12 }}>
              <textarea value={text} onChange={e => setText(e.target.value)}
                placeholder="Paste an SMS message to test" style={{ minHeight: 70 }} />
              <div className="scan-row">
                <button className="btn primary" disabled={classifying || !sms.enabled || !text.trim()} onClick={runClassify}>
                  Test a message
                </button>
                {!sms.enabled && <span className="small">channel is disabled — toggle it on first</span>}
                {classifying && <span className="small">scoring&hellip;</span>}
              </div>
              {classifyErr && <div className="err" style={{ marginTop: 6 }}>{classifyErr}</div>}
              {result && (
                <div className="ev" style={{ marginTop: 6 }}>
                  <div>
                    <span className="chip" style={{ color: result.label === "smishing" ? "var(--critical)" : "var(--good)" }}>
                      {result.label === "smishing" ? "✖" : "✔"} {result.label}
                    </span>
                  </div>
                  <div className="body">
                    <div className="sum">confidence <span className="prob">{result.confidence.toFixed(2)}</span></div>
                    {result.reasons.length > 0 && (
                      <ul className="reasons">{result.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {dummy.map(c => (
          <div className="channel-card" key={c.id}>
            <div className="channel-head">
              <b>{c.display_name}</b>
              <ChannelToggle c={c} busy={busyId === c.id} onToggle={() => toggle(c.id)} />
            </div>
            <span className="badge-demo">Demo data &mdash; not trained</span>
            <div className="small" style={{ marginTop: 6 }}>{c.description}</div>
            <div className="channel-metrics">
              <span>accuracy <b>{fmtPct(c.metrics.accuracy)}</b></span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// -- timeline -----------------------------------------------------------------------

export function Timeline({ events, error }: { events: SmEvent[]; error: string | null }) {
  const [showGate, setShowGate] = useState(false);
  const shown = showGate ? events : events.filter(e => e.type !== "gate_decision");
  return (
    <Card title="Timeline" hint={
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
