import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { BatteryChart, PowerChart, ProjectionChart } from "../charts";
import CyberMeshBackground from "../components/CyberMeshBackground";
import TiltCard from "../components/TiltCard";
import { useEnergy, useEvents, usePoll } from "../data";
import { ExperimentTable, Scan } from "../experiment";
import { Controls, GateFeed, Incidents, StatusBar, Timeline } from "../panels";
import { Card } from "../ui";

const FIXTURES = import.meta.env.VITE_USE_FIXTURES === "1";

type Tab = "overview" | "events" | "incidents" | "energy" | "experiment" | "scan";
const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "events", label: "Events" },
  { id: "incidents", label: "Incidents" },
  { id: "energy", label: "Energy" },
  { id: "experiment", label: "Experiment" },
  { id: "scan", label: "Scan" },
];

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const status = usePoll(api.status, 1000);
  const incidents = usePoll(api.incidents, 3000);
  const [profile, setProfile] = useState("loud");
  const experiment = usePoll(() => api.experiment(profile), 3000);
  const { events, error: evError, resync } = useEvents();
  const { series, resync: resyncEnergy } = useEnergy();

  const refreshAll = () => { status.refresh(); incidents.refresh(); experiment.refresh(); resync(); resyncEnergy(); };
  const simulated = !!status.data?.simulated || !!series.simulated;
  const down = status.error !== null;
  const incidentBadge = incidents.data?.filter(i => i.severity === "critical" || i.severity === "high").length ?? 0;
  const gateCount = events.filter(e => e.type === "gate_decision").length;

  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <CyberMeshBackground dim />
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden>
            <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
              <polygon points="11,1 21,6 21,16 11,21 1,16 1,6" stroke="#fff" strokeWidth="2" fill="none" />
              <circle cx="11" cy="11" r="3" fill="#fff" />
            </svg>
          </span>
          <span>Sentinel<b>Mesh</b></span>
        </Link>
        <div className="brand-sub">Security Console</div>
        <nav className="tabs">
          {TABS.map(t => (
            <button key={t.id} className={`tab${tab === t.id ? " on" : ""}`} onClick={() => setTab(t.id)}>
              {t.label}
              {t.id === "incidents" && incidentBadge > 0 && <span className="tab-badge">{incidentBadge}</span>}
              {t.id === "events" && gateCount > 0 && <span className="tab-dot" />}
            </button>
          ))}
        </nav>
        <a href="/" className="back-link">&larr; Website</a>
      </aside>

      <main className="main">
        <header className="topbar">
          <span className={`conn${down ? " bad" : ""}`}>
            {FIXTURES ? "○ fixtures — no API in use"
              : down ? `✖ console API unreachable (${status.error})` : "✔ console API connected"}
          </span>
        </header>

        {FIXTURES && <div className="banner fixtures">FIXTURE MODE &mdash; showing console/frontend-kit/fixtures, not live data. Controls do nothing.</div>}
        {simulated && !FIXTURES && (
          <div className="banner">SIMULATED ENERGY DATA from tools/mock_rig.py &mdash; illustrates the idea, measures nothing. Do not quote these numbers.</div>
        )}

        <StatusBar s={status.data} />
        <Controls s={status.data} onChange={refreshAll} />

        {tab === "overview" && (
          <div className="grid-main">
            <div className="col">
              <TiltCard maxTilt={2} glare={false}><Incidents incidents={incidents.data} error={incidents.error} /></TiltCard>
              <TiltCard maxTilt={2} glare={false}><Card title="Battery projection"><ProjectionChart exp={experiment.data} /></Card></TiltCard>
            </div>
            <div className="col">
              <TiltCard maxTilt={2} glare={false}><GateFeed events={events} /></TiltCard>
            </div>
          </div>
        )}

        {tab === "events" && <Timeline events={events} error={evError} />}

        {tab === "incidents" && <Incidents incidents={incidents.data} error={incidents.error} />}

        {tab === "energy" && (
          <Card title="Energy" hint="live, 1 s samples from the INA219 monitor · markers show when the controls changed">
            <div className="row2">
              <PowerChart series={series} baseline={status.data?.baseline_mw ?? null} />
              <BatteryChart series={series} />
            </div>
          </Card>
        )}

        {tab === "experiment" && (
          <ExperimentTable exp={experiment.data} error={experiment.error} profile={profile}
            setProfile={p => { setProfile(p); setTimeout(experiment.refresh, 0); }} onChange={refreshAll} />
        )}

        {tab === "scan" && <Scan onStored={refreshAll} />}
      </main>
    </div>
  );
}
