// Energy charts. Rules applied (kit + dataviz method):
//  - one y-axis per chart: power and battery are two charts, never one
//  - 2px lines, no dots, recessive grid, linear interpolation (no invented smoothness)
//  - hover tooltip on every chart; markers are labelled reference lines
//  - the projection's three series use the validated categorical slots, are
//    direct-labelled at their end points, and have a legend
import {
  CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { EnergySeries, Experiment } from "./types";
import { fmtTime } from "./ui";

// SVG presentation attributes do not reliably resolve CSS var(), so the chart
// uses the same hex values as the :root tokens in styles.css.
const C = {
  ink: "#ffffff", ink2: "#c3c2b7", muted: "#898781", grid: "#2c2c2a", axis: "#383835",
  s1: "#3987e5", s2: "#d95926", s3: "#199e70",
};

const axisProps = {
  stroke: C.axis, tick: { fill: C.ink2, fontSize: 13 }, tickLine: false,
} as const;

type TTProps = { active?: boolean; label?: number; payload?: { name?: string; value?: number; color?: string }[] };

function makeTooltip(headFmt: (v: number) => string, unit: string, digits: number,
                     extra?: (label: number) => string[]) {
  return function TT({ active, label, payload }: TTProps) {
    if (!active || !payload?.length || label === undefined) return null;
    return (
      <div className="tt">
        <div className="tt-h">{headFmt(label)}</div>
        {extra?.(label).map((x, i) => <div key={i} style={{ color: C.ink2 }}>&#9662; {x}</div>)}
        {payload.filter(p => p.value !== null && p.value !== undefined).map(p => (
          <div key={p.name}><span style={{ color: p.color }}>&#9644;</span> {p.name}: <b>{Number(p.value).toFixed(digits)} {unit}</b></div>
        ))}
      </div>
    );
  };
}

/** Every control change is a line; only markers with room get a text label.
 * Controls pressed seconds apart (an experiment run, a demo beat) would
 * otherwise stack their labels into an unreadable smear. */
const MAX_LABELS = 2;
const LABEL_CHARS = 18;

function Markers({ series, from, to }: { series: EnergySeries; from: number; to: number }) {
  // Newest first: the latest change ("EnergyGate on") is the one the audience
  // needs to read. A label needs about a third of a half-width chart to itself.
  const minGap = Math.max(1, (to - from) * 0.34);
  let lastLabelled = Infinity;
  let labelled = 0;
  const inRange = series.markers.filter(m => m.ts >= from && m.ts <= to);
  const shown = [...inRange].reverse().map(m => {
    const quiet = m.label.startsWith("experiment done");
    const ok = !quiet && labelled < MAX_LABELS && lastLabelled - m.ts >= minGap;
    const text = m.label.replace(/^experiment: /, "run: ");
    const label = ok ? (text.length > LABEL_CHARS ? `${text.slice(0, LABEL_CHARS - 1)}…` : text) : null;
    if (label) { lastLabelled = m.ts; labelled += 1; }
    return { ...m, label };
  });
  return (
    <>
      {shown.map(m => (
        <ReferenceLine key={`${m.ts}${m.label}`} x={m.ts} stroke={C.ink2} strokeDasharray="3 4"
          label={m.label ? { value: m.label, position: "insideTopLeft", fill: C.ink, fontSize: 13 } : undefined} />
      ))}
    </>
  );
}

/** Markers near the hovered time, listed in the tooltip, so unlabelled lines are still explained. */
function markersNear(series: EnergySeries, ts: number, span: number) {
  return series.markers.filter(m => Math.abs(m.ts - ts) <= span).map(m => m.label);
}

export function PowerChart({ series, baseline }: { series: EnergySeries; baseline: number | null }) {
  const data = series.samples;
  if (!data.length) return <div className="empty">No power samples yet. They arrive as NRG lines from the INA219 monitor board,
    or run <code>python tools/mock_rig.py</code>.</div>;
  const TT = makeTooltip(fmtTime, "mW", 0, ts => markersNear(series, ts, 1500));
  return (
    <div>
      <div className="chart-title">Power draw (mW)</div>
      <div className="chart-sub">dashed line: idle baseline</div>
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={data} margin={{ top: 22, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fmtTime} {...axisProps} minTickGap={50} />
          <YAxis width={52} {...axisProps} domain={[0, "auto"]} />
          <Tooltip content={<TT />} cursor={{ stroke: C.ink2, strokeWidth: 1 }} />
          {baseline !== null && (
            <ReferenceLine y={baseline} stroke={C.muted} strokeDasharray="6 4"
              label={{ value: `idle ${baseline.toFixed(0)} mW`, position: "insideBottomRight", fill: C.ink2, fontSize: 13 }} />
          )}
          <Markers series={series} from={data[0].ts} to={data[data.length - 1].ts} />
          <Line type="linear" dataKey="power_mw" name="draw" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BatteryChart({ series }: { series: EnergySeries }) {
  const data = series.samples.filter(s => s.battery_pct !== null);
  if (!data.length) return <div className="empty">No battery readings yet (battery_pct is optional in NRG lines).</div>;
  const TT = makeTooltip(fmtTime, "%", 2, ts => markersNear(series, ts, 1500));
  return (
    <div>
      <div className="chart-title">Battery (%)</div>
      <div className="chart-sub">measured at the field node</div>
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={data} margin={{ top: 22, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fmtTime} {...axisProps} minTickGap={50} />
          <YAxis width={52} {...axisProps}
            domain={[(min: number) => Math.max(0, Math.floor(min - 0.5)), (max: number) => Math.min(100, Math.ceil(max + 0.5))]} />
          <Tooltip content={<TT />} cursor={{ stroke: C.ink2, strokeWidth: 1 }} />
          <Markers series={series} from={data[0].ts} to={data[data.length - 1].ts} />
          <Line type="linear" dataKey="battery_pct" name="battery" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// -- projection: the pitch chart ------------------------------------------------------

const PROJECTED = [
  { condition: "no_attack", name: "No attack", color: C.s1 },
  { condition: "undefended", name: "Attack, undefended", color: C.s2 },
  { condition: "gate", name: "Attack + EnergyGate", color: C.s3 },
] as const;

export function ProjectionChart({ exp }: { exp: Experiment | null }) {
  const lines = PROJECTED.map(p => ({
    ...p, row: exp?.rows.find(r => r.condition === p.condition && r.status === "done" && r.projected_days !== null),
  })).filter(l => l.row);

  if (!exp || !lines.length) {
    return <div className="empty">Run the experiment below (no attack, undefended, EnergyGate) to draw the projected
      battery life for each condition — brief v4's chart for the pitch.</div>;
  }
  const days = (l: (typeof lines)[number]) => l.row!.projected_days as number;
  const maxDays = Math.max(...lines.map(days)) * 1.05;
  const xs = new Set<number>();
  for (let i = 0; i <= 80; i++) xs.add((maxDays * i) / 80);
  lines.forEach(l => xs.add(days(l)));
  const data = [...xs].sort((a, b) => a - b).map(d => {
    const row: Record<string, number | null> = { d };
    for (const l of lines) row[l.condition] = d <= days(l) ? 100 * (1 - d / days(l)) : null;
    return row;
  });
  const simulated = lines.some(l => l.row!.source === "simulated");
  const TT = makeTooltip(v => `day ${v.toFixed(2)}`, "%", 0);
  const flatDate = (d: number) =>
    new Date(Date.now() + d * 86_400_000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

  return (
    <div>
      <div className="chart-title">
        Projected battery life by condition {simulated && <span className="sim">&nbsp;SIMULATED &mdash; do not quote</span>}
      </div>
      <div className="chart-sub">from each experiment run's measured mean draw, on an assumed full cell &mdash; an estimate, not a measurement of a full discharge</div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 16, right: 60, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="d" type="number" domain={[0, maxDays]} tickFormatter={v => (v === 0 ? "0" : `${Number(v).toFixed(maxDays < 3 ? 1 : 0)} d`)} {...axisProps} />
          <YAxis width={52} domain={[0, 100]} {...axisProps} tickFormatter={v => `${v}%`} />
          <Tooltip content={<TT />} cursor={{ stroke: C.ink2, strokeWidth: 1 }} />
          {lines.map(l => (
            <Line key={l.condition} type="linear" dataKey={l.condition} name={l.name} stroke={l.color}
              strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          ))}
          {lines.map(l => (
            <ReferenceDot key={`${l.condition}-end`} x={days(l)} y={0} r={5} fill={l.color} stroke="#1a1a19" strokeWidth={2}
              label={{ value: `${days(l).toFixed(1)} d`, position: "top", fill: C.ink, fontSize: 13 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="legend">
        {lines.map(l => (
          <span key={l.condition}>
            <span className="sw" style={{ background: l.color }} />{l.name}: flat in <b>{days(l).toFixed(1)} days</b>
            <span className="small"> (~{flatDate(days(l))})</span>
          </span>
        ))}
      </div>
    </div>
  );
}
