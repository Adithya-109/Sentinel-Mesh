import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

// A dotted, curving timeline that runs down the landing page. It weaves between
// the sections (always on the side the text is not), draws itself in as you
// scroll, and carries a lead dot that stays near the middle of the screen.
// Milestones light up when the lead dot reaches them.

type Pt = [number, number];
type Stop = { x: number; y: number; n?: string; label?: string; side: "left" | "right" | "top" };
type Geo = { w: number; h: number; d: string; stops: Stop[] };

// A cubic S-curve that leaves and arrives vertically, so the line always runs
// straight through a milestone and swings sideways in between.
const curve = (a: Pt, b: Pt) => {
  const k = (b[1] - a[1]) * 0.55;
  return `C ${a[0]} ${a[1] + k} ${b[0]} ${b[1] - k} ${b[0]} ${b[1]}`;
};

function build(main: HTMLElement): Geo | null {
  const q = (sel: string) => main.querySelector<HTMLElement>(sel);
  const hero = q("#top"), mission = q("#mission"), approach = q("#approach");
  const choose = q(".choose"), grid = q(".choose-grid"), join = q(".join");
  if (!hero || !mission || !approach || !choose || !grid || !join) return null;

  const box = main.getBoundingClientRect();
  const y = (el: HTMLElement, f = 0.5) => { const r = el.getBoundingClientRect(); return r.top - box.top + r.height * f; };
  const w = main.clientWidth;
  const desk = w >= 1024;
  const u = desk ? Math.min(1, w / 1600) : 1;
  const x = (f: number, px: number) => (desk ? w * f : px);

  const p0: Pt = [w * 0.5, y(hero, 1)];
  const p1: Pt = [x(0.84, 6), y(mission)];
  const p2: Pt = [x(0.14, 9), y(approach)];
  const p3: Pt = [x(0.9, 6), y(choose, 0) + 120 * u];
  const p4: Pt = [x(0.94, 9), y(grid, 1) + 50 * u];
  const p3b: Pt = [x(0.955, 5), (p3[1] + p4[1]) / 2];
  const p5: Pt = [w * 0.5, y(join, 0) - 46 * u];

  const d = `M ${p0[0]} ${p0[1]} ` + [[p0, p1], [p1, p2], [p2, p3], [p3, p3b], [p3b, p4], [p4, p5]]
    .map(([a, b]) => curve(a, b)).join(" ");

  const stops: Stop[] = [
    { x: p0[0], y: p0[1], side: "top" },
    { x: p1[0], y: p1[1], n: "01", label: "The problem", side: "left" },
    { x: p2[0], y: p2[1], n: "02", label: "The approach", side: "right" },
    { x: p3[0], y: p3[1], n: "03", label: "Your way in", side: "left" },
    { x: p5[0], y: p5[1], n: "04", label: "See it live", side: "left" },
  ];
  return { w, h: box.height, d, stops };
}

const labelPos = { left: { x: -26, y: 5, a: "end" }, right: { x: 26, y: 5, a: "start" }, top: { x: 0, y: -30, a: "middle" } } as const;

export default function TimelineLine() {
  const svgRef = useRef<SVGSVGElement>(null);
  const baseRef = useRef<SVGPathElement>(null);
  const clipRef = useRef<SVGRectElement>(null);
  const leadRef = useRef<SVGGElement>(null);
  const nodeEls = useRef<(SVGGElement | null)[]>([]);
  const samples = useRef<{ ys: Float32Array; lens: Float32Array; total: number } | null>(null);
  const geoRef = useRef<Geo | null>(null);
  const [geo, setGeo] = useState<Geo | null>(null);

  const measure = useCallback(() => {
    const main = svgRef.current?.parentElement;
    if (!main) return;
    const g = build(main);
    if (!g) return;
    setGeo(prev => (prev && prev.d === g.d && prev.w === g.w && prev.h === g.h ? prev : g));
  }, []);

  const update = useCallback(() => {
    const s = samples.current, g = geoRef.current, base = baseRef.current, main = svgRef.current?.parentElement;
    if (!s || !g || !base || !main) return;
    // the point of the page that sits at 60% of the viewport height, in this container's coordinates
    const target = window.innerHeight * 0.6 - main.getBoundingClientRect().top;
    const { ys, lens, total } = s;
    let len = 0;
    if (target >= ys[ys.length - 1]) len = total;
    else if (target > ys[0]) {
      let lo = 0, hi = ys.length - 1;
      while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (ys[mid] <= target) lo = mid; else hi = mid; }
      const span = ys[hi] - ys[lo] || 1;
      len = lens[lo] + ((target - ys[lo]) / span) * (lens[hi] - lens[lo]);
    }
    const pt = base.getPointAtLength(len);
    // the line only ever runs downward, so revealing it up to the lead dot's y is a plain rectangular clip
    clipRef.current?.setAttribute("height", String(len > 0 ? pt.y : 0));
    const lead = leadRef.current;
    if (lead) {
      lead.setAttribute("transform", `translate(${pt.x} ${pt.y})`);
      lead.style.opacity = len > 0 ? "1" : "0";
    }
    g.stops.forEach((st, i) => nodeEls.current[i]?.classList.toggle("on", target >= st.y - 6));
  }, []);

  useEffect(() => {
    measure();
    const main = svgRef.current!.parentElement!;
    const ro = new ResizeObserver(measure);
    ro.observe(main);
    window.addEventListener("resize", measure);
    document.fonts?.ready.then(measure);
    const late = setTimeout(measure, 1600);

    let queued = false;
    const onScroll = () => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; update(); }); } };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      ro.disconnect(); clearTimeout(late);
      window.removeEventListener("resize", measure); window.removeEventListener("scroll", onScroll);
    };
  }, [measure, update]);

  // sample the path once per geometry, so scrolling only does a lookup
  useLayoutEffect(() => {
    geoRef.current = geo;
    const base = baseRef.current;
    if (!geo || !base) return;
    const total = base.getTotalLength();
    const n = 480;
    const ys = new Float32Array(n + 1), lens = new Float32Array(n + 1);
    for (let i = 0; i <= n; i++) { const l = (total * i) / n; lens[i] = l; ys[i] = base.getPointAtLength(l).y; }
    samples.current = { ys, lens, total };
    update();
  }, [geo, update]);

  return (
    <svg ref={svgRef} className="timeline" width={geo?.w ?? 0} height={geo?.h ?? 0} aria-hidden>
      {geo && (
        <>
          <defs>
            <clipPath id="tl-reveal" clipPathUnits="userSpaceOnUse">
              <rect ref={clipRef} x={0} y={0} width={geo.w} height={0} />
            </clipPath>
          </defs>
          <path ref={baseRef} className="tl-base" d={geo.d} />
          <path className="tl-live" d={geo.d} clipPath="url(#tl-reveal)" />
          {geo.stops.map((s, i) => {
            const lp = labelPos[s.side];
            return (
              <g key={i} ref={el => { nodeEls.current[i] = el; }} className={`tl-node${s.label ? "" : " tl-start"}`}
                transform={`translate(${s.x} ${s.y})`}>
                <circle className="tl-halo" r={s.label ? 19 : 12} />
                <circle className="tl-dot" r={s.label ? 8 : 5} />
                {s.label && (
                  <text className="tl-label" x={lp.x} y={lp.y} textAnchor={lp.a}>
                    <tspan className="tl-n">{s.n}</tspan>{"  "}{s.label}
                  </text>
                )}
              </g>
            );
          })}
          <g ref={leadRef} className="tl-lead" style={{ opacity: 0 }}>
            <circle className="tl-lead-halo" r={13} />
            <circle className="tl-lead-core" r={5.5} />
          </g>
        </>
      )}
    </svg>
  );
}
