import { Link } from "react-router-dom";
import CyberMeshBackground from "../components/CyberMeshBackground";
import QuantumCore from "../components/QuantumCore";
import TiltCard from "../components/TiltCard";

// Ported from Front-End/src/pages/LandingPage.tsx (design), with three
// corrections made while porting -- see console/CLAUDE.md and the project's
// own "honest numbers only" rule (root CLAUDE.md #4), which this page should
// hold itself to exactly like the dashboard does:
//   1. "ML-DSA-87" -> "ML-DSA-44": this project benchmarks ML-DSA-44 only;
//      -87 is a real NIST parameter set, just not one this repo implements.
//   2. The original's "8 supported hardware targets" (ESP32-S3, RISC-V,
//      ARM Cortex, FreeRTOS, Zephyr...) don't exist in this project -- the
//      real stack is one ESP32-WROOM-32 board on the Arduino framework.
//      Replaced with the actual cryptographic/hardware stack this repo uses.
//   3. Dropped the "field deployment" customer testimonials section
//      entirely -- "Substation Grid Sentinel, 4,200 sensors" etc. never
//      existed. A hackathon project quoting fabricated customers is a
//      credibility risk this page doesn't need to take.
// The benchmark tiers below use the same placeholder J/hr figures the
// original frontend-kit fixtures shipped with (contracts/CHANGELOG.md,
// console/frontend-kit/fixtures/experiment.json) -- explicitly captioned
// as illustrative rather than presented as a settled measurement, matching
// how the live Experiment tab shows "pending" for the same rows.

const FEATURES = [
  {
    title: "Hardware-Measured Budgets",
    body: "Real-time power telemetry using an INA219 current sensor on an ESP32 field node. Every cryptographic operation is measured in millijoules without perturbing the node under test.",
    icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  },
  {
    title: "EnergyGate Admission Control",
    body: "A tiny, cost-sensitive decision tree runs in front of the expensive handshake. It reads signal variance and the token-bucket balance to choose SPEND, CHALLENGE, or DROP.",
    icon: "M4 4h16v16H4z M9 12l2 2 4-4",
  },
  {
    title: "Defeating Drain Attacks",
    body: "Prevents asymmetric battery exhaustion from radio replay floods and slow-drip requests designed to force repeated, costly post-quantum handshakes.",
    icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  },
];

const TIERS = [
  { tag: "BASELINE — NO DEFENCE", label: "Attack, no defence", jhr: "1,843", days: "1.2", connect: "61%", delay: "+2,400 ms", note: "Vulnerable to radio replay flood", bad: true },
  { tag: "STATIC CONTROL", label: "Attack + rate limit", jhr: "470", days: "26.0", connect: "92%", delay: "+300 ms", note: "Drops bursts blindly, misses slow-drip" },
  { tag: "STATELESS PROBE", label: "Attack + cookie only", jhr: "388", days: "32.0", connect: "97%", delay: "+120 ms", note: "8-byte stateless verification" },
  { tag: "RECOMMENDED", label: "Attack + EnergyGate", jhr: "310", days: "~40.0", connect: "99.8%*", delay: "< 5 ms*", note: "Signal variance + joule token bucket", highlight: true },
];

const STACK = [
  { name: "ML-KEM", sub: "512 / 768 / 1024" },
  { name: "ML-DSA-44", sub: "Signatures" },
  { name: "AES-256-GCM", sub: "Payload encryption" },
  { name: "ESP-NOW", sub: "Mesh transport" },
  { name: "ESP32-WROOM-32", sub: "Arduino framework" },
  { name: "INA219", sub: "Current sensor" },
];

const STEPS = [
  { n: "01", tag: "FREE", title: "Stranger says hello", body: "The incoming radio frame costs the node nothing to receive. The node registers the attempt and forwards free signal metadata to EnergyGate." },
  { n: "02", tag: "EVALUATE", title: "EnergyGate model", body: "A decision tree checks RSSI variance, completion history and the remaining joule budget. Inference runs in microseconds directly on the ESP32." },
  { n: "03", tag: "DECIDE", title: "Tactical action", body: "The field node drops the packet, issues an 8-byte cookie challenge, or spends its battery on the full post-quantum handshake." },
];

function Logo() {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden>
        <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
          <polygon points="11,1 21,6 21,16 11,21 1,16 1,6" stroke="#fff" strokeWidth="2" fill="none" />
          <circle cx="11" cy="11" r="3" fill="#fff" />
        </svg>
      </span>
      <span>Sentinel<b>Mesh</b></span>
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="landing">
      <div className="lp-hero">
        <CyberMeshBackground />
        <div className="lp-glow" aria-hidden />
        <nav className="lp-nav">
          <Logo />
          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#benchmarks">Benchmarks</a>
            <a href="#how">How It Works</a>
            <Link to="/dashboard" className="pill pill-solid">
              <span className="dot" /> Live Dashboard &rarr;
            </Link>
          </div>
        </nav>

        <section className="lp-hero-grid">
          <div className="lp-hero-copy">
            <span className="pill pill-outline">
              <span className="dot amber" /> Post-Quantum &middot; IoT Security &middot; Telemetry
            </span>
            <h1>Protect the Battery.<br /><span className="amber">Secure Post-Quantum IoT.</span></h1>
            <p>
              Post-quantum cryptography turns the battery into the attack surface. SentinelMesh measures the
              joule cost of every crypto operation on real hardware and uses a tiny ML gatekeeper to decide if
              a stranger is worth the energy — before spending it.
            </p>
            <div className="lp-cta-row">
              <Link to="/dashboard" className="pill pill-solid lg">View Live Dashboard &rarr;</Link>
              <a href="#benchmarks" className="pill pill-ghost lg">Read Benchmarks ↗</a>
            </div>
          </div>
          <div className="lp-hero-visual">
            <QuantumCore />
          </div>
        </section>
      </div>

      <section id="features" className="lp-section white">
        <div className="lp-wrap">
          <div className="lp-grid-3">
            {FEATURES.map(f => (
              <TiltCard key={f.title} maxTilt={8}>
                <div className="feature-card">
                  <div className="feature-icon">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                      <path d={f.icon} strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </div>
              </TiltCard>
            ))}
          </div>
        </div>
      </section>

      <div className="lp-strip" />

      <section id="benchmarks" className="lp-section tint">
        <div className="lp-wrap center">
          <h2>Defence Benchmarks</h2>
          <p className="lp-lede">Comparing sensor autonomy and battery drain across defensive configurations.</p>
          <div className="lp-grid-4">
            {TIERS.map(t => (
              <TiltCard key={t.label} maxTilt={t.highlight ? 10 : 7} glareColor={t.highlight ? "rgba(224, 76, 30, 0.2)" : undefined}>
                <div className={`tier-card${t.highlight ? " highlight" : ""}`}>
                  <div className={`tier-tag${t.highlight ? " tier-tag-hi" : ""}`}>{t.tag}</div>
                  <div className="tier-body">
                    <span className="tier-sub">{t.label}</span>
                    <p className="tier-num">{t.jhr}<small>&nbsp;J/hr</small></p>
                    <div className={`tier-days${t.bad ? " bad" : t.highlight ? " good" : ""}`}>Projected life: {t.days} days</div>
                    <ul>
                      <li><b>{t.connect}</b> legit connect rate</li>
                      <li><b>{t.delay}</b> extra handshake delay</li>
                      <li>{t.note}</li>
                    </ul>
                  </div>
                </div>
              </TiltCard>
            ))}
          </div>
          <p className="lp-fineprint">
            * EnergyGate figures are illustrative targets from the original fixture data, not yet a real hardware
            measurement — the live <Link to="/dashboard">Experiment</Link> tab shows this row as pending until
            the energy rig produces it. Don't quote these numbers as results.
          </p>
        </div>
      </section>

      <section className="lp-section white">
        <div className="lp-wrap lp-cta-split">
          <h3>Deploy post-quantum energy defences across your sensor mesh.</h3>
          <Link to="/dashboard" className="pill pill-solid">Launch Live Console &rarr;</Link>
        </div>
      </section>

      <section id="how" className="lp-section white">
        <div className="lp-wrap lp-how">
          <div className="how-visual">
            <TiltCard maxTilt={6}>
              <div className="pipeline-card">
                <div className="pipeline-head">
                  <span className="pipeline-icon">&#9635;</span>
                  <div>
                    <h4>Decision Pipeline Architecture</h4>
                    <span>Microsecond on-node inference</span>
                  </div>
                </div>
                <div className="pipeline-row"><span className="badge badge-drop">DROP</span> Connection rejected, zero joules spent</div>
                <div className="pipeline-row"><span className="badge badge-challenge">CHALLENGE</span> 8-byte cookie probe, near-zero cost</div>
                <div className="pipeline-row"><span className="badge badge-spend">SPEND</span> Full ML-KEM / ML-DSA handshake</div>
              </div>
            </TiltCard>
          </div>
          <div className="how-copy">
            <span className="eyebrow">Decision Pipeline</span>
            <h2>How EnergyGate Works</h2>
            <p className="lp-lede">A layered defence for post-quantum edge and SCADA-style networks.</p>
            <div className="steps">
              {STEPS.map(s => (
                <div key={s.n} className="step">
                  <div className="step-n">{s.n}</div>
                  <div>
                    <div className="step-head"><h3>{s.title}</h3><span className="badge badge-mini">{s.tag}</span></div>
                    <p>{s.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section tint">
        <div className="lp-wrap center">
          <p className="eyebrow">SUPPORTED CRYPTOGRAPHIC &amp; HARDWARE STACK</p>
          <div className="lp-grid-6">
            {STACK.map(s => (
              <div key={s.name} className="stack-chip">
                <span className="stack-name">{s.name}</span>
                <span className="stack-sub">{s.sub}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <CyberMeshBackground dim />
        <div className="lp-wrap center">
          <Link to="/dashboard" className="pill pill-solid lg">
            <span className="dot" /> Launch Live Security Console &rarr;
          </Link>
          <div className="lp-foot-row">
            <span><b>SentinelMesh</b> — Code Cortex 3.0 Security Track</span>
            <div className="lp-foot-links">
              <Link to="/dashboard">Live Console Dashboard</Link>
              <a href="#features">Features</a>
              <a href="#benchmarks">Benchmarks</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
