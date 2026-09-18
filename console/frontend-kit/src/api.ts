// One place for every call. Set VITE_USE_FIXTURES=1 to develop with no backend running.
import type { SmEvent, Incident, Status, EnergySeries, Experiment } from "./types";

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === "1";
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function getJson<T>(path: string, fixture: string): Promise<T> {
  if (USE_FIXTURES) return (await fetch(`/fixtures/${fixture}`)).json();
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const api = {
  // Poll every 1000 ms. Pass the newest ts you already hold, so you only fetch what is new.
  events: (since = 0) => getJson<SmEvent[]>(`/events?since=${since}&limit=200`, "events.json"),
  incidents: () => getJson<Incident[]>("/incidents", "incidents.json"),
  status: () => getJson<Status>("/status", "status.json"),
  // Poll every 1000 ms during the demo. `since` keeps the payload small.
  energy: (since = 0) => getJson<EnergySeries>(`/energy?since=${since}`, "energy.json"),
  experiment: () => getJson<Experiment>("/experiment", "experiment.json"),

  scanEmail: async (text: string): Promise<SmEvent[]> => {
    if (USE_FIXTURES) return (await (await fetch("/fixtures/scan_examples.json")).json()).email;
    const r = await fetch(`${BASE}/scan/email`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    return r.json();
  },
  scanFile: async (file: File): Promise<SmEvent[]> => {
    if (USE_FIXTURES) return (await (await fetch("/fixtures/scan_examples.json")).json()).file;
    const fd = new FormData(); fd.append("file", file);
    return (await fetch(`${BASE}/scan/file`, { method: "POST", body: fd })).json();
  },

  // Demo controls. These reach the boards over serial, so they can take ~1 s to take effect.
  setMode: (mode: Status["mode"]) => post("/mode", { mode }),
  setAttack: (profile: Status["attack_profile"]) => post("/attack", { profile }),
  runExperiment: (condition: string, profile: string) => post("/experiment/run", { condition, profile }),
};

async function post(path: string, body: unknown) {
  if (USE_FIXTURES) return { ok: true, fixture: true };
  return (await fetch(`${BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  })).json();
}

// Shared display helpers — keep severity styling in ONE place.
export const SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"] as const;
export const LAYER_LABEL = { mail: "Inbox", file: "Endpoint", field: "Field link", tamper: "Physical" } as const;
