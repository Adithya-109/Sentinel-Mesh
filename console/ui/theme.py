"""Severity styling for the console UI.

Colours come from the validated status palette (good / warning / serious /
critical), which is reserved for state and never reused as a series colour.
The contract has five severities and the palette has four status roles, so:

    info      neutral grey   -- "we looked, it was fine"; not an alarm state
    low       warning        #fab219
    medium    serious        #ec835a
    high      critical       #d03b3b   (outlined chip)
    critical  critical       #d03b3b   (solid chip, inverted text)

high and critical share a hue deliberately -- they are the same kind of bad,
one worse than the other -- and are told apart by fill, icon and the label
text, which every chip carries. Colour never carries meaning on its own, which
also keeps the timeline readable for colour-blind viewers and on a projector.

On the light surface `warning` and `serious` sit below 3:1 contrast by design;
the icon + label pairing is the documented mitigation.
"""

SEVERITY = {
    "info":     {"color": "#898781", "icon": "•", "fill": False, "label": "info"},
    "low":      {"color": "#fab219", "icon": "!", "fill": False, "label": "low"},
    "medium":   {"color": "#ec835a", "icon": "!!", "fill": False, "label": "medium"},
    "high":     {"color": "#d03b3b", "icon": "!!!", "fill": False, "label": "high"},
    "critical": {"color": "#d03b3b", "icon": "###", "fill": True, "label": "critical"},
}
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

LAYER_ICON = {"mail": "MAIL", "file": "FILE", "field": "FIELD", "tamper": "TAMPER"}

CSS = """
<style>
:root {
  --sm-ink:       #0b0b0b;
  --sm-ink-2:     #52514e;
  --sm-muted:     #898781;
  --sm-surface:   #fcfcfb;
  --sm-rule:      #e1e0d9;
  --sm-border:    rgba(11,11,11,0.10);
}
@media (prefers-color-scheme: dark) {
  :root {
    --sm-ink:     #ffffff;
    --sm-ink-2:   #c3c2b7;
    --sm-muted:   #898781;
    --sm-surface: #1a1a19;
    --sm-rule:    #2c2c2a;
    --sm-border:  rgba(255,255,255,0.10);
  }
}
.sm-chip {
  display:inline-block; padding:1px 8px; border-radius:999px;
  font-size:0.72rem; font-weight:600; letter-spacing:0.02em;
  border:1.5px solid currentColor; white-space:nowrap;
}
.sm-chip.filled { color:#fcfcfb !important; border-color:transparent; }
.sm-tile {
  border:1px solid var(--sm-border); border-radius:10px; padding:10px 14px;
  background:var(--sm-surface); border-left-width:4px;
}
.sm-tile .n { font-size:1.9rem; font-weight:700; line-height:1.1; color:var(--sm-ink); }
.sm-tile .k { font-size:0.75rem; color:var(--sm-ink-2); text-transform:uppercase; letter-spacing:0.04em; }
.sm-row {
  display:flex; gap:12px; align-items:flex-start;
  padding:9px 0; border-bottom:1px solid var(--sm-rule);
}
.sm-row .t { color:var(--sm-muted); font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
             font-size:0.78rem; white-space:nowrap; padding-top:2px; }
.sm-row .s { color:var(--sm-ink); font-size:0.92rem; }
.sm-row .m { color:var(--sm-ink-2); font-size:0.78rem; }
.sm-step {
  border:1.5px solid var(--sm-rule); border-radius:10px; padding:10px 6px;
  text-align:center; color:var(--sm-muted); font-size:0.8rem; font-weight:600;
}
.sm-step.lit { border-color:#d03b3b; color:#d03b3b; background:rgba(208,59,59,0.07); }
.sm-arrow { text-align:center; color:var(--sm-muted); padding-top:12px; font-size:1.1rem; }
.sm-why {
  border-left:3px solid var(--sm-rule); padding:2px 0 2px 12px; margin:4px 0;
  color:var(--sm-ink-2); font-size:0.86rem;
}
.sm-tech {
  display:inline-block; padding:1px 7px; border-radius:4px; font-size:0.72rem;
  border:1px solid var(--sm-border); color:var(--sm-ink-2);
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}
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
