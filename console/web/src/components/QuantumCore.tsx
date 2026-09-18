import { useCallback, useRef, useState } from "react";
import type { MouseEvent } from "react";

// Ported from Front-End/src/components/3d/HeroQuantumCore3D.tsx -- CSS 3D
// transforms (perspective + rotateX/rotateY/translateZ) tracking the mouse,
// no library. Numbers (310 J/hr, ML-KEM-1024, 512mW) are the same
// illustrative figures used throughout the landing page copy, not a live
// reading -- this is decorative, the real numbers live on /dashboard.
export default function QuantumCore() {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState(false);

  const onMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({ x: -y * 24, y: x * 24 });
  }, []);
  const onLeave = useCallback(() => { setHovered(false); setTilt({ x: 0, y: 0 }); }, []);

  return (
    <div ref={ref} onMouseMove={onMove} onMouseEnter={() => setHovered(true)} onMouseLeave={onLeave} className="qcore-wrap">
      <div aria-hidden className={`qcore-glow${hovered ? " hot" : ""}`} />
      <div className="qcore-3d" style={{
        transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: hovered ? "transform 0.08s ease-out" : "transform 0.6s cubic-bezier(0.2,0.8,0.2,1)",
      }}>
        <div aria-hidden className="qcore-ring qcore-ring-a"><span className="qcore-photon qcore-photon-a" /></div>
        <div aria-hidden className="qcore-ring qcore-ring-b"><span className="qcore-photon qcore-photon-b" /></div>
        <div aria-hidden className="qcore-ring qcore-ring-c" />
        <div className="qcore-face">
          <div className="qcore-inner">
            <span aria-hidden className="qcore-grid" />
            <span className="qcore-bolt">&#9889;</span>
            <span className="qcore-label">ENERGYGATE CORE</span>
            <div className="qcore-value">310 <small>J/hr</small></div>
            <div className="qcore-active"><span className="qcore-ping" />ML-KEM-1024 ACTIVE</div>
          </div>
        </div>
        <div className="qcore-badge qcore-badge-1"><span>&#128293;</span>512mW Defended</div>
        <div className="qcore-badge qcore-badge-2"><span className="qcore-ping light" />Real ESP32 + INA219</div>
      </div>
    </div>
  );
}
