// One place for every call. Set VITE_USE_FIXTURES=1 to develop with no backend running.
// The live copy the app compiles is console/web/src/api.ts; keep the two identical.
import type { SmEvent, Incident, Status, EnergySeries, Experiment, Mode, AttackProfile } from "./types";

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === "1";
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function getJson<T>(path: string, fixture: string): Promise<T> {
  if (USE_FIXTURES) return (await fetch(`/fixtures/${fixture}`)).json();
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (USE_FIXTURES) return { ok: true, fixture: true } as T;
  const r = await fetch(`${BASE}${path}`, {
    method, headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `${path} -> ${r.status}`);
  return data as T;
}

export const api = {
  // Poll every 1000 ms. `since` is exclusive; 0 returns the newest page.
  events: (since = 0) => getJson<SmEvent[]>(`/events?since=${since}&limit=200`, "events.json"),
  incidents: () => getJson<Incident[]>("/incidents", "incidents.json"),
  status: () => getJson<Status>("/status", "status.json"),
  // Poll every 1000 ms during the demo. `since` keeps the payload small.
  energy: (since = 0) => getJson<EnergySeries>(`/energy?since=${since}`, "energy.json"),
  experiment: (profile?: string) =>
    getJson<Experiment>(`/experiment${profile ? `?profile=${profile}` : ""}`, "experiment.json"),

  scanEmail: async (text: string): Promise<SmEvent[]> => {
    if (USE_FIXTURES) return (await (await fetch("/fixtures/scan_examples.json")).json()).email;
    return send<SmEvent[]>("POST", "/scan/email", { text });
  },
  scanFile: async (file: File): Promise<SmEvent[]> => {
    if (USE_FIXTURES) return (await (await fetch("/fixtures/scan_examples.json")).json()).file;
    const fd = new FormData(); fd.append("file", file);
    const r = await fetch(`${BASE}/scan/file`, { method: "POST", body: fd });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `scan -> ${r.status}`);
    return data;
  },

  // Demo controls. The console relays these to the boards over serial
  // (DEFENSE <mode> / MODE <...>), so they can take ~1 s to take effect.
  setMode: (mode: Mode) => send("POST", "/mode", { mode }),
  setAttack: (profile: AttackProfile) => send("POST", "/attack", { profile }),
  runExperiment: (condition: string, profile: string, duration_s?: number) =>
    send("POST", "/experiment/run", { condition, profile, duration_s }),
  stopExperiment: () => send("POST", "/experiment/stop"),
  reset: () => send("POST", "/reset"),
};

// Shared display helpers — keep severity styling in ONE place.
export const SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"] as const;
export const LAYER_LABEL = { mail: "Inbox", file: "Endpoint", field: "Field link", tamper: "Physical" } as const;
