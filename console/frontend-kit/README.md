# SentinelMesh console — frontend kit

> **Stood up (2026-09-18):** the running app built from this kit is
> `console/web/` — `npm run build` there, and the console API serves it at
> http://127.0.0.1:8000/. This folder stays as the reference: the fixtures, and
> `src/types.ts` / `src/api.ts`, which `web/src/` copies verbatim (keep them
> identical). The types were updated for the implemented backend: nullable
> numbers where there may be no data yet, a `link: "offline"` state, SIMULATED
> flags, and the extra attack profiles — see the header of `src/types.ts`.
> Also: use `http://127.0.0.1:8000` in the proxy below, not `localhost`
> (~2 s per request on this Windows machine), and the backend already serves
> everything under `/api`, so no path rewrite is needed.

Everything here is for the person building the UI. You can start **before the backend exists**.

## Start now, with no backend

    npm create vite@latest console-ui -- --template react-ts
    cd console-ui && npm i recharts
    # copy this kit:
    #   fixtures/*  ->  public/fixtures/
    #   src/types.ts, src/api.ts -> src/
    echo "VITE_USE_FIXTURES=1" > .env.local
    npm run dev

Every screen reads through `src/api.ts`. With `VITE_USE_FIXTURES=1` it serves the JSON in
`public/fixtures/`, so the whole UI can be built and styled with realistic data. When the backend
is up, delete that line (or set it to 0) and add a dev proxy so `/api` reaches `http://localhost:8000`:

    // vite.config.ts
    server: { proxy: { "/api": "http://localhost:8000" } }

Nothing else in the UI changes.

## The rules that matter

1. **Never invent a field.** `src/types.ts` mirrors the team's contract. If you need something that
   isn't there, ask for a contract change; don't compute it in the UI.
2. **Always show `reasons`.** Every alert carries up to three. Judges ask "why did it say that?" —
   the answer must be on screen, not in someone's head.
3. **Poll, don't stream.** 1 s for status/energy/events, 3 s for incidents. Keep the last `ts` you saw
   and pass it as `since`.
4. **Readable from three metres.** This gets shown on a projector: big type, dark background, no
   thin grey text for anything that matters.
5. **Never use colour alone.** Severity gets an icon and a word too.
6. **One y-axis per chart.** Never plot battery % and power draw on the same pair of axes; use two charts.

## Fixture data

| File | What it stands in for |
|---|---|
| `events.json` | The full demo story, 11 events across all four layers |
| `incidents.json` | Those events grouped into one incident |
| `status.json` | The top bar: link state, battery, draw, mode, per-node state |
| `energy.json` | 10 min of power samples, with markers for "attack starts" and "EnergyGate on" |
| `experiment.json` | The five-condition results table (placeholder numbers) |
| `scan_examples.json` | What the scan page gets back |

**The numbers in `energy.json` and `experiment.json` are made up** so you can build the charts.
The real ones come from the measurement rig. Don't quote them anywhere.
