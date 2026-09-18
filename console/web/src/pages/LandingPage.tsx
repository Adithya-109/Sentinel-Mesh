import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GlassSlabs from "../components/GlassSlabs";
import { useReveal, useSnap } from "../components/hooks";
import { Button, Wordmark } from "../components/parts";
import SiteFooter from "../components/SiteFooter";
import SiteHeader from "../components/SiteHeader";
import type { NavItem } from "../components/SiteHeader";
import TileField from "../components/TileField";
import "../landing.css";

// The design follows nodenza.com (see styles.css). The words are this project's
// own, and stick to what the repo can back up -- no invented numbers, customers
// or hardware claims (console/CLAUDE.md, root CLAUDE.md rule 4). The energy
// results are still pending real boards, so nothing here quotes one.

const go = (id: string) => () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

function Preloader() {
  const [done, setDone] = useState(false);
  const [gone, setGone] = useState(false);
  useEffect(() => {
    const a = setTimeout(() => setDone(true), 500);
    const b = setTimeout(() => setGone(true), 1700);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, []);
  if (gone) return null;
  return <div className={`preloader${done ? " done" : ""}`} aria-hidden><i /><i /><Wordmark /></div>;
}

function FlipCard({ title, back, to, cta }: { title: string; back: string; to: string; cta: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="choose-col">
      <div className={`flip${open ? " open" : ""}`}>
        <div className="flip-card" onClick={() => setOpen(o => !o)} role="button" tabIndex={0} aria-label={`${title}: flip card`}
          onKeyDown={e => { if (e.key === "Enter" || e.key === " ") setOpen(o => !o); }}>
          <div className="flip-face front"><h3 className="title">{title}</h3></div>
          <div className="flip-face back"><p>{back}</p></div>
        </div>
        <Button to={to} small>{cta}</Button>
      </div>
    </div>
  );
}

export default function LandingPage() {
  useReveal();
  useSnap();

  const nav: NavItem[] = [
    { id: "home", label: "Home", onClick: () => window.scrollTo({ top: 0, behavior: "smooth" }) },
    { id: "mission", label: "Mission", onClick: go("mission") },
    { id: "approach", label: "Approach", onClick: go("approach") },
    { id: "console", label: "Console", to: "/dashboard" },
  ];

  return (
    <div className="site landing">
      <Preloader />
      <GlassSlabs variant="hero" />
      <SiteHeader nav={nav} action={<Link to="/dashboard" className="link">Open console</Link>} />

      <main className="main">
        <section className="hero" id="top">
          <div className="hero-content">
            <h1 className="title">Protect the battery,<br />not just the message.</h1>
            <p className="hero-sub">Energy-aware security for post-quantum IoT.</p>
            <div className="hero-cta"><Button to="/dashboard">Open console</Button></div>
          </div>
          <button type="button" className="hero-scroll" onClick={go("mission")}>Scroll</button>
        </section>

        <section className="statement wrapper" id="mission">
          <div className="statement-box reveal">
            <h2 className="title statement-title">Our Mission</h2>
            <p className="statement-text">
              Post-quantum keys and signatures are large, and checking them costs real energy. An attacker who
              simply keeps saying hello can flatten a field sensor's battery without ever breaking a key.
              SentinelMesh sets out to measure that cost in joules on real hardware, and to defend against it.
            </p>
          </div>
        </section>

        <section className="statement right wrapper" id="approach">
          <div className="statement-box reveal">
            <h2 className="title statement-title">Our Approach</h2>
            <p className="statement-text">
              EnergyGate runs before the expensive handshake, using only signals that cost nothing to collect.
              It decides whether to spend the full post-quantum handshake, send a cheap cookie challenge, or drop
              the request, against a joule-denominated energy budget.
            </p>
          </div>
        </section>

        <section className="choose">
          <div className="choose-head reveal"><h2 className="title">What brings you to SentinelMesh?</h2></div>
          <div className="choose-grid reveal" style={{ "--d": "0.1s" } as React.CSSProperties}>
            <FlipCard title="I'm an Operator" to="/dashboard"
              cta="Open console"
              back="Watch the link, the battery and every EnergyGate decision live, and run the drain attack yourself." />
            <FlipCard title="I'm a Reviewer" to="/dashboard?tab=incidents"
              cta="See incidents"
              back="See how four detection layers join into one incident: phishing email, malicious file, radio link and physical tamper." />
          </div>
        </section>

        <section className="join on-deep">
          <TileField />
          <div className="join-inner">
            <h2 className="title reveal">See the drain attack live.</h2>
            <p className="join-sub reveal" style={{ "--d": "0.08s" } as React.CSSProperties}>Watch the battery fall, then watch EnergyGate stop it.</p>
            <div className="join-cta reveal" style={{ "--d": "0.16s" } as React.CSSProperties}><Button to="/dashboard">Open console</Button></div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
