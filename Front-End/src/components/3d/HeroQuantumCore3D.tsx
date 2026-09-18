import { useState, useCallback, useRef } from 'react'

export default function HeroQuantumCore3D() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [isHovered, setIsHovered] = useState(false)

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width - 0.5
    const y = (e.clientY - rect.top) / rect.height - 0.5
    setTilt({
      x: -y * 24, // tilt up/down
      y: x * 24,  // tilt left/right
    })
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false)
    setTilt({ x: 0, y: 0 })
  }, [])

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true)
  }, [])

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="relative w-80 h-80 sm:w-96 sm:h-96 flex items-center justify-center cursor-pointer select-none"
      style={{ perspective: 1200 }}
    >
      {/* 1. Deep Ambient Pulsing Glow */}
      <div
        aria-hidden
        className="absolute inset-0 rounded-full pointer-events-none transition-all duration-700"
        style={{
          background: 'radial-gradient(circle, rgba(224, 76, 30, 0.45) 0%, rgba(219, 161, 54, 0.2) 45%, transparent 70%)',
          filter: 'blur(36px)',
          transform: isHovered ? 'scale(1.2)' : 'scale(1)',
        }}
      />

      {/* 2. Main 3D Container tracking mouse */}
      <div
        className="relative w-72 h-72 sm:w-80 sm:h-80 flex items-center justify-center"
        style={{
          transformStyle: 'preserve-3d',
          transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
          transition: isHovered ? 'transform 0.08s ease-out' : 'transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1)',
        }}
      >
        {/* Ring A: Outer 3D Gyro Orbit (Clockwise) */}
        <div
          aria-hidden
          className="absolute inset-0 rounded-full border border-dashed border-[#dba136]/50 pointer-events-none"
          style={{
            animation: 'orbit3D 20s linear infinite',
            transformStyle: 'preserve-3d',
          }}
        >
          {/* Traveling energy photon */}
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#f59e0b] shadow-[0_0_12px_#f59e0b]"
          />
        </div>

        {/* Ring B: Counter-tilted 3D Orbit (Counter-clockwise) */}
        <div
          aria-hidden
          className="absolute inset-4 rounded-full border border-dotted border-[#e04c1e]/60 pointer-events-none"
          style={{
            animation: 'orbit3DReverse 14s linear infinite',
            transformStyle: 'preserve-3d',
          }}
        >
          {/* Traveling energy photon */}
          <div
            className="absolute bottom-0 right-1/4 w-2.5 h-2.5 rounded-full bg-[#e04c1e] shadow-[0_0_10px_#e04c1e]"
          />
        </div>

        {/* Ring C: Equator Ring */}
        <div
          aria-hidden
          className="absolute inset-10 rounded-full border border-[#f59e0b]/25 pointer-events-none animate-pulse"
        />

        {/* Central 3D Quantum Energy Shield Core */}
        <div
          className="relative z-10 w-52 h-52 sm:w-60 sm:h-60 rounded-full flex items-center justify-center p-3 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8)]"
          style={{
            background: 'conic-gradient(from 180deg at 50% 50%, #200b1a 0deg, #e04c1e 120deg, #dba136 240deg, #200b1a 360deg)',
            transform: 'translateZ(30px)',
            transformStyle: 'preserve-3d',
          }}
        >
          {/* Inner Depth Disc */}
          <div
            className="w-full h-full rounded-full flex flex-col items-center justify-center text-center p-4 border border-white/15 relative overflow-hidden"
            style={{
              backgroundColor: '#170713',
              boxShadow: 'inset 0 4px 20px rgba(0,0,0,0.8), 0 10px 30px rgba(224,76,30,0.2)',
              transform: 'translateZ(20px)',
            }}
          >
            {/* Subtle rotating grid background */}
            <div
              className="absolute inset-0 opacity-20 pointer-events-none"
              style={{
                backgroundImage: 'radial-gradient(#dba136 1px, transparent 1px)',
                backgroundSize: '16px 16px',
              }}
            />

            <span className="text-3xl sm:text-4xl mb-1 animate-bounce" style={{ animationDuration: '2.5s' }}>
              ⚡
            </span>
            <span className="font-mono text-[11px] sm:text-xs font-bold text-[#f59e0b] tracking-widest uppercase">
              EnergyGate Core
            </span>
            <div className="font-mono text-2xl sm:text-3xl font-extrabold text-white mt-0.5 tracking-tight">
              310 <span className="text-xs text-[#a08595] font-normal">J/hr</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#10b981] mt-2 px-2.5 py-0.5 rounded-full bg-[#10b981]/15 border border-[#10b981]/30">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" />
              <span>ML-KEM-1024 ACTIVE</span>
            </div>
          </div>
        </div>

        {/* 3D Popping Floating Badge: Power Anomaly */}
        <div
          className="absolute -top-2 -right-4 px-3.5 py-1.5 rounded-full text-xs font-mono font-bold shadow-xl border border-[#e04c1e]/40 flex items-center gap-1.5 transition-transform"
          style={{
            backgroundColor: '#300f26',
            color: '#ff8c5a',
            transform: 'translateZ(55px)',
          }}
        >
          <span className="text-[10px]">🔥</span>
          <span>512mW Defended</span>
        </div>

        {/* 3D Popping Floating Badge: Hardware Verified */}
        <div
          className="absolute -bottom-4 px-4 py-1.5 rounded-full text-xs font-mono font-bold shadow-2xl flex items-center gap-2 border border-white/20 transition-transform"
          style={{
            backgroundColor: '#e04c1e',
            color: '#ffffff',
            transform: 'translateZ(65px)',
          }}
        >
          <span className="w-2 h-2 rounded-full bg-white animate-ping" />
          <span>Real ESP32 + INA219</span>
        </div>
      </div>
    </div>
  )
}
