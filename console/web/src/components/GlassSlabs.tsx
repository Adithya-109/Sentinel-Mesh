import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";

// Translucent glass slabs that drift behind the page and shift with scroll.
// x/y are the slab's position in vw/vh, s its width in vw, r its tilt, k how far
// it travels over a full scroll (in viewport heights), dur/delay its idle float.
type Slab = { x: number; y: number; s: number; r: number; k: number; dur: number; delay: number; tone: "lilac" | "slate" | "mist"; ar?: number; blur?: number };

const PRESETS: Record<"hero" | "quiet", Slab[]> = {
  // Positions are where each slab sits at the top of the page; scrolling then
  // carries it k viewport-heights over the whole page. The middle stays clear.
  hero: [
    { x: 62, y: -19, s: 27, r: 268, k: 0.6, dur: 21, delay: -4, tone: "slate" },
    { x: -17, y: 46, s: 40, r: 10, k: -0.5, dur: 26, delay: -11, tone: "lilac", ar: 1.33 },
    { x: 73, y: 58, s: 26, r: -14, k: 0.8, dur: 19, delay: -7, tone: "slate", blur: 3 },
    { x: -7, y: -17, s: 25, r: -18, k: 0.35, dur: 23, delay: -2, tone: "mist" },
    { x: 89, y: 22, s: 18, r: 24, k: -0.4, dur: 17, delay: -9, tone: "lilac" },
    { x: 13, y: 90, s: 28, r: 8, k: 0.5, dur: 28, delay: -15, tone: "lilac", ar: 1.25 },
    { x: 56, y: 96, s: 22, r: -30, k: -0.3, dur: 22, delay: -6, tone: "mist", blur: 3 },
  ],
  // The console keeps its slabs at the far edges so they never sit under text.
  quiet: [
    { x: 82, y: -26, s: 22, r: 262, k: 0.5, dur: 24, delay: -5, tone: "slate" },
    { x: -26, y: 46, s: 24, r: 12, k: -0.4, dur: 27, delay: -12, tone: "lilac", ar: 1.3 },
    { x: 93, y: 58, s: 17, r: -16, k: 0.6, dur: 20, delay: -8, tone: "mist", blur: 2 },
    { x: 4, y: 97, s: 18, r: 6, k: 0.3, dur: 25, delay: -14, tone: "lilac" },
  ],
};

export default function GlassSlabs({ variant = "hero" }: { variant?: "hero" | "quiet" }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let queued = false;
    const update = () => {
      queued = false;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      el.style.setProperty("--p", String(max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0));
    };
    const onScroll = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); };
  }, []);

  return (
    <div className="slabs" ref={ref} aria-hidden>
      {PRESETS[variant].map((s, i) => (
        <div key={i} className={`slab ${s.tone}`}
          style={{
            "--x": `${s.x}vw`, "--y": `${s.y}vh`, "--s": s.s, "--r": `${s.r}deg`, "--k": s.k,
            "--dur": `${s.dur}s`, "--delay": `${s.delay}s`, "--ar": s.ar ?? 1, "--blur": `${s.blur ?? 0}px`,
          } as CSSProperties}>
          <div className="slab-inner"><div className="slab-face" /></div>
        </div>
      ))}
    </div>
  );
}
