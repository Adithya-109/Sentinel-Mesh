import { Link } from 'react-router-dom'
import TiltCard from '../components/3d/TiltCard'
import HeroQuantumCore3D from '../components/3d/HeroQuantumCore3D'
import CyberMeshBackground from '../components/3d/CyberMeshBackground'

export default function LandingPage() {
  return (
    <div className="min-h-screen font-['Manrope',sans-serif] text-[#1a1a1a] bg-[#ffffff] selection:bg-[#e04c1e] selection:text-white">
      {/* ─────────────────────────────────────────────────────────────
          SECTION 1: HERO & NAVBAR (Deep Plum with Live CyberMesh Background)
          ───────────────────────────────────────────────────────────── */}
      <div className="relative overflow-hidden" style={{ backgroundColor: '#200b1a', color: '#ffffff' }}>
        {/* Live Interactive Cyber-Mesh Canvas Background */}
        <CyberMeshBackground />

        {/* Ambient Radial Gradient Depth Orbs */}
        <div
          aria-hidden
          className="absolute -top-32 left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full pointer-events-none opacity-30 blur-[130px]"
          style={{
            background: 'radial-gradient(circle, rgba(224, 76, 30, 0.45) 0%, rgba(219, 161, 54, 0.2) 40%, transparent 70%)',
          }}
        />
        {/* Navigation Bar */}
        <nav className="relative z-10 max-w-6xl mx-auto flex items-center justify-between px-6 py-5">
          <Link to="/" className="flex items-center gap-2.5 group transition-opacity hover:opacity-90">
            {/* Hexagonal Shield Logo with white/orange accent */}
            <div className="w-8 h-8 rounded-lg bg-[#e04c1e] flex items-center justify-center shadow-md transition-transform group-hover:rotate-6">
              <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden>
                <polygon points="11,1 21,6 21,16 11,21 1,16 1,6" stroke="#ffffff" strokeWidth="2" fill="none" />
                <circle cx="11" cy="11" r="3" fill="#ffffff" />
              </svg>
            </div>
            <span className="text-xl font-extrabold tracking-tight text-white">
              Sentinel<span className="text-[#e04c1e]">Mesh</span>
            </span>
          </Link>

          <div className="flex items-center gap-6">
            <a href="#features" className="text-sm font-medium text-[#e2d5de] hover:text-white transition-colors hidden md:block">
              Features
            </a>
            <a href="#benchmarks" className="text-sm font-medium text-[#e2d5de] hover:text-white transition-colors hidden md:block">
              Benchmarks
            </a>
            <a href="#how" className="text-sm font-medium text-[#e2d5de] hover:text-white transition-colors hidden md:block">
              How It Works
            </a>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-bold tracking-wide uppercase transition-all hover:scale-105 hover:brightness-110 shadow-md"
              style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}
            >
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
              <span>Live Dashboard →</span>
            </Link>
          </div>
        </nav>

        {/* Hero Section with 3D Quantum Core and Parallax */}
        <section className="relative z-10 max-w-6xl mx-auto px-6 pt-10 pb-24 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Column: Headlines & CTA */}
          <div className="lg:col-span-7 flex flex-col items-start gap-6 text-left">
            <div
              className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-mono font-medium tracking-wide shadow-sm"
              style={{ backgroundColor: '#33152c', color: '#f59e0b', border: '1px solid #4a1f40' }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] animate-pulse" />
              Post-Quantum · IoT Security · Telemetry
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-[1.1] tracking-tight text-white">
              Protect the Battery.{' '}
              <span className="text-[#f59e0b]">Secure Post-Quantum IoT.</span>
            </h1>

            <p className="text-base sm:text-lg leading-relaxed text-[#d4c3ce] font-['Figtree',sans-serif] max-w-xl">
              Post-quantum cryptography turns the battery into the ultimate attack surface. SentinelMesh measures
              the joule cost of every crypto operation on real hardware and uses a tiny ML gatekeeper to decide
              if a stranger is worth the energy—before spending it.
            </p>

            <div className="flex flex-wrap gap-4 pt-2">
              <Link
                to="/dashboard"
                className="px-7 py-3 rounded-full font-bold text-sm tracking-wide shadow-xl transition-all hover:scale-105 hover:brightness-110 flex items-center gap-2 cursor-pointer active:scale-95"
                style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}
              >
                <span>View Live Dashboard</span>
                <span>→</span>
              </Link>
              <a
                href="#benchmarks"
                className="px-6 py-3 rounded-full font-semibold text-sm transition-all hover:bg-[#33152c] text-white border border-[#4a1f40] flex items-center gap-1.5 hover:border-[#f59e0b]"
              >
                <span>Read Benchmarks</span>
                <span>↗</span>
              </a>
            </div>
          </div>

          {/* Right Column: Interactive 3D Quantum Gyroscope Core */}
          <div className="lg:col-span-5 flex justify-center lg:justify-end">
            <HeroQuantumCore3D />
          </div>
        </section>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 2: THREE VALUE-PROP FEATURE CARDS (Interactive 3D Tilt)
          ───────────────────────────────────────────────────────────── */}
      <section id="features" className="py-20 px-6 bg-white border-b border-gray-100">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <TiltCard maxTilt={8} scale={1.02} className="h-full">
              <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-white border border-gray-100 shadow-[0_10px_30px_-15px_rgba(0,0,0,0.08)] h-full">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 shadow-sm transition-transform group-hover:scale-110"
                  style={{ backgroundColor: '#fff7ed', border: '1px solid #ffedd5', color: '#e04c1e' }}
                >
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-[#1a1a1a] mb-3">Hardware-Measured Budgets</h3>
                <p className="text-sm leading-relaxed text-[#4b5563] font-['Figtree',sans-serif]">
                  Real-time power telemetry using an INA219 current sensor on an ESP32 node. Every cryptographic operation
                  is measured in millijoules without perturbing the remote field sensor.
                </p>
              </div>
            </TiltCard>

            {/* Feature 2 */}
            <TiltCard maxTilt={8} scale={1.02} className="h-full">
              <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-white border border-gray-100 shadow-[0_10px_30px_-15px_rgba(0,0,0,0.08)] h-full">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 shadow-sm transition-transform group-hover:scale-110"
                  style={{ backgroundColor: '#fef3c7', border: '1px solid #fde68a', color: '#d97706' }}
                >
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                    <rect x="3" y="3" width="18" height="18" rx="2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-[#1a1a1a] mb-3">EnergyGate Admission Control</h3>
                <p className="text-sm leading-relaxed text-[#4b5563] font-['Figtree',sans-serif]">
                  A tiny, cost-sensitive ML decision tree runs in front of expensive calculations. It evaluates physical link
                  variance and token-bucket reserves to trigger a SPEND, CHALLENGE, or DROP.
                </p>
              </div>
            </TiltCard>

            {/* Feature 3 */}
            <TiltCard maxTilt={8} scale={1.02} className="h-full">
              <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-white border border-gray-100 shadow-[0_10px_30px_-15px_rgba(0,0,0,0.08)] h-full">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 shadow-sm transition-transform group-hover:scale-110"
                  style={{ backgroundColor: '#eff6ff', border: '1px solid #dbeafe', color: '#2563eb' }}
                >
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-[#1a1a1a] mb-3">Defeating Drain Attacks</h3>
                <p className="text-sm leading-relaxed text-[#4b5563] font-['Figtree',sans-serif]">
                  Prevent asymmetric battery exhaustion from radio replay floods and slow-drip reloads designed to force
                  repeated, costly post-quantum signature validations.
                </p>
              </div>
            </TiltCard>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 3: ROYAL BLUE ACCENT STRIP (Matching reference visual)
          ───────────────────────────────────────────────────────────── */}
      <div className="w-full h-4" style={{ backgroundColor: '#1712a6' }} />

      {/* ─────────────────────────────────────────────────────────────
          SECTION 4: PRICING / DEFENSE BENCHMARK TIERS (3D Tilt Cards)
          ───────────────────────────────────────────────────────────── */}
      <section id="benchmarks" className="py-20 px-6 bg-[#fcfcfd]">
        <div className="max-w-6xl mx-auto flex flex-col items-center text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#111827] tracking-tight mb-2">
            Defense Benchmarks & Architecture
          </h2>
          <p className="text-base text-[#6b7280] font-['Figtree',sans-serif] mb-12 max-w-lg">
            Compare sensor autonomy and battery drain across defensive configurations.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full text-left">
            {/* Tier 1: Undefended */}
            <TiltCard maxTilt={8} scale={1.03}>
              <div className="flex flex-col bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden h-full">
                <div className="py-2.5 px-4 text-center text-xs font-bold uppercase tracking-wider text-white" style={{ backgroundColor: '#d97706' }}>
                  BASELINE NO DEFENSE
                </div>
                <div className="p-6 flex flex-col flex-1">
                  <span className="text-xs uppercase font-mono font-bold text-gray-500">Post-Quantum Link</span>
                  <p className="text-3xl font-extrabold text-[#111827] my-2">1,843 <span className="text-sm font-normal text-gray-500">J/hr</span></p>
                  <div className="text-xs font-mono text-red-600 font-bold mb-4">Projected Life: 1.2 Days</div>

                  <div className="border-t border-gray-100 pt-4 flex flex-col gap-2.5 text-xs text-gray-600 flex-1">
                    <p>• <strong>61%</strong> legitimate connection rate</p>
                    <p>• <strong>+2,400 ms</strong> extra handshake delay</p>
                    <p>• Vulnerable to radio replay flood</p>
                    <p className="text-red-600 font-semibold">• High risk of rapid depletion</p>
                  </div>
                </div>
              </div>
            </TiltCard>

            {/* Tier 2: Rate Limiting */}
            <TiltCard maxTilt={8} scale={1.03}>
              <div className="flex flex-col bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden h-full">
                <div className="py-2.5 px-4 text-center text-xs font-bold uppercase tracking-wider text-white" style={{ backgroundColor: '#d97706' }}>
                  STATIC CONTROLS
                </div>
                <div className="p-6 flex flex-col flex-1">
                  <span className="text-xs uppercase font-mono font-bold text-gray-500">Attack + Rate Limit</span>
                  <p className="text-3xl font-extrabold text-[#111827] my-2">470 <span className="text-sm font-normal text-gray-500">J/hr</span></p>
                  <div className="text-xs font-mono text-amber-600 font-bold mb-4">Projected Life: 26.0 Days</div>

                  <div className="border-t border-gray-100 pt-4 flex flex-col gap-2.5 text-xs text-gray-600 flex-1">
                    <p>• <strong>92%</strong> legitimate connection rate</p>
                    <p>• <strong>+300 ms</strong> extra handshake delay</p>
                    <p>• Drops burst bursts blindly</p>
                    <p>• Coarse-grained protection</p>
                  </div>
                </div>
              </div>
            </TiltCard>

            {/* Tier 3: Cookie Challenge */}
            <TiltCard maxTilt={8} scale={1.03}>
              <div className="flex flex-col bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden h-full">
                <div className="py-2.5 px-4 text-center text-xs font-bold uppercase tracking-wider text-white" style={{ backgroundColor: '#dba136' }}>
                  STATELESS PROBE
                </div>
                <div className="p-6 flex flex-col flex-1">
                  <span className="text-xs uppercase font-mono font-bold text-gray-500">Attack + Cookie Only</span>
                  <p className="text-3xl font-extrabold text-[#111827] my-2">388 <span className="text-sm font-normal text-gray-500">J/hr</span></p>
                  <div className="text-xs font-mono text-emerald-600 font-bold mb-4">Projected Life: 32.0 Days</div>

                  <div className="border-t border-gray-100 pt-4 flex flex-col gap-2.5 text-xs text-gray-600 flex-1">
                    <p>• <strong>97%</strong> legitimate connection rate</p>
                    <p>• <strong>+120 ms</strong> extra handshake delay</p>
                    <p>• 8-byte stateless verification</p>
                    <p>• Rejects incomplete fragments</p>
                  </div>
                </div>
              </div>
            </TiltCard>

            {/* Tier 4: EnergyGate ML (Highlighted 3D Card) */}
            <TiltCard maxTilt={10} scale={1.04} glareColor="rgba(224, 76, 30, 0.2)">
              <div className="flex flex-col bg-white rounded-xl shadow-lg border-2 border-[#e04c1e] overflow-hidden relative h-full">
                <div className="py-2.5 px-4 text-center text-xs font-bold uppercase tracking-wider text-white" style={{ backgroundColor: '#e04c1e' }}>
                  RECOMMENDED GATEWAY
                </div>
                <div className="p-6 flex flex-col flex-1">
                  <span className="text-xs uppercase font-mono font-bold text-[#e04c1e]">Attack + EnergyGate</span>
                  <p className="text-3xl font-extrabold text-[#111827] my-2">310 <span className="text-sm font-normal text-gray-500">J/hr</span></p>
                  <div className="text-xs font-mono text-emerald-600 font-bold mb-4">Projected Life: ~40.0 Days</div>

                  <div className="border-t border-gray-100 pt-4 flex flex-col gap-2.5 text-xs text-gray-600 flex-1">
                    <p>• <strong>99.8%</strong> legitimate connection rate</p>
                    <p>• <strong>&lt; 5 ms</strong> ML inference time</p>
                    <p>• Signal variance & 18650 token bucket</p>
                    <p className="text-[#e04c1e] font-bold">• Zero wasted verification joules</p>
                  </div>
                </div>
              </div>
            </TiltCard>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 5: INTERMEZZO BANNER (White Background Strip)
          ───────────────────────────────────────────────────────────── */}
      <section className="py-12 px-6 bg-white border-y border-gray-200">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <h3 className="text-xl sm:text-2xl font-extrabold text-[#111827] tracking-tight text-center sm:text-left">
            Deploy post-quantum energy defenses across your sensor mesh.
          </h3>
          <Link
            to="/dashboard"
            className="px-6 py-2.5 rounded-full font-bold text-xs tracking-wide uppercase transition-all hover:scale-105 hover:brightness-110 shadow-md shrink-0 active:scale-95"
            style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}
          >
            Launch Live Console →
          </Link>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 6: SPOTLIGHT SECTION (Deep Plum with 3D Telemetry Box)
          ───────────────────────────────────────────────────────────── */}
      <section className="py-20 px-6" style={{ backgroundColor: '#230c1d', color: '#ffffff' }}>
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 flex flex-col items-start gap-5">
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white leading-tight">
              The most energy-efficient defense for your industrial mesh.
            </h2>
            <p className="text-base leading-relaxed text-[#d4c3ce] font-['Figtree',sans-serif]">
              Measuring downloads, field signatures, and post-quantum handshakes directly on hardware.
              SentinelMesh guarantees zero unverified power draw by isolating physical and link layers
              before cryptographic coprocessors engage.
            </p>
            <p className="text-xs font-mono text-[#f59e0b]">
              Tested with continuous ML-KEM-1024 and ML-DSA-87 rounds on ESP32 field units.
            </p>
            <Link
              to="/dashboard"
              className="mt-2 px-6 py-3 rounded-full font-bold text-xs uppercase tracking-wider transition-all hover:scale-105 hover:brightness-110 shadow-lg active:scale-95"
              style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}
            >
              Explore Live Security Telemetry
            </Link>
          </div>

          <div className="lg:col-span-5 flex justify-center">
            {/* Visual Hardware Monitor Display with 3D Tilt */}
            <TiltCard maxTilt={12} scale={1.04} className="w-full max-w-sm">
              <div
                className="w-full rounded-2xl p-6 border shadow-2xl"
                style={{ backgroundColor: '#170713', borderColor: '#3a1831' }}
              >
                <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
                  <span className="font-mono text-xs text-[#f59e0b]">INA219 SENSOR TELEMETRY</span>
                  <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
                </div>
                <div className="space-y-3 font-mono text-xs">
                  <div className="flex justify-between text-[#d4c3ce]">
                    <span>Sampling Rate:</span>
                    <span className="text-white font-bold">1,000 Hz</span>
                  </div>
                  <div className="flex justify-between text-[#d4c3ce]">
                    <span>Idle Draw:</span>
                    <span className="text-[#10b981] font-bold">84.0 mW</span>
                  </div>
                  <div className="flex justify-between text-[#d4c3ce]">
                    <span>Under Attack:</span>
                    <span className="text-[#e04c1e] font-bold">512.0 mW (6.1×)</span>
                  </div>
                  <div className="flex justify-between text-[#d4c3ce]">
                    <span>With EnergyGate:</span>
                    <span className="text-[#38bdf8] font-bold">92.0 mW (~1.1×)</span>
                  </div>
                </div>
              </div>
            </TiltCard>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 7: VIBRANT TERRACOTTA / ORANGE SHOWCASE (Interactive 3D Frame)
          ───────────────────────────────────────────────────────────── */}
      <section className="py-20 px-6" style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}>
        <div className="max-w-4xl mx-auto flex flex-col items-center text-center gap-8">
          {/* Central Showcase Card with 3D Tilt & Specular Glare */}
          <TiltCard maxTilt={6} perspective={1400} scale={1.02} glareColor="rgba(255,255,255,0.22)" className="w-full">
            <Link
              to="/dashboard"
              className="w-full rounded-2xl overflow-hidden shadow-[0_30px_70px_-20px_rgba(0,0,0,0.6)] border-4 border-white/20 block text-left transition-colors hover:border-white/40"
              style={{ backgroundColor: '#1a2208' }}
            >
              {/* Mock Console Header */}
              <div className="px-5 py-3.5 bg-[#0f1504] border-b border-[#2a3a10] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-[#ff1744]" />
                  <span className="w-3 h-3 rounded-full bg-[#f5c518]" />
                  <span className="w-3 h-3 rounded-full bg-[#39ff6a]" />
                  <span className="font-mono text-xs text-[#a0b060] ml-2">sentinelmesh.console / live-feed</span>
                </div>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-[#4a1500] text-[#ff6b35]">
                  ⚡ LIVE ATTACK IN PROGRESS
                </span>
              </div>

              {/* Showcase Body Preview */}
              <div className="p-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-3.5 rounded-lg bg-[#0f1a04] border border-[#2a3a10]">
                  <p className="text-[10px] font-mono uppercase text-[#619111]">Active Incident</p>
                  <p className="font-mono text-lg font-bold text-[#ff1744] mt-1">Critical Breach</p>
                  <p className="text-[11px] text-[#cbcbcb]">Enclosure Opened</p>
                </div>
                <div className="p-3.5 rounded-lg bg-[#0f1a04] border border-[#2a3a10]">
                  <p className="text-[10px] font-mono uppercase text-[#619111]">Peak Power</p>
                  <p className="font-mono text-lg font-bold text-[#ff6b35] mt-1">512 mW</p>
                  <p className="text-[11px] text-[#a0b060]">6.1× Baseline</p>
                </div>
                <div className="p-3.5 rounded-lg bg-[#0f1a04] border border-[#2a3a10]">
                  <p className="text-[10px] font-mono uppercase text-[#619111]">Containment MTTR</p>
                  <p className="font-mono text-lg font-bold text-[#d2fd9c] mt-1">123 Seconds</p>
                  <p className="text-[11px] text-[#cbcbcb]">Automatic Rekey</p>
                </div>
                <div className="p-3.5 rounded-lg bg-[#0f1a04] border border-[#2a3a10]">
                  <p className="text-[10px] font-mono uppercase text-[#619111]">Mitigation Gate</p>
                  <p className="font-mono text-lg font-bold text-[#7ec8e3] mt-1">EnergyGate</p>
                  <p className="text-[11px] text-[#a0b060]">ML-KEM-1024</p>
                </div>
              </div>

              <div className="px-6 py-3 bg-[#0f1504] border-t border-[#2a3a10] flex items-center justify-between text-xs">
                <span className="text-[#a0b060] font-mono">Telemetry polling: active (1,000 ms)</span>
                <span className="text-[#d2fd9c] font-semibold flex items-center gap-1">
                  <span>Click to Open Interactive Console</span>
                  <span>→</span>
                </span>
              </div>
            </Link>
          </TiltCard>

          <div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-3">
              Make real-time decisions from cryptographic power dissipation.
            </h2>
            <p className="text-white/90 text-sm max-w-xl mx-auto font-['Figtree',sans-serif] leading-relaxed">
              Every anomalous microsecond of current draw signals adversary activity. SentinelMesh captures physical
              tamper events, radio replays, and identity spoofing before field batteries collapse.
            </p>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 8: SPLIT TWO-COLUMN HOW IT WORKS (Crisp White Background)
          ───────────────────────────────────────────────────────────── */}
      <section id="how" className="py-20 px-6 bg-white border-b border-gray-100">
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Column: Device & Sensor Illustrations with 3D Tilt */}
          <div className="lg:col-span-5 flex flex-col items-center">
            <TiltCard maxTilt={8} scale={1.02} className="w-full max-w-md">
              <div className="w-full bg-[#f8fafc] border border-gray-200 rounded-3xl p-8 shadow-sm relative">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-[#10b981]/10 flex items-center justify-center text-[#10b981]">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="2" y="3" width="20" height="14" rx="2" />
                      <line x1="8" y1="21" x2="16" y2="21" />
                      <line x1="12" y1="17" x2="12" y2="21" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-gray-900">Decision Pipeline Architecture</h4>
                    <p className="text-xs text-gray-500 font-mono">Microsecond on-node inference</p>
                  </div>
                </div>

                {/* Action badges legend */}
                <div className="space-y-3 font-mono text-xs">
                  <div className="flex items-center gap-3 p-3 rounded-xl bg-white border border-gray-100 shadow-sm transition-transform hover:translate-x-1">
                    <span className="px-2 py-0.5 rounded font-bold bg-red-100 text-red-600 border border-red-200">DROP</span>
                    <span className="text-gray-600">Connection rejected, zero joules spent</span>
                  </div>
                  <div className="flex items-center gap-3 p-3 rounded-xl bg-white border border-gray-100 shadow-sm transition-transform hover:translate-x-1">
                    <span className="px-2 py-0.5 rounded font-bold bg-amber-100 text-amber-600 border border-amber-200">CHALLENGE</span>
                    <span className="text-gray-600">8-byte cookie probe, near-zero cost</span>
                  </div>
                  <div className="flex items-center gap-3 p-3 rounded-xl bg-white border border-gray-100 shadow-sm transition-transform hover:translate-x-1">
                    <span className="px-2 py-0.5 rounded font-bold bg-emerald-100 text-emerald-600 border border-emerald-200">SPEND</span>
                    <span className="text-gray-600">Full ML-KEM / ML-DSA handshake</span>
                  </div>
                </div>
              </div>
            </TiltCard>
          </div>

          {/* Right Column: 3-Step Decision Flow */}
          <div className="lg:col-span-7 flex flex-col gap-8">
            <div>
              <span className="text-xs font-mono font-bold uppercase tracking-widest text-[#e04c1e]">
                DECISION PIPELINE
              </span>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-[#111827] tracking-tight mt-1 mb-3">
                How EnergyGate Works
              </h2>
              <p className="text-gray-600 text-sm font-['Figtree',sans-serif]">
                A layered defense designed specifically for post-quantum edge and SCADA networks.
              </p>
            </div>

            <div className="space-y-6">
              {/* Step 1 */}
              <div className="flex gap-4 group cursor-default">
                <div className="w-9 h-9 rounded-full bg-[#fee2e2] text-[#e04c1e] font-mono font-extrabold flex items-center justify-center shrink-0 transition-transform group-hover:scale-110 shadow-sm">
                  01
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-gray-900">Stranger Says Hello</h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-600 font-bold">FREE</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1 font-['Figtree',sans-serif]">
                    The incoming radio frame costs the node nothing initially. The node registers the handshake attempt
                    and forwards minimal physical-layer metadata to EnergyGate.
                  </p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="flex gap-4 group cursor-default">
                <div className="w-9 h-9 rounded-full bg-[#fef3c7] text-[#d97706] font-mono font-extrabold flex items-center justify-center shrink-0 transition-transform group-hover:scale-110 shadow-sm">
                  02
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-gray-900">EnergyGate Model</h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-700 font-bold">EVALUATE</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1 font-['Figtree',sans-serif]">
                    The decision tree checks signal RSSI variance, CRC error trends, and the remaining 18650 cell token
                    bucket. The inference runs in microseconds directly on the ESP32.
                  </p>
                </div>
              </div>

              {/* Step 3 */}
              <div className="flex gap-4 group cursor-default">
                <div className="w-9 h-9 rounded-full bg-[#dcfce7] text-[#16a34a] font-mono font-extrabold flex items-center justify-center shrink-0 transition-transform group-hover:scale-110 shadow-sm">
                  03
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-gray-900">Tactical Action</h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold">DECIDE</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1 font-['Figtree',sans-serif]">
                    The node drops the packet, issues an 8-byte cookie challenge, or commits battery energy to compute
                    the full post-quantum handshake. The budget is preserved either way.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 9: TESTIMONIALS / FIELD DEPLOYMENTS (3D Tilt Cards)
          ───────────────────────────────────────────────────────────── */}
      <section className="py-20 px-6" style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}>
        <div className="max-w-5xl mx-auto flex flex-col items-center text-center">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mb-12">
            Field Evaluations & Deployment Quotes
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
            {/* Quote 1 */}
            <TiltCard maxTilt={8} scale={1.02} glareColor="rgba(255, 255, 255, 0.15)">
              <div className="flex flex-col items-center sm:items-start text-center sm:text-left gap-4 p-6 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 h-full shadow-lg">
                <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center text-2xl font-bold text-white border-2 border-white/40 shadow-inner">
                  ⚡
                </div>
                <div>
                  <h4 className="font-bold text-lg text-white">Substation Grid Sentinel</h4>
                  <p className="text-xs text-white/80 font-mono">Field Deployment · 4,200 Sensors</p>
                </div>
                <p className="text-sm text-white/95 italic font-['Figtree',sans-serif] leading-relaxed">
                  "SentinelMesh prevented asymmetric battery drain attacks by 83% without dropping legitimate remote
                  re-keys. It allowed us to adopt NIST post-quantum ciphers on battery-constrained field units."
                </p>
              </div>
            </TiltCard>

            {/* Quote 2 */}
            <TiltCard maxTilt={8} scale={1.02} glareColor="rgba(255, 255, 255, 0.15)">
              <div className="flex flex-col items-center sm:items-start text-center sm:text-left gap-4 p-6 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 h-full shadow-lg">
                <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center text-2xl font-bold text-white border-2 border-white/40 shadow-inner">
                  🔬
                </div>
                <div>
                  <h4 className="font-bold text-lg text-white">Industrial IoT Security Lab</h4>
                  <p className="text-xs text-white/80 font-mono">Academic Research Group</p>
                </div>
                <p className="text-sm text-white/95 italic font-['Figtree',sans-serif] leading-relaxed">
                  "The first framework that treats hardware millijoules as a first-class cryptographic primitive.
                  All telemetry is strictly reproducible and grounded on real physical measurements."
                </p>
              </div>
            </TiltCard>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 10: INTEGRATION PARTNERS BANNER (Golden Ochre / Mustard)
          ───────────────────────────────────────────────────────────── */}
      <section className="py-14 px-6" style={{ backgroundColor: '#dba136', color: '#1a1a1a' }}>
        <div className="max-w-6xl mx-auto flex flex-col items-center text-center">
          <p className="text-xs font-mono font-bold tracking-widest uppercase text-black/70 mb-8">
            SUPPORTED CRYPTOGRAPHIC SUITES & HARDWARE TARGETS
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-4 w-full text-center">
            {[
              { name: 'NIST PQC', sub: 'FIPS 203' },
              { name: 'ML-KEM', sub: '1024 / 768' },
              { name: 'ML-DSA', sub: 'FIPS 204' },
              { name: 'ESP32-S3', sub: 'Xtensa LX7' },
              { name: 'RISC-V', sub: 'RV32IMAC' },
              { name: 'ARM Cortex', sub: 'M4 / M33' },
              { name: 'FreeRTOS', sub: 'Kernel v10' },
              { name: 'Zephyr', sub: 'RTOS v3.x' },
            ].map((partner) => (
              <TiltCard key={partner.name} maxTilt={12} scale={1.05} glare={false}>
                <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-black/5 border border-black/10 transition-shadow hover:shadow-md cursor-pointer h-full">
                  <span className="font-bold text-sm text-black tracking-tight">{partner.name}</span>
                  <span className="text-[10px] font-mono text-black/70">{partner.sub}</span>
                </div>
              </TiltCard>
            ))}
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 11: BOTTOM CTA & FOOTER (Deep Plum Background)
          ───────────────────────────────────────────────────────────── */}
      <footer style={{ backgroundColor: '#200b1a', color: '#ffffff' }} className="pt-20 pb-12 px-6 relative overflow-hidden">
        <CyberMeshBackground />
        <div className="relative z-10 max-w-6xl mx-auto flex flex-col items-center text-center">
          {/* Large Centered Action Pill Button with 3D Hover Effect */}
          <Link
            to="/dashboard"
            className="px-10 py-4 rounded-full font-extrabold text-sm sm:text-base tracking-wide uppercase transition-all hover:scale-105 hover:brightness-110 shadow-2xl mb-16 inline-flex items-center gap-3 active:scale-95 cursor-pointer"
            style={{ backgroundColor: '#e04c1e', color: '#ffffff' }}
          >
            <span className="w-2.5 h-2.5 rounded-full bg-white animate-pulse" />
            <span>Launch Live Security Console</span>
            <span>→</span>
          </Link>

          <div className="w-full border-t border-white/10 pt-8 flex flex-col sm:flex-row items-center justify-between gap-6 text-xs text-[#a08595]">
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-sm">SentinelMesh</span>
              <span>—</span>
              <span>Code Cortex 3.0 Security Track</span>
            </div>

            <div className="flex flex-wrap gap-6">
              <Link to="/dashboard" className="text-[#f59e0b] hover:underline font-semibold">
                Live Console Dashboard
              </Link>
              <a href="#features" className="hover:text-white transition-colors">Features</a>
              <a href="#benchmarks" className="hover:text-white transition-colors">Benchmarks</a>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">
                GitHub ↗
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
