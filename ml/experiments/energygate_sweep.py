"""EnergyGate operating-point sweep: legitimate senders connected vs. energy an
attacker still makes the node spend, as the spend threshold moves.

SIMULATED. The scores come from a model trained on simulated traces
(tests/generate_synthetic_traces.py --hard), so this shows the *shape* of the
trade-off the mechanism offers, not a measured result. Every chart it writes
says so on the figure.

Inputs are out-of-fold scores (each session scored by a model that never saw
it) and the recorded real / not-real label per window.

Policy, per window, mirroring firmware/.../gate_policy.h:
    score >= t_spend                  -> SPEND      (full handshake)
    t_challenge <= score < t_spend    -> CHALLENGE  (cheap cookie round-trip)
    score <  t_challenge              -> DROP
with t_challenge = t_spend * (0.4 / 0.7), the firmware's default ratio.

Outcomes (assumptions, stated on the chart):
  * a legitimate sender answers a challenge and then connects (delayed, not lost);
  * an attacker does not complete the handshake after a challenge, so it costs the
    node only the challenge, CHALLENGE_COST of a full handshake (ASSUMED 5%; the
    real ratio has to be measured with the INA219 rig);
  * no defence = every window is spent: 100% of legit connect, 100% attack energy.
"""
import json

import numpy as np

CHALLENGE_COST = 0.05         # ASSUMED: cookie round-trip as a fraction of a full handshake
FIRMWARE_SPEND, FIRMWARE_CHALLENGE = 0.7, 0.4   # gate_policy.h defaults (placeholders)
CHALLENGE_RATIO = FIRMWARE_CHALLENGE / FIRMWARE_SPEND


def outcomes(p, real, t_spend, use_challenge=True):
    """Return (legit connected %, legit delayed %, attack energy % of undefended)."""
    spend = p >= t_spend
    if use_challenge:
        challenge = (p >= t_spend * CHALLENGE_RATIO) & ~spend
    else:
        challenge = np.zeros_like(spend)
    legit, attack = real == 1, real == 0
    connected = (spend | challenge)[legit].mean() * 100
    delayed = challenge[legit].mean() * 100
    energy = (spend[attack].sum() + CHALLENGE_COST * challenge[attack].sum()) / attack.sum() * 100
    return float(connected), float(delayed), float(energy)


def sweep(p, real, use_challenge=True):
    grid = np.round(np.arange(0.05, 0.96, 0.01), 2)
    return [dict(t_spend=float(t), **dict(zip(("legit_connected_pct", "legit_delayed_pct", "attack_energy_pct"),
                                              outcomes(p, real, t, use_challenge)))) for t in grid]


def plot(gate, binary, firmware_point, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    BLUE, ORANGE = "#2a78d6", "#eb6834"      # reference palette slots 1-2

    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    xs = lambda rows: [r["legit_connected_pct"] for r in rows]
    ys = lambda rows: [r["attack_energy_pct"] for r in rows]
    ax.plot(xs(binary), ys(binary), color=ORANGE, lw=2, label="Spend / drop only (no challenge)")
    ax.plot(xs(gate), ys(gate), color=BLUE, lw=2, label="Spend / challenge / drop (EnergyGate policy)")
    ax.text(0.99, 0.97, "Undefended (off the scale): 100% of legit senders connect,\n"
            "and the attacker gets 100% of the energy it wants", transform=ax.transAxes,
            ha="right", va="top", fontsize=9, color=INK2)
    fx, fy = firmware_point["legit_connected_pct"], firmware_point["attack_energy_pct"]
    ax.scatter([fx], [fy], s=64, color=BLUE, zorder=6, edgecolor=SURFACE, linewidth=2)
    ax.annotate(f"firmware defaults 0.7 / 0.4\n{fx:.0f}% legit connect, {fy:.0f}% attack energy",
                (fx, fy), textcoords="offset points", xytext=(-16, 34), ha="right", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))

    ax.set_xlabel("Legitimate senders that connect (%)   -> better", color=INK2)
    ax.set_ylabel("Attacker-forced energy (% of undefended)\n<- better", color=INK2)
    ax.set_title("SIMULATED: the trade-off EnergyGate offers as its threshold moves",
                 loc="left", fontsize=13, color=INK, pad=14, fontweight="bold")
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2)
    ax.set_xlim(left=min(96.0, min(xs(binary) + xs(gate)) - 0.3), right=100.2)
    ax.set_ylim(0, 26)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.86), frameon=False, labelcolor=INK, fontsize=9)
    fig.text(0.01, 0.005,
             "SIMULATED: out-of-fold scores from a tree trained on simulated traces, not recordings.\n"
             f"Assumes a challenge costs {CHALLENGE_COST * 100:.0f}% of a handshake (not measured); legitimate senders "
             "pass it, attackers do not.\nPer-window, not a time simulation. Zoomed: stricter thresholds turn away "
             "more legit senders (off to the left).\nShows the shape of the mechanism, not a result.",
             fontsize=7.5, color=INK2, va="bottom")
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    fig.savefig(out_png, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def run(p, real, out_json, out_png):
    p, real = np.asarray(p, float), np.asarray(real, int)
    gate, binary = sweep(p, real, True), sweep(p, real, False)
    c, d, e = outcomes(p, real, FIRMWARE_SPEND, True)
    firmware = dict(t_spend=FIRMWARE_SPEND, t_challenge=FIRMWARE_CHALLENGE,
                    legit_connected_pct=c, legit_delayed_pct=d, attack_energy_pct=e,
                    share_of_windows_in_challenge_band=float(((p >= FIRMWARE_CHALLENGE) & (p < FIRMWARE_SPEND)).mean() * 100))
    result = dict(
        SIMULATED=True,
        note="out-of-fold scores from a model trained on simulated traces; the shape of the trade-off, not a result",
        assumptions=dict(challenge_cost_fraction_of_handshake=CHALLENGE_COST,
                         legit_sender_passes_challenge=True, attacker_passes_challenge=False),
        firmware_default_thresholds=firmware, gate_policy_sweep=gate, spend_drop_only_sweep=binary)
    with open(out_json, "w") as f:
        json.dump(result, f, indent=2)
    plot(gate, binary, firmware, out_png)
    return result
