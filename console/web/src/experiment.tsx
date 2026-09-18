import { useState } from "react";
import { api } from "./api";
import type { Experiment, SmEvent } from "./types";
import { Card, EventRow } from "./ui";

const STATUS_WORD = { pending: "○ pending", running: "▶ running", done: "✔ done" } as const;

export function ExperimentTable({ exp, error, profile, setProfile, onChange }: {
  exp: Experiment | null; error: string | null; profile: string;
  setProfile: (p: string) => void; onChange: () => void;
}) {
  const [duration, setDuration] = useState(120);
  const [err, setErr] = useState<string | null>(null);
  const running = exp?.running ?? null;
  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); setErr(null); onChange(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  const secsLeft = running ? Math.max(0, Math.round((running.ends_ts - Date.now()) / 1000)) : 0;
  const n = (v: number | null, d = 0) => (v === null ? <span className="dash">&mdash;</span> : v.toFixed(d));

  return (
    <Card title="Energy experiment" hint="brief v4 §6 — one run per condition, same attack profile">
      <div className="controls" style={{ marginBottom: 10 }}>
        <div>
          <span className="ctl-label">Attack profile</span>
          <span className="seg">
            {(exp?.profiles ?? ["loud", "slow_drip"]).map(p => (
              <button key={p} className={profile === p ? "on" : ""} onClick={() => setProfile(p)}>{p === "slow_drip" ? "Slow drip" : "Loud"}</button>
            ))}
          </span>
        </div>
        <label className="small">run length&nbsp;
          <input type="number" min={5} max={3600} value={duration} onChange={e => setDuration(Number(e.target.value))}
            style={{ width: 80, background: "var(--page)", border: "1px solid var(--axis)", borderRadius: 6, padding: "4px 6px" }} /> s
        </label>
        {running && <span><b>running:</b> {running.condition} ({running.profile}) &mdash; {secsLeft}s left&nbsp;
          <button className="btn" onClick={() => act(api.stopExperiment)}>Stop now</button></span>}
      </div>
      {error && <div className="err">{error}</div>}
      <table>
        <thead>
          <tr>
            <th>Condition</th><th className="num">Energy (J/h)</th><th className="num">Projected days (est.)</th>
            <th className="num">Legit connect %</th><th className="num">Legit extra delay (ms)</th><th>Status</th><th />
          </tr>
        </thead>
        <tbody>
          {(exp?.rows ?? []).map(r => (
            <tr key={r.condition}>
              <td><b>{r.label}</b> {r.source === "simulated" && <span className="sim">SIMULATED</span>}</td>
              <td className="num">{n(r.energy_j_per_hour, 0)}</td>
              <td className="num">{n(r.projected_days, r.projected_days !== null && r.projected_days < 10 ? 1 : 0)}</td>
              <td className="num">{n(r.legit_connect_pct, 0)}</td>
              <td className="num">{n(r.legit_extra_delay_ms, 0)}</td>
              <td>{STATUS_WORD[r.status]}</td>
              <td>
                <button className="btn" disabled={!!running}
                  onClick={() => act(() => api.runExperiment(r.condition, profile, duration))}>
                  {r.status === "done" ? "Re-run" : "Run"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {err && <div className="err" style={{ marginTop: 8 }}>{err}</div>}
      {exp?.note && <div className="note">{exp.note}</div>}
    </Card>
  );
}

export function Scan({ onStored }: { onStored: () => void }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SmEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<SmEvent[]>) => {
    setBusy(true); setErr(null);
    try { setResult(await fn()); onStored(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };

  return (
    <Card title="Scan" hint="the console calls the ML service and stores the verdict · benign files only, never live malware">
      <textarea value={text} onChange={e => setText(e.target.value)} placeholder="Paste an email (subject and body)" />
      <div className="scan-row">
        <button className="btn primary" disabled={busy || !text.trim()} onClick={() => run(() => api.scanEmail(text))}>Scan email</button>
        <input type="file" onChange={e => setFile(e.target.files?.[0] ?? null)} />
        <button className="btn" disabled={busy || !file} onClick={() => file && run(() => api.scanFile(file))}>Scan file</button>
        {busy && <span className="small">scoring&hellip;</span>}
      </div>
      {err && <div className="err" style={{ marginTop: 8 }}>{err}</div>}
      {result.map(e => <EventRow key={e.id} e={e} />)}
    </Card>
  );
}
