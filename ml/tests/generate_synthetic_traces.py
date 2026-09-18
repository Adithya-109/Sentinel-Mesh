"""Synthetic Trace rows for testing the field-model pipeline end to end
before real recordings exist. Test-only: every label is prefixed
"SYNTH_" so it can never be mistaken for a real class, and nothing here
ever writes to ml/reports/ or ml/export/.

Each generated *.jsonl file is one synthetic "recording session" with its
own random RSSI baseline (simulating a different distance/environment),
so leave-one-session-out evaluation is non-trivial.
"""
import argparse
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "synthetic_traces")

SYNTH_CLASSES = ["SYNTH_normal", "SYNTH_weak_link", "SYNTH_replay", "SYNTH_flood", "SYNTH_impersonation"]


def _clip(x, lo, hi):
    return float(np.clip(x, lo, hi))


def _row(rng, label, rssi_base, battery_pct):
    """One physically-plausible window for `label`, around this session's
    rssi_base and battery_pct.

    frag_complete_pct / dup_pct (v4-optional Trace fields, EnergyGate's
    free signals): a legit sender's fragments mostly arrive complete with
    few duplicates; replay is duplicates *by definition*; flood tends to
    send incomplete garbage fast rather than clean duplicates.
    battery_pct is the field node's own level, not attacker-controlled --
    sampled once per session, same across every row in it.
    """
    if label == "SYNTH_normal":
        row = dict(
            hs_per_s=_clip(rng.normal(0.5, 0.2), 0, 3),
            hs_fail=0, replay_rej=0, auth_fail=0,
            stale=int(_clip(rng.poisson(0.2), 0, 3)),
            frag_timeout=0,
            rssi_mean=_clip(rng.normal(rssi_base, 3), -95, -30),
            rssi_var=_clip(rng.normal(2.5, 1), 0.2, 8),
            loss_pct=_clip(rng.normal(0.5, 0.5), 0, 3),
            jitter_ms=_clip(rng.normal(2.5, 1), 0.5, 6),
            frag_complete_pct=_clip(rng.normal(98, 2), 80, 100),
            dup_pct=_clip(rng.normal(0.5, 0.5), 0, 3),
        )
    elif label == "SYNTH_weak_link":
        row = dict(
            hs_per_s=_clip(rng.normal(0.5, 0.2), 0, 3),
            hs_fail=int(_clip(rng.poisson(1), 0, 5)),
            replay_rej=0, auth_fail=0,
            stale=int(_clip(rng.poisson(2), 0, 8)),
            frag_timeout=int(_clip(rng.poisson(1), 0, 5)),
            rssi_mean=_clip(rng.normal(rssi_base - 30, 5), -100, -60),
            rssi_var=_clip(rng.normal(10, 3), 4, 20),
            loss_pct=_clip(rng.normal(18, 8), 5, 45),
            jitter_ms=_clip(rng.normal(14, 5), 5, 35),
            frag_complete_pct=_clip(rng.normal(65, 12), 20, 95),
            dup_pct=_clip(rng.normal(5, 3), 0, 15),
        )
    elif label == "SYNTH_replay":
        row = dict(
            hs_per_s=_clip(rng.normal(0.5, 0.2), 0, 3),
            hs_fail=0,
            replay_rej=int(_clip(rng.normal(20, 8), 3, 60)),
            auth_fail=0,
            stale=int(_clip(rng.poisson(1), 0, 5)),
            frag_timeout=0,
            rssi_mean=_clip(rng.normal(rssi_base, 4), -95, -30),
            rssi_var=_clip(rng.normal(3, 1.5), 0.2, 9),
            loss_pct=_clip(rng.normal(1, 1), 0, 5),
            jitter_ms=_clip(rng.normal(3, 1.5), 0.5, 8),
            # captured-and-replayed packets are complete by construction
            frag_complete_pct=_clip(rng.normal(95, 3), 80, 100),
            dup_pct=_clip(rng.normal(30, 10), 10, 70),
        )
    elif label == "SYNTH_flood":
        row = dict(
            hs_per_s=_clip(rng.normal(150, 60), 30, 500),
            hs_fail=int(_clip(rng.normal(40, 15), 5, 150)),
            replay_rej=0,
            auth_fail=int(_clip(rng.normal(20, 10), 0, 80)),
            stale=int(_clip(rng.poisson(3), 0, 10)),
            frag_timeout=int(_clip(rng.poisson(4), 0, 15)),
            rssi_mean=_clip(rng.normal(rssi_base, 5), -95, -30),
            rssi_var=_clip(rng.normal(6, 3), 0.5, 15),
            loss_pct=_clip(rng.normal(12, 6), 1, 40),
            jitter_ms=_clip(rng.normal(10, 5), 1, 30),
            # spam over quality: often incomplete, some duplication
            frag_complete_pct=_clip(rng.normal(35, 15), 5, 80),
            dup_pct=_clip(rng.normal(15, 8), 0, 50),
        )
    elif label == "SYNTH_impersonation":
        row = dict(
            hs_per_s=_clip(rng.normal(2, 1), 0.2, 8),
            hs_fail=int(_clip(rng.normal(15, 6), 2, 50)),
            replay_rej=0,
            auth_fail=int(_clip(rng.normal(25, 10), 3, 80)),
            stale=0,
            frag_timeout=0,
            # attacker often transmits closer/stronger than the legit node
            rssi_mean=_clip(rng.normal(rssi_base + 15, 5), -80, -25),
            rssi_var=_clip(rng.normal(3, 1.5), 0.2, 9),
            loss_pct=_clip(rng.normal(1, 1), 0, 5),
            jitter_ms=_clip(rng.normal(2.5, 1), 0.5, 6),
            # crafted to look legit: complete fragments, low duplication
            frag_complete_pct=_clip(rng.normal(90, 5), 70, 100),
            dup_pct=_clip(rng.normal(1, 1), 0, 5),
        )
    else:
        raise ValueError(label)

    row.update(ts=0, node="gateway", label=label, window_ms=5000, battery_pct=battery_pct)
    return row


ATTACK_LABELS = {"SYNTH_replay", "SYNTH_flood", "SYNTH_impersonation"}
_FLOAT_KEYS = ("hs_per_s", "rssi_mean", "rssi_var", "loss_pct", "jitter_ms", "frag_complete_pct", "dup_pct")
_INT_KEYS = ("hs_fail", "replay_rej", "auth_fail", "stale", "frag_timeout")
_NOISY_KEYS = ("hs_per_s", "hs_fail", "rssi_var", "loss_pct", "jitter_ms", "dup_pct")
LABEL_FLIP_PROB = 0.03   # operator LABEL-command timing errors at attack start/stop


def _harden(rng, row, rssi_base, battery_pct):
    """Make a window less cleanly separable, as recorded data is.

    Hard mode only; the default generator is untouched so existing tests keep
    their behaviour. Three effects, fixed in advance rather than tuned to a
    result:
      * partial / stealthy attacks -- an attack window is interpolated toward a
        normal one by lambda ~ Beta(2, 1.2), so many attack windows are only
        weakly abnormal (and a mild weak_link window looks nearly normal);
      * multiplicative measurement noise on rates and counts;
      * label noise -- a few windows carry the wrong label (the console's LABEL
        command is set by a human, so windows straddling a switch are mislabelled).
    """
    lab = row["label"]
    if lab != "SYNTH_normal":
        normal = _row(rng, "SYNTH_normal", rssi_base, battery_pct)
        lam = rng.beta(2.0, 1.2) if lab in ATTACK_LABELS else rng.beta(1.5, 1.5)
        for k in _FLOAT_KEYS + _INT_KEYS:
            row[k] = normal[k] + lam * (row[k] - normal[k])
    for k in _NOISY_KEYS:
        row[k] = row[k] * rng.lognormal(0.0, 0.2)
    for k in _INT_KEYS:
        row[k] = int(max(0, round(row[k])))
    for k in ("loss_pct", "dup_pct", "frag_complete_pct"):
        row[k] = _clip(row[k], 0, 100)
    row["rssi_mean"] = _clip(row["rssi_mean"], -100, -20)
    for k in ("hs_per_s", "rssi_var", "jitter_ms"):
        row[k] = max(0.0, float(row[k]))
    if rng.random() < LABEL_FLIP_PROB:
        row["label"] = str(rng.choice([c for c in SYNTH_CLASSES if c != lab]))
    return row


def generate_session(rng, n_rows, class_weights=None, hard=False):
    rssi_base = float(rng.uniform(-65, -45))
    battery_pct = float(rng.uniform(20, 100))
    classes = SYNTH_CLASSES
    weights = class_weights or [0.5, 0.15, 0.12, 0.12, 0.11]
    labels = rng.choice(classes, size=n_rows, p=weights)
    rows = [_row(rng, lab, rssi_base, battery_pct) for lab in labels]
    if hard:
        rows = [_harden(rng, r, rssi_base, battery_pct) for r in rows]
    return rows


def main(n_sessions=6, rows_per_session=120, seed=0, hard=False, out_dir=None):
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(seed)
    total = 0
    for i in range(n_sessions):
        rows = generate_session(rng, rows_per_session, hard=hard)
        path = os.path.join(out_dir, f"session_{i + 1:02d}.jsonl")
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        total += len(rows)
    print(f"wrote {total} synthetic Trace rows across {n_sessions} sessions to {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=6)
    ap.add_argument("--rows-per-session", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hard", action="store_true", help="overlapping classes, noise and label noise")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    main(a.sessions, a.rows_per_session, a.seed, hard=a.hard, out_dir=a.out_dir)
