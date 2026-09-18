// Polling (kit rule 3: poll, don't stream). 1 s for status/energy/events,
// 3 s for incidents and the experiment table.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { EnergySample, EnergySeries, SmEvent } from "./types";

export function usePoll<T>(fn: () => Promise<T>, ms: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const refresh = useCallback(async () => {
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    let live = true;
    let busy = false;
    const tick = async () => {
      if (busy || !live) return;       // never stack requests on a slow backend
      busy = true;
      await refresh();
      busy = false;
    };
    tick();
    const id = setInterval(tick, ms);
    return () => { live = false; clearInterval(id); };
  }, [ms, refresh]);

  return { data, error, refresh };
}

const RESYNC_EVERY = 10;   // polls; a full refetch catches an external reset
const KEEP_EVENTS = 400;

/** Events, merged incrementally by id, newest first. */
export function useEvents() {
  const [events, setEvents] = useState<SmEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const state = useRef({ lastTs: 0, n: 0 });

  const poll = useCallback(async (full = false) => {
    const s = state.current;
    const resync = full || s.lastTs === 0 || s.n % RESYNC_EVERY === 0;
    s.n += 1;
    try {
      // 2 s of overlap, deduped by id: catches same-millisecond and slightly
      // out-of-order arrivals that an exclusive `since` would skip
      const batch = await api.events(resync ? 0 : Math.max(1, s.lastTs - 2000));
      setEvents(prev => {
        const byId = new Map((resync ? [] : prev).map(e => [e.id, e]));
        for (const e of batch) byId.set(e.id, e);
        const merged = [...byId.values()].sort((a, b) => b.ts - a.ts).slice(0, KEEP_EVENTS);
        s.lastTs = merged.length ? merged[0].ts : 0;
        return merged;
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    poll(true);
    const id = setInterval(() => poll(), 1000);
    return () => clearInterval(id);
  }, [poll]);

  return { events, error, resync: () => poll(true) };
}

const KEEP_SAMPLES = 600;   // 10 minutes at 1 Hz

/** Energy samples + markers, merged incrementally. */
export function useEnergy() {
  const [series, setSeries] = useState<EnergySeries>({ samples: [], markers: [] });
  const state = useRef({ lastTs: 0, n: 0 });

  const poll = useCallback(async (full = false) => {
    const s = state.current;
    const resync = full || s.lastTs === 0 || s.n % (RESYNC_EVERY * 3) === 0;
    s.n += 1;
    try {
      const got = await api.energy(resync ? 0 : s.lastTs);
      setSeries(prev => {
        const base: EnergySample[] = resync ? [] : prev.samples;
        const byTs = new Map(base.map(x => [x.ts, x]));
        for (const x of got.samples) byTs.set(x.ts, x);
        const samples = [...byTs.values()].sort((a, b) => a.ts - b.ts).slice(-KEEP_SAMPLES);
        const mk = new Map((resync ? [] : prev.markers).map(m => [`${m.ts}|${m.label}`, m]));
        for (const m of got.markers) mk.set(`${m.ts}|${m.label}`, m);
        s.lastTs = samples.length ? samples[samples.length - 1].ts : 0;
        return {
          samples,
          markers: [...mk.values()].sort((a, b) => a.ts - b.ts),
          simulated: samples.some(x => x.source === "sim"),
        };
      });
    } catch {
      /* the status bar already reports a dead backend */
    }
  }, []);

  useEffect(() => {
    poll(true);
    const id = setInterval(() => poll(), 1000);
    return () => clearInterval(id);
  }, [poll]);

  return { series, resync: () => poll(true) };
}
