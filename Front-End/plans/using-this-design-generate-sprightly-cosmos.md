# Plan: SentinelMesh Landing Page + Dashboard

## Context

The user has provided a Figma design (file `lccAvlgVYbBMv6sjeMJB7u`) with two nodes:
- **1:25** — "Etran" fintech landing page (Money Transfers Made Simple), dark-green theme
- **1:452** — design system style guide (colors, type, buttons, icons)

Plus a SentinelMesh README describing a security console frontend with fixture data already present in `src/imports/`. The task is to build two pages sharing the same design system:
1. `/` → landing page (from Figma node 1:25)
2. `/dashboard` → SentinelMesh security console with live-polling metrics

The codebase is a bare Vite + React 19 + Tailwind v4 scaffold. No routing, no components, no types — just `App.tsx`, `index.css`, `main.tsx`, and the `src/imports/` fixture files.

---

## Design tokens (from Figma)

```
--bg-1:       #394508   (dark green, primary surface)
--bg-2:       #FFFFFF
--bg-3:       #EDEDED
--accent-1:   #D2FD9C   (lime green, highlights)
--accent-2:   #77912A
--accent-3:   #619111
--text-head:  #394508
--text-p1:    #000000
--text-p2:    #5D5D5D
--text-sub:   #CBCBCB
--text-over:  #D9D9D9
--divider:    #E9E9E9
```

Typography: Manrope (primary, both pages), Figtree (dashboard body), Roboto Mono (dashboard monospace).

---

## Implementation steps

### 1. Install dependencies

```
pnpm add react-router-dom recharts
```

- `react-router-dom` — client-side routing between landing and dashboard
- `recharts` — power draw and battery charts (already suggested in README)

### 2. Create `src/imports/types.ts`

Referenced by `api.ts` but missing. Derive shapes from the fixture JSON:

```ts
export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type Layer    = 'mail' | 'file' | 'field' | 'tamper'

export interface SmEvent {
  id: string; ts: number; layer: Layer; type: string
  severity: Severity; score: number | null; node: string | null
  technique: string | null; summary: string; reasons: string[]
  details: Record<string, unknown>
}

export interface Incident {
  id: string; ts: number; severity: Severity
  summary: string; events: string[]
}

export interface NodeStatus {
  id: string; state: string; rssi: number
  battery_pct: number | null; last_seen_ms: number
}

export interface Status {
  ts: number; link: string; crypto_level: number
  battery_pct: number; power_mw: number; baseline_mw: number
  projected_days: number; projected_days_idle: number
  mode: string; attack_profile: string
  budget_j: number; budget_max_j: number
  nodes: NodeStatus[]
}

export interface EnergySample {
  ts: number; power_mw: number; battery_pct: number
  volts: number; amps: number
}

export interface EnergySeries { samples: EnergySample[] }

export interface ExperimentRow {
  condition: string; [metric: string]: unknown
}

export interface Experiment { rows: ExperimentRow[] }
```

### 3. Wire fonts in `src/index.css`

Run `figma fonts resolve` for all required faces, then add `@font-face` rules and a Google Fonts `@import` for any URL-resolved faces. Final font list across both pages:

- Manrope (Regular + Medium) — Google Fonts, add `@import` at top of CSS
- Figtree (Regular) — Google Fonts
- Roboto Mono (Regular) — Google Fonts
- Abhaya Libre Medium, Geist, IBM Plex Sans, Radio Canada Big, Saira — resolve via `figma fonts resolve`

Add CSS custom properties for design tokens in `src/index.css`.

### 4. Set up routing in `src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import Dashboard   from './pages/Dashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"          element={<LandingPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
```

No router provider needed in `main.tsx` (BrowserRouter wraps inside App).

### 5. Copy fixture files to `public/fixtures/`

`api.ts` reads from `/fixtures/*.json` in fixture mode. The JSON files live in `src/imports/`; copy them to `public/fixtures/` so the Vite dev server serves them statically.

Files to copy: `events.json`, `incidents.json`, `status.json`, `energy.json`, `experiment.json`, `scan_examples.json`

Set `VITE_USE_FIXTURES=1` in `.env.local` (create if absent).

### 6. Download design context archives and install assets

**Node 1:25 archive:**
```
dir="/tmp/figma-design-context/1-25"
mkdir -p "$dir"
curl -fL "https://www.figma.com/api/mcp/asset/c14b8780-98ed-4a85-bc20-6ca22625696b.zip" -o "$dir/design_context.zip"
unzip -o "$dir/design_context.zip" -d "$dir"
cp -r "$dir/assets" public/assets
```

Read `design_context.tsx` from the extracted dir; use it as the visual reference.

### 7. Build `src/pages/LandingPage.tsx`

Implement fidelity to node 1:25 screenshot. Sections (top-down):

1. **Nav** — logo "Etran" (left), CTA button "Get started" (right), dark green bg
2. **Hero** — headline "Money Transfers Made Simple", sub-copy, hero image of man smiling, badges row (Trusted · Ranked · #Award · #Rates)
3. **Stats section** — "We accelerate transfer efficiency and productivity"
4. **Features** — "Get More Done In A Week" — 2× stat cards (2x, 130%, etc.) with Recharts bar chart in one card
5. **The Most Reliable App** — dark card with credit card image, tax-form document screenshot
6. **Photo** — full-width lifestyle image
7. **First Class Software** — icon grid (4 icons: Tax Manager, Taxes, Tax Fraud, Transactions)
8. **Download CTA** — dark green section, "Download Etran and manage everything from your phone", CTA button
9. **Footer** — logo, navigation links, tagline

All images from the design archive go into `public/assets/` and are referenced via `assetPathPrefix = "/assets"`.

Use Tailwind v4 utilities. No inline styles except when absolutely necessary.  
Preserve font stacks exactly as returned by `design_context.tsx`.

Add a small "Go to Dashboard →" link in the nav (right of CTA) so judges can navigate.

### 8. Build `src/pages/Dashboard.tsx`

Dark-green theme (#394508 background), big readable text for projector use.

**Layout:** Full-height sidebar nav + main content area.

**Sidebar:** SentinelMesh logo, nav items: Overview, Events, Incidents, Energy, Experiment, Scan.

**Top status bar** (polled every 1 s from `api.status()`):
- Link state badge (color + icon + word)
- Crypto level (ML-KEM-XXXX)
- Battery % with color indicator
- Power draw vs baseline (mW)
- Projected days remaining
- Mode / attack profile

**Per-node status row** — one badge per node (id, state, rssi, battery, last seen).

**Events feed** (polled every 1 s, `api.events(since)`):
- Table: timestamp, layer (Inbox/Endpoint/Field link/Physical), severity badge (icon + word + color), summary, reasons (up to 3 shown inline)
- Color-coded rows by severity but never color alone — always icon + word
- Severity icons: ℹ info, ⚠ low, ⚡ medium, 🔴 high, ☠ critical

**Incidents panel** (polled every 3 s):
- Card list of incidents, expandable to show linked events

**Energy charts** — two separate charts (one y-axis each):
- Chart A: Power draw (mW) over time — area line chart with a reference line at baseline
- Chart B: Battery % over time — area line chart
- Both use Recharts `<LineChart>` / `<AreaChart>` with `<ReferenceLine>` for event markers

**Experiment table** — `api.experiment()` polled once on mount; renders 5-condition comparison table.

**Scan page** — textarea input for email text + file upload; calls `api.scanEmail` / `api.scanFile`; shows results with reasons.

Use `useInterval` custom hook (uses `setInterval` + cleanup) for polling. Never stream.

### 9. Create shared `src/components/SeverityBadge.tsx`

Reused in both Events feed and node status:

```tsx
const ICONS = { info: 'ℹ', low: '▲', medium: '⚡', high: '🔴', critical: '☠' }
```

Shows icon + capitalized word + background color. Satisfies the "never use colour alone" rule.

---

## Critical files to create / modify

| File | Action |
|---|---|
| `src/imports/types.ts` | Create — type contract |
| `src/App.tsx` | Modify — add BrowserRouter + routes |
| `src/index.css` | Modify — add fonts, CSS tokens |
| `src/pages/LandingPage.tsx` | Create — from Figma node 1:25 |
| `src/pages/Dashboard.tsx` | Create — SentinelMesh console |
| `src/components/SeverityBadge.tsx` | Create — shared severity display |
| `public/fixtures/*.json` | Copy from `src/imports/` |
| `.env.local` | Create/update — `VITE_USE_FIXTURES=1` |
| `public/assets/` | Populate from design context archive |

---

## Verification

1. `pnpm dev` — dev server starts, no TypeScript errors in terminal
2. Visit `/` — landing page renders with dark green theme, hero image, stat cards, all sections visible
3. Visit `/dashboard` — dashboard renders with status bar, events table, two energy charts
4. In browser console — no 404s for fixture JSON files or image assets
5. Energy charts show two separate axes (power_mw spike at t=180s visible, battery % declining)
6. Severity badges show icon + word (not just color)
7. "Go to Dashboard" link in landing nav works; browser back returns to landing
