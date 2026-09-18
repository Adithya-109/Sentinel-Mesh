import { useState } from "react";
import { api } from "./api";
import { BatteryChart, PowerChart, ProjectionChart } from "./charts";
import { useEnergy, useEvents, usePoll } from "./data";
import { ExperimentTable, Scan } from "./experiment";
import { Controls, GateFeed, Incidents, StatusBar, Timeline } from "./panels";
import { Card } from "./ui";

const FIXTURES = import.meta.env.VITE_USE_FIXTURES === "1";

export default function App() {
  const status = usePoll(api.status, 1000);
  const incidents = usePoll(api.incidents, 3000);
  const [profile, setProfile] = useState("loud");
  const experiment = usePoll(() => api.experiment(profile), 3000);
  const { events, error: evError, resync } = useEvents();
  const { series, resync: resyncEnergy } = useEnergy();

  const refreshAll = () => { status.refresh(); incidents.refresh(); experiment.refresh(); resync(); resyncEnergy(); };
  const simulated = !!status.data?.simulated || !!series.simulated;
  const down = status.error !== null;

  return (
    <div className="app">
      <header className="header">
        <h1>SentinelMesh</h1>
        <span className="sub">attack-chain console &middot; inbox &rarr; endpoint &rarr; field network &rarr; physical</span>
        <span className="spacer" />
        <span className={`conn${down ? " bad" : ""}`}>
          {FIXTURES ? "\u25cb fixtures \u2014 no API in use"
            : down ? `\u2716 console API unreachable (${status.error})` : "\u2714 console API connected"}
        </span>
      </header>

      {FIXTURES && <div className="banner fixtures">FIXTURE MODE &mdash; showing console/frontend-kit/fixtures, not live data. Controls do nothing.</div>}
      {simulated && !FIXTURES && (
        <div className="banner">SIMULATED ENERGY DATA from tools/mock_rig.py &mdash; illustrates the idea, measures nothing. Do not quote these numbers.</div>
      )}

      <StatusBar s={status.data} />
      <Controls s={status.data} onChange={refreshAll} />

      <div className="grid-main">
        <div className="col">
          <Incidents incidents={incidents.data} error={incidents.error} />
          <Card title="Energy" hint="live, 1 s samples from the INA219 monitor · markers show when the controls changed">
            <div className="row2">
              <PowerChart series={series} baseline={status.data?.baseline_mw ?? null} />
              <BatteryChart series={series} />
            </div>
          </Card>
          <Card title="Battery projection"><ProjectionChart exp={experiment.data} /></Card>
        </div>
        <div className="col">
          <GateFeed events={events} />
          <Timeline events={events} error={evError} />
        </div>
      </div>

      <div className="full">
        <ExperimentTable exp={experiment.data} error={experiment.error} profile={profile}
          setProfile={p => { setProfile(p); setTimeout(experiment.refresh, 0); }} onChange={refreshAll} />
      </div>
      <div className="full"><Scan onStored={refreshAll} /></div>
    </div>
  );
}
