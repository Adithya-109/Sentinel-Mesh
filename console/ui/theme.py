"""Visual identity for the console UI.

Palette: maroon #6D0808, near-black #2D0000, sage #757D6F, beige #EEEAD7 --
a warm, muted set rather than the stock Streamlit blue/red. The near-black
is the page background itself (not just a dark-mode fallback), maroon is the
one accent used for anything that needs to grab attention, and sage/beige
carry everything else.

Severity keeps the same design rule the original palette used: high and
critical share the same hue (maroon) deliberately -- they are the same kind
of bad, one worse than the other -- and are told apart by fill, not colour.
Info through medium step from sage up through a warm tan/rust on the way to
that maroon, so the ramp reads as "calm -> urgent" at a glance.
"""

SEVERITY = {
    "info":     {"color": "#8A9180", "icon": "•",   "fill": False, "label": "info"},
    "low":      {"color": "#B08D52", "icon": "!",        "fill": False, "label": "low"},
    "medium":   {"color": "#B0522E", "icon": "!!",       "fill": False, "label": "medium"},
    "high":     {"color": "#8A2A14", "icon": "!!!",      "fill": False, "label": "high"},
    "critical": {"color": "#6D0808", "icon": "✖",   "fill": True,  "label": "critical"},
}
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

LAYER_ICON = {"mail": "MAIL", "file": "FILE", "field": "FIELD", "tamper": "TAMPER"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --sm-bg:         #2D0000;
  --sm-surface:    #391212;
  --sm-surface-2:  #481A1A;
  --sm-ink:        #F5F1E4;
  --sm-ink-2:      #CFC9B8;
  --sm-muted:      #A39C8C;
  --sm-rule:       #4E2323;
  --sm-border:     rgba(238,234,215,0.11);
  --sm-accent:     #6D0808;
  --sm-accent-2:   #2D0000;
  --sm-sage:       #8A9180;
  --sm-beige:      #EEEAD7;
  --sm-font-head:  'Fraunces', Georgia, serif;
  --sm-font-body:  'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --sm-font-mono:  'JetBrains Mono', ui-monospace, Menlo, monospace;
}

/* -- base ----------------------------------------------------------- */
html, body, .stApp {
  background: var(--sm-bg) !important;
  color: var(--sm-ink);
  font-family: var(--sm-font-body);
}
[data-testid="stMainBlockContainer"] { padding-top: 2.2rem; max-width: 1180px; }
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
  font-family: var(--sm-font-head); font-weight: 600; letter-spacing: -0.01em;
  color: var(--sm-ink);
}
[data-testid="stHeading"] h2 { margin-top: 0.2rem; }
[data-testid="stCaptionContainer"] { color: var(--sm-muted) !important; font-size: 0.85rem; }
p, span, label, div { font-family: var(--sm-font-body); }
hr { border-color: var(--sm-rule) !important; margin: 1.6rem 0 !important; }

/* -- sidebar ---------------------------------------------------------*/
[data-testid="stSidebar"] {
  background: var(--sm-surface); border-right: 1px solid var(--sm-border);
}
[data-testid="stSidebarContent"] { padding-top: 1.6rem; }
[data-testid="stSidebar"] [data-testid="stHeading"] h1 {
  font-size: 1.4rem; margin-bottom: 0;
}
[data-testid="stRadioOption"] {
  padding: 7px 10px; border-radius: 8px; margin-bottom: 2px;
  transition: background 0.15s ease;
}
[data-testid="stRadioOption"]:hover { background: var(--sm-surface-2); }

/* -- inputs & controls ------------------------------------------------*/
[data-testid="stButton"] button, [data-testid^="stBaseButton"] {
  border-radius: 10px !important; font-weight: 600 !important;
  font-family: var(--sm-font-body) !important;
}
[data-testid="stExpander"] {
  background: var(--sm-surface); border: 1px solid var(--sm-border) !important;
  border-radius: 12px; overflow: hidden;
}
[data-testid="stAlert"] { border-radius: 10px; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background: rgba(138,145,128,0.16) !important; color: #D6D2C2 !important;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--sm-border); border-radius: 10px; overflow: hidden;
}
[data-testid="stMultiSelectTagsContainer"] span {
  background: var(--sm-surface-2) !important;
}
[data-testid="stMetricValue"] { font-family: var(--sm-font-head); color: var(--sm-ink); }
[data-testid="stMetricLabel"] { color: var(--sm-ink-2); }

/* -- custom components -------------------------------------------------*/
.sm-chip {
  display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:999px;
  font-size:0.72rem; font-weight:700; letter-spacing:0.03em; text-transform:uppercase;
  border:1.5px solid currentColor; white-space:nowrap;
}
.sm-chip.filled { color:var(--sm-beige) !important; border-color:transparent; }

.sm-tile {
  border:1px solid var(--sm-border); border-radius:14px; padding:18px 20px;
  background:var(--sm-surface); border-left-width:4px;
}
.sm-tile .n { font-family:var(--sm-font-head); font-size:2rem; font-weight:600; line-height:1; color:var(--sm-ink); }
.sm-tile .k { font-size:0.72rem; color:var(--sm-ink-2); text-transform:uppercase;
              letter-spacing:0.06em; margin-top:8px; font-weight:600; }

.sm-row {
  display:flex; gap:16px; align-items:flex-start;
  padding:13px 10px; border-bottom:1px solid var(--sm-rule); border-radius:8px;
}
.sm-row .t { min-width:62px; color:var(--sm-muted); font-family:var(--sm-font-mono);
             font-size:0.76rem; white-space:nowrap; padding-top:3px; }
.sm-row .s { color:var(--sm-ink); font-size:0.95rem; line-height:1.5; }
.sm-row .m { color:var(--sm-ink-2); font-size:0.8rem; margin-top:2px; }

.sm-step {
  border:1.5px solid var(--sm-rule); border-radius:12px; padding:14px 8px;
  text-align:center; color:var(--sm-muted); font-size:0.82rem; font-weight:600;
  background:var(--sm-surface);
}
.sm-step.lit { border-color:var(--sm-accent); color:var(--sm-beige); background:var(--sm-accent); }
.sm-arrow { text-align:center; color:var(--sm-muted); padding-top:16px; font-size:1.2rem; }

.sm-why {
  border-left:3px solid var(--sm-rule); padding:3px 0 3px 14px; margin:6px 0;
  color:var(--sm-ink-2); font-size:0.87rem; line-height:1.5;
}
.sm-tech {
  display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.72rem;
  border:1px solid var(--sm-border); color:var(--sm-sage); background:rgba(138,145,128,0.12);
  font-family:var(--sm-font-mono);
}
.sm-note { color:var(--sm-muted); font-size:0.84rem; font-style:italic; padding:4px 2px; }
</style>
"""


def chip(severity: str) -> str:
    s = SEVERITY.get(severity, SEVERITY["info"])
    style = f"background:{s['color']};" if s["fill"] else f"color:{s['color']};"
    cls = "sm-chip filled" if s["fill"] else "sm-chip"
    return f'<span class="{cls}" style="{style}">{s["icon"]} {s["label"]}</span>'


def tile(n, caption: str, severity: str = "info") -> str:
    color = SEVERITY.get(severity, SEVERITY["info"])["color"]
    return (f'<div class="sm-tile" style="border-left-color:{color}">'
            f'<div class="n">{n}</div><div class="k">{caption}</div></div>')


def color_for(severity: str) -> str:
    return SEVERITY.get(severity, SEVERITY["info"])["color"]
