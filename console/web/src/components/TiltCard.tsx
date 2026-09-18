import { useCallback, useRef, useState } from "react";
import type { CSSProperties, MouseEvent, ReactNode } from "react";

// Ported from Front-End/src/components/3d/TiltCard.tsx -- pure CSS 3D
// transforms (perspective + rotateX/rotateY), no library.
export default function TiltCard({
  children, className = "", style = {}, maxTilt = 8, perspective = 1000,
  glare = true, glareColor = "rgba(255, 255, 255, 0.12)", scale = 1.02,
}: {
  children: ReactNode; className?: string; style?: CSSProperties; maxTilt?: number;
  perspective?: number; glare?: boolean; glareColor?: string; scale?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState("");
  const [glarePos, setGlarePos] = useState({ x: 50, y: 50, opacity: 0 });
  const [hovered, setHovered] = useState(false);

  const onMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width, py = (e.clientY - rect.top) / rect.height;
    const tiltX = (py - 0.5) * -maxTilt * 2, tiltY = (px - 0.5) * maxTilt * 2;
    setTransform(`perspective(${perspective}px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg) scale3d(${scale},${scale},${scale})`);
    if (glare) setGlarePos({ x: Math.round(px * 100), y: Math.round(py * 100), opacity: 1 });
  }, [maxTilt, perspective, scale, glare]);

  const onLeave = useCallback(() => {
    setHovered(false);
    setTransform(`perspective(${perspective}px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)`);
    setGlarePos(p => ({ ...p, opacity: 0 }));
  }, [perspective]);

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={onLeave}
      className={`tilt-card ${className}`}
      style={{
        transform, transformStyle: "preserve-3d",
        transition: hovered ? "transform 0.08s ease-out" : "transform 0.5s cubic-bezier(0.2,0.8,0.2,1)",
        ...style,
      }}
    >
      {glare && (
        <div aria-hidden className="tilt-glare" style={{
          opacity: glarePos.opacity,
          background: `radial-gradient(circle at ${glarePos.x}% ${glarePos.y}%, ${glareColor} 0%, transparent 60%)`,
        }} />
      )}
      {children}
    </div>
  );
}
