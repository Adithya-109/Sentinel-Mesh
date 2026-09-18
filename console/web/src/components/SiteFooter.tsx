import { Link } from "react-router-dom";
import { Button, Wordmark } from "./parts";

const REPO = "https://github.com/ramkirangaruda/Sentinel-Mesh";

export default function SiteFooter() {
  return (
    <footer className="footer">
      <div className="wrapper">
        <div className="footer-grid">
          <div className="f1">
            <Wordmark />
            <p className="f1-2">Energy-aware security for post-quantum IoT.</p>
            <div className="f1-3"><Button to="/dashboard" contrast small>Open console</Button></div>
          </div>
          <div className="f2">
            <div>
              <h3>Console</h3>
              <ul>
                {["overview", "events", "incidents", "energy", "experiment", "scan"].map(t => (
                  <li key={t}><Link className="underline-link" to={`/dashboard?tab=${t}`}>{t[0].toUpperCase() + t.slice(1)}</Link></li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Project</h3>
              <ul>
                <li><a className="underline-link" href={REPO} target="_blank" rel="noreferrer">Source on GitHub</a></li>
                <li>Code Cortex 3.0</li>
                <li>Security track</li>
              </ul>
            </div>
          </div>
          <div className="f3">
            <h3>Honest numbers</h3>
            <p>Anything simulated is labelled SIMULATED, and never presented as a result.</p>
          </div>
          <div className="f4">
            <p>Copyright SentinelMesh</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
