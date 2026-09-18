"""SentinelMesh attack-chain console (Streamlit).

Reads the console API on :8000 -- it never touches the database directly, so
what an operator sees is exactly what the API serves, and the UI can run on a
different machine from the gateway laptop if the demo needs it.

    streamlit run ui/app.py          # from console/

Pages: Timeline, Incidents, Scan, Trace recording, Evidence.
"""
import json
import os
import sys
import time

import requests
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import attack                      # noqa: E402  (labels only, no DB access)
from ui import theme                        # noqa: E402

# 127.0.0.1, never "localhost" -- see console/api/config.py for the 2s-per-request
# reason on Windows. Every page polls, so the UI would feel broken.
CONSOLE_URL = os.environ.get("SENTINEL_CONSOLE_URL", "http://127.0.0.1:8000")
ML_URL = os.environ.get("SENTINEL_ML_URL", "http://127.0.0.1:8001")
ML_REPORTS = os.environ.get(
    "SENTINEL_ML_REPORTS",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml", "reports"),
)

st.set_page_config(page_title="SentinelMesh console", page_icon="\U0001F6E1", layout="wide")
st.markdown(theme.CSS, unsafe_allow_html=True)

# Event types that fire constantly by design (EnergyGate scores every single
# handshake attempt) and were never meant to be read one-by-one -- they flood
# the live feed without being alerts. Shown as a count, not a wall of rows.
ROUTINE_TYPES = {"gate_decision"}


# -- API helpers -----------------------------------------------------------

@st.cache_resource
def http() -> requests.Session:
    """One pooled session for the whole app -- every page polls, and reopening
    a connection per widget render makes the UI feel sluggish."""
    return requests.Session()


def api_get(path: str, **params):
    try:
        r = http().get(f"{CONSOLE_URL}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def api_post(path: str, payload: dict | None = None, base: str = None):
    try:
        r = http().post(f"{base or CONSOLE_URL}{path}", json=payload or {}, timeout=30)
        return r, None
    except requests.RequestException as exc:
        return None, str(exc)


def fmt_time(ts_ms: int) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts_ms / 1000))


def fmt_date(ts_ms: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_ms / 1000))


# -- shared fragments ------------------------------------------------------

def event_row(e: dict, show_date: bool = False) -> str:
    when = fmt_date(e["ts"]) if show_date else fmt_time(e["ts"])
    score = f' &middot; score {e["score"]:.3f}' if e.get("score") is not None else ""
    node = f' &middot; {e["node"]}' if e.get("node") else ""
    tech = ""
    if e.get("technique"):
        info = attack.technique_info(e["technique"])
        tech = f' <span class="sm-tech">{e["technique"]} {info["name"]}</span>'
    return (
        f'<div class="sm-row">'
        f'<div class="t">{when}</div>'
        f'<div>{theme.chip(e["severity"])}</div>'
        f'<div style="flex:1">'
        f'<div class="s"><b>{theme.LAYER_ICON.get(e["layer"], e["layer"])}</b> &nbsp;{e["summary"]}</div>'
        f'<div class="m">{e["type"]}{node}{score}{tech}</div>'
        f'</div></div>'
    )


def why_panel(e: dict) -> None:
    """The 'why' behind one alert: the detector's top reasons, plus ATT&CK."""
    if e.get("technique"):
        info = attack.technique_info(e["technique"])
        st.markdown(
            f'<span class="sm-tech">{e["technique"]}</span> &nbsp;**{info["name"]}** '
            f'&nbsp;<span style="color:var(--sm-muted)">{info["tactic"]}</span>',
            unsafe_allow_html=True,
        )
    reasons = e.get("reasons") or []
    if reasons:
        for r in reasons:
            st.markdown(f'<div class="sm-why">{r}</div>', unsafe_allow_html=True)
    else:
        st.caption("no reasons supplied by the detector")
    if e.get("details"):
        with st.expander("details"):
            st.json(e["details"])


def severity_tiles(events: list[dict]) -> None:
    counts = {s: 0 for s in theme.SEVERITY_ORDER}
    for e in events:
        counts[e["severity"]] = counts.get(e["severity"], 0) + 1
    cols = st.columns(len(theme.SEVERITY_ORDER), gap="small")
    for col, sev in zip(cols, theme.SEVERITY_ORDER):
        with col:
            st.markdown(theme.tile(counts.get(sev, 0), f"{sev} events", sev), unsafe_allow_html=True)


def chain_strip(chain: list[dict]) -> None:
    """Inbox -> Endpoint -> Field network -> Physical, lighting up as layers fire."""
    cols = st.columns([3, 1, 3, 1, 3, 1, 3], gap="small")
    for i, step in enumerate(chain):
        with cols[i * 2]:
            cls = "sm-step lit" if step["lit"] else "sm-step"
            st.markdown(f'<div class="{cls}">{step["step"]}</div>', unsafe_allow_html=True)
        if i < len(chain) - 1:
            with cols[i * 2 + 1]:
                st.markdown('<div class="sm-arrow">&rarr;</div>', unsafe_allow_html=True)


# -- pages -----------------------------------------------------------------

def page_timeline():
    st.subheader("Live timeline")
    data, err = api_get("/events", limit=500)
    if err:
        st.error(f"console API unreachable at {CONSOLE_URL} -- {err}")
        st.caption("Start it with:  uvicorn api.main:app --port 8000")
        return

    all_events = data["events"]
    if not all_events:
        st.info("No events yet. Run `python tools/mock_events.py` to replay the demo story.")
        return

    routine = [e for e in all_events if e["type"] in ROUTINE_TYPES]
    events = [e for e in all_events if e["type"] not in ROUTINE_TYPES]

    severity_tiles(events)
    st.write("")

    left, right = st.columns([1, 1], gap="large")
    with left:
        layers = st.multiselect("layer", ["mail", "file", "field", "tamper"], default=[])
    with right:
        min_sev = st.select_slider("minimum severity", options=list(reversed(theme.SEVERITY_ORDER)),
                                   value="info")

    from api.correlation import severity_rank
    shown = [e for e in events
             if (not layers or e["layer"] in layers)
             and severity_rank(e["severity"]) >= severity_rank(min_sev)]

    st.caption(f"{len(shown)} of {len(events)} alerts &middot; newest first")
    html = "".join(event_row(e) for e in reversed(shown))
    st.markdown(html, unsafe_allow_html=True)

    if routine:
        with st.expander(f"{len(routine)} routine EnergyGate decisions (not alerts, hidden by default)"):
            st.markdown("".join(event_row(e) for e in reversed(routine)), unsafe_allow_html=True)


def page_incidents():
    st.subheader("Incidents")
    st.caption("Correlation is rules, not ML -- a sliding 10-minute window, escalated when "
               "more than one layer fires. The ML lives in the detectors.")

    data, err = api_get("/incidents")
    if err:
        st.error(f"console API unreachable at {CONSOLE_URL} -- {err}")
        return

    incidents = data["incidents"]
    if not incidents:
        st.info("No incidents yet. Informational events (clean scans, rekeys) never form one.")
        return

    for inc in incidents:
        with st.container(border=True):
            head = (f'{theme.chip(inc["severity"])} &nbsp; **{inc["title"]}** '
                    f'&nbsp;<span style="color:var(--sm-muted)">{fmt_date(inc["started_ts"])} '
                    f'&middot; {inc["event_count"]} alerts &middot; {len(inc["layers"])} layers</span>')
            st.markdown(head, unsafe_allow_html=True)
            st.write("")
            chain_strip(inc["chain"])

            if inc["escalated_by"]:
                st.markdown(
                    '<div class="sm-why"><b>Why this severity:</b> base '
                    f'{inc["base_severity"]} &rarr; {inc["severity"]} &mdash; '
                    + "; ".join(inc["escalated_by"]) + "</div>",
                    unsafe_allow_html=True,
                )
            if inc["technique_names"]:
                st.markdown(" ".join(f'<span class="sm-tech">{t}</span>' for t in inc["technique_names"]),
                            unsafe_allow_html=True)

            with st.expander(f"timeline and why ({inc['event_count']} alerts)", expanded=inc is incidents[0]):
                for e in inc["events"]:
                    st.markdown(event_row(e), unsafe_allow_html=True)
                    why_panel(e)
                    st.write("")
        st.write("")


def page_scan():
    st.subheader("Scan")
    st.caption(f"Calls the ML service at {ML_URL} and stores the Event it returns. "
               "Safety rule: only benign files are ever scanned live.")

    health, err = None, None
    try:
        health = http().get(f"{ML_URL}/health", timeout=3).json()
    except requests.RequestException as exc:
        err = str(exc)
    if health:
        st.success(f"ML service up -- MailGuard {'loaded' if health.get('mailguard_loaded') else 'MISSING'}, "
                   f"FileGuard {'loaded' if health.get('fileguard_loaded') else 'MISSING'}")
    else:
        st.warning(f"ML service not reachable at {ML_URL} ({err}). "
                   "Start it with: uvicorn service:app --port 8001 (from ml/)")

    tab_email, tab_file = st.tabs(["Email", "File"])

    with tab_email:
        text = st.text_area("Paste an email", height=200,
                            placeholder="Subject and body -- paste a suspicious email here")
        if st.button("Scan email", type="primary", disabled=not text.strip()):
            r, exc = api_post("/score/email", {"text": text}, base=ML_URL)
            if exc:
                st.error(f"ML service unreachable: {exc}")
            elif r.status_code != 200:
                st.error(f"{r.status_code}: {r.text[:300]}")
            else:
                _show_and_store(r.json())

    with tab_file:
        st.caption("Upload a **benign** binary (.exe/.dll) or an .eml message. "
                   "Malicious samples in the demo are held-out dataset feature rows, never real files.")
        up = st.file_uploader("File", type=None)
        if up is not None and st.button("Scan file", type="primary"):
            endpoint = "/score/eml" if up.name.lower().endswith(".eml") else "/score/file"
            try:
                r = http().post(f"{ML_URL}{endpoint}",
                                files={"file": (up.name, up.getvalue())}, timeout=60)
            except requests.RequestException as exc:
                st.error(f"ML service unreachable: {exc}")
                return
            if r.status_code != 200:
                st.error(f"{r.status_code}: {r.text[:300]}")
                return
            body = r.json()
            for ev in (body if isinstance(body, list) else [body]):
                _show_and_store(ev)


def _show_and_store(event: dict) -> None:
    """Show a scored Event, then POST it to the console so it joins the timeline."""
    st.markdown(event_row(event, show_date=True), unsafe_allow_html=True)
    why_panel(event)
    r, exc = api_post("/events", event)
    if exc:
        st.warning(f"scored, but the console did not accept it: {exc}")
    elif r.status_code == 201:
        st.caption("stored -- it is on the timeline now")
    elif r.status_code == 422:
        st.error("The ML service returned an Event that fails contracts/event.schema.json:")
        st.json(r.json().get("errors"))
    else:
        st.warning(f"console returned {r.status_code}: {r.text[:200]}")


def page_traces():
    st.subheader("Trace recording")
    st.caption("Records the gateway's TRC windows with the label you choose, into "
               "one .jsonl per session -- the training set for the FieldGuard on-device model. "
               "The serial bridge picks the label up and sends `LABEL <x>` to the gateway.")

    rec, err = api_get("/recording")
    if err:
        st.error(f"console API unreachable -- {err}")
        return

    labels = ["normal", "weak_link", "replay", "flood", "impersonation"]

    if rec["active"]:
        st.success(f"RECORDING  &middot;  session **{rec['session']}**  &middot;  "
                   f"label **{rec['label']}**  &middot;  {rec['rows']} rows kept, {rec['dropped']} dropped")
        if rec.get("mismatched"):
            st.warning(
                f"{rec['mismatched']} of {rec['rows']} rows disagreed with the gateway's own label. "
                f"That is expected right after you switch labels, but if it keeps climbing you are "
                f"probably recording one attack under another attack's name -- which would train the "
                f"field model on the wrong thing. Check the attacker node is running **{rec['label']}**."
            )
    else:
        st.info("Not recording. TRC lines arriving now are discarded.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Session**")
        session = st.text_input("name", value=time.strftime("session_%Y%m%d_%H%M%S"),
                                disabled=rec["active"])
        start_label = st.selectbox("starting label", labels, disabled=rec["active"])
        if rec["active"]:
            if st.button("Stop recording", type="primary"):
                api_post("/recording/stop")
                st.rerun()
        else:
            if st.button("Start recording", type="primary"):
                api_post("/recording/start", {"session": session, "label": start_label})
                st.rerun()

    with col_b:
        st.markdown("**Label the windows arriving now**")
        st.caption("Switch this as you run each attack from the attacker node.")
        for lab in labels:
            if st.button(lab, use_container_width=True, disabled=not rec["active"],
                         type="secondary" if lab != rec["label"] else "primary"):
                api_post("/recording/label", {"label": lab})
                st.rerun()

    st.divider()
    st.markdown("**Recorded sessions**")
    traces, terr = api_get("/traces")
    if terr or not traces["sessions"]:
        st.caption("Nothing recorded yet.")
        return
    st.dataframe(
        [{"session": s["session"], "rows": s["rows"],
          "labels": ", ".join(f"{k}:{v}" for k, v in sorted(s["labels"].items()))}
         for s in traces["sessions"]],
        use_container_width=True, hide_index=True,
    )
    st.caption(f"Files in `{traces['trace_dir']}`. Hand-off to the ML stream: copy them to "
               "`ml/data/traces/` and run `make field-model`.")


def page_evidence():
    st.subheader("Evidence")
    st.caption("The ML stream's measured numbers and pitch charts, read straight from ml/reports/.")

    charts_dir = os.path.join(ML_REPORTS, "charts")
    metrics_path = os.path.join(ML_REPORTS, "metrics.json")

    if os.path.exists(metrics_path):
        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)
        mail = metrics.get("mailguard", {})
        file_ = metrics.get("fileguard", {})
        loco = mail.get("email_leave_one_corpus_out", {})
        accs = [v["acc"] for v in loco.values() if "acc" in v]
        det = file_.get("malware_group_split_final", {}).get("detection_at_0p1pct_false_alarm")

        # Only the honest numbers get a tile here. The flattering random-split
        # score exists in metrics.json too, but the project's own rule is not
        # to quote it -- so it doesn't get to be the thing an operator sees first.
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown(
                theme.tile(f"{min(accs):.1%}-{max(accs):.1%}" if accs else "-",
                           "MailGuard &middot; held-out corpus accuracy", "info"),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                theme.tile(f"{det:.1%}" if det else "-",
                           "FileGuard &middot; detection @ 0.1% false alarms", "info"),
                unsafe_allow_html=True,
            )
        st.write("")

        with st.expander("full metrics.json"):
            st.json(metrics)
    else:
        st.caption(f"No metrics.json at {metrics_path}.")

    st.write("")
    if os.path.isdir(charts_dir):
        pngs = sorted(f for f in os.listdir(charts_dir) if f.endswith(".png"))
        if pngs:
            cols = st.columns(len(pngs), gap="medium")
            for col, name in zip(cols, pngs):
                with col:
                    with st.container(border=True):
                        st.image(os.path.join(charts_dir, name), use_container_width=True)
        else:
            st.caption("No charts yet -- the ML stream writes them with reports/make_charts.py.")
    else:
        st.caption(f"No charts directory at {charts_dir}.")


# -- shell -----------------------------------------------------------------

PAGES = {
    "Timeline": page_timeline,
    "Incidents": page_incidents,
    "Scan": page_scan,
    "Trace recording": page_traces,
    "Evidence": page_evidence,
}

with st.sidebar:
    st.title("SentinelMesh")
    st.caption("Attack-chain console")
    st.write("")
    choice = st.radio("Page", list(PAGES), label_visibility="collapsed")
    st.divider()

    health, herr = api_get("/health")
    if health:
        st.success(f"console up &middot; {health['events']} events")
    else:
        st.error("console API down")
        st.code("uvicorn api.main:app --port 8000", language="bash")

    col_a, col_b = st.columns(2, gap="small")
    with col_a:
        auto_refresh = st.checkbox("Auto-refresh", value=False)
    with col_b:
        if st.button("Refresh", use_container_width=True):
            st.rerun()
    if auto_refresh:
        time.sleep(3)
        st.rerun()

    st.divider()
    st.caption(f"console &middot; {CONSOLE_URL}  \nML service &middot; {ML_URL}")

PAGES[choice]()
