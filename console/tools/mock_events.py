"""Stand-in for the ML and firmware streams: replays the whole demo story.

The console must be demonstrable before MailGuard, the gateway or the boards
are wired up, so this posts the five-beat story from brief v3 section 10 --
phishing email -> malicious attachment -> replay -> impersonation -> case
opened -- straight to the console API with realistic gaps between beats.

The `reasons` strings copy the exact shapes the real detectors emit
(MailGuard: "'token' -> malicious signal (+0.123)", FileGuard:
"ImageBase=4194304 (contrib +1.234)") so the Why panel looks the same whether
an event came from here or from the real ML service.

    python tools/mock_events.py                 # full story, demo pacing
    python tools/mock_events.py --speed 10      # 10x faster, for development
    python tools/mock_events.py --dry-run       # print events, post nothing
"""
import argparse
import json
import sys
import time
import uuid

import requests

# 127.0.0.1, never "localhost" -- see console/api/config.py for the 2s-per-request
# reason on Windows.
DEFAULT_CONSOLE = "http://127.0.0.1:8000"

# (gap before this beat in seconds, event-without-id-or-ts, what the operator sees)
STORY = [
    (0, {
        "layer": "mail", "type": "email_clean", "severity": "info", "score": 0.03,
        "node": None, "technique": None,
        "summary": "Email looks clean",
        "reasons": ["'meeting' -> legit signal (-0.412)", "'attached agenda' -> legit signal (-0.287)"],
        "details": {"subject": "Re: Tuesday maintenance window", "from": "ops@grid-utility.example"},
    }, "background traffic: an ordinary email scores clean"),

    (6, {
        "layer": "field", "type": "link_degraded", "severity": "low", "score": None,
        "node": "field-1", "technique": None,
        "summary": "Field node link degraded (RSSI -81 dBm, 6.2% loss)",
        "reasons": ["rssi_mean -81.3 dBm", "loss_pct 6.2", "jitter_ms 14.8"],
        "details": {"rssi_mean": -81.3, "loss_pct": 6.2, "classified": "weak_link"},
    }, "background traffic: a genuinely weak radio link, not an attack"),

    (8, {
        "layer": "mail", "type": "email_malicious", "severity": "high", "score": 0.981,
        "node": None, "technique": "T1566.001",
        "summary": "Malicious email detected",
        "reasons": [
            "'urgent' -> malicious signal (+0.734)",
            "'verify your account' -> malicious signal (+0.618)",
            "'click numtok' -> malicious signal (+0.455)",
        ],
        "details": {"subject": "URGENT: substation access review - action required",
                    "from": "it-security@grid-utillty.example",
                    "attachment": "SCADA_access_review.exe"},
    }, "BEAT 1 -- the phishing email lands and MailGuard flags it"),

    (11, {
        "layer": "file", "type": "file_malicious", "severity": "high", "score": 0.994,
        "node": None, "technique": "T1204.002",
        "summary": "Malicious file detected",
        "reasons": [
            "ImageBase=4194304 (contrib +2.418)",
            "SectionsMaxEntropy=7.91 (contrib +1.203)",
            "ResourcesMaxEntropy=7.88 (contrib +0.874)",
        ],
        "details": {"filename": "SCADA_access_review.exe", "source": "held-out dataset row",
                    "note": "no live malware: this is a held-out feature row"},
    }, "BEAT 2 -- the attachment is blocked"),

    (9, {
        "layer": "field", "type": "replay_rejected", "severity": "medium", "score": None,
        "node": "attacker", "technique": "T1692.002",
        "summary": "Replayed reading rejected (seq 41 already seen)",
        "reasons": ["seq 41 inside the 64-bit replay window", "session timestamp 38s stale",
                    "AES-GCM tag valid but sequence reused"],
        "details": {"seq": 41, "window": 64, "peer": "field-1"},
    }, "BEAT 3a -- the attacker replays a 'normal' reading"),

    (4, {
        "layer": "field", "type": "attack_detected", "severity": "high", "score": None,
        "node": "attacker", "technique": "T1692.002",
        "summary": "Replay campaign from attacker node",
        "reasons": ["12 replayed packets in 20s", "all reusing seq 38-49", "sender locked out"],
        "details": {"kind": "replay_campaign", "count": 12, "locked_out": True},
    }, "BEAT 3b -- enough replays to call it a campaign"),

    (7, {
        "layer": "field", "type": "handshake_rejected", "severity": "high", "score": None,
        "node": "attacker", "technique": "T0830",
        "summary": "Handshake rejected: ML-DSA signature did not verify",
        "reasons": ["claimed sender field-1", "ML-DSA-44 verify failed",
                    "public key not in the provisioned set"],
        "details": {"claimed_sender": "field-1", "kem_level": 768},
    }, "BEAT 3c -- the attacker tries to impersonate the field node"),

    (3, {
        "layer": "field", "type": "attack_detected", "severity": "high", "score": None,
        "node": "attacker", "technique": "T0830",
        "summary": "Impersonation attempt: attacker claiming to be field-1",
        "reasons": ["3 signed handshakes failed verification", "same claimed sender each time",
                    "sender locked out for 60s"],
        "details": {"kind": "impersonation", "attempts": 3, "locked_out": True},
    }, "BEAT 3d -- impersonation confirmed, attacker locked out"),

    (6, {
        "layer": "tamper", "type": "case_opened", "severity": "critical", "score": None,
        "node": "field-1", "technique": None,
        "summary": "Field node case opened -- session keys wiped",
        "reasons": ["LDR 12 lux -> 840 lux in 200ms", "MPU6050 movement 1.8g",
                    "keys wiped, re-handshake started"],
        "details": {"sensor": "ldr+mpu6050", "keys_wiped": True},
    }, "BEAT 4 -- someone opens the field node's case"),

    (4, {
        "layer": "field", "type": "rekey", "severity": "info", "score": None,
        "node": "field-1", "technique": None,
        "summary": "Re-handshake complete at ML-KEM-1024",
        "reasons": ["tamper event forced a rekey", "level raised 768 -> 1024"],
        "details": {"level": 1024, "reason": "tamper"},
    }, "BEAT 4b -- the node recovers on a fresh, stronger handshake"),
]


def build(event: dict) -> dict:
    return {"id": str(uuid.uuid4()), "ts": int(time.time() * 1000), **event}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--console", default=DEFAULT_CONSOLE)
    ap.add_argument("--speed", type=float, default=1.0, help="time compression; 10 = ten times faster")
    ap.add_argument("--dry-run", action="store_true", help="print the events instead of posting them")
    ap.add_argument("--clear", action="store_true", help="DELETE /events first")
    args = ap.parse_args()

    if args.clear and not args.dry_run:
        try:
            requests.delete(f"{args.console}/events", timeout=5)
            print("cleared existing events")
        except requests.RequestException as exc:
            print(f"could not clear events: {exc}", file=sys.stderr)

    posted = 0
    for gap, template, caption in STORY:
        if gap:
            time.sleep(gap / max(args.speed, 0.01))
        event = build(template)

        if args.dry_run:
            print(f"\n# {caption}")
            print(json.dumps(event))
            posted += 1
            continue

        try:
            r = requests.post(f"{args.console}/events", json=event, timeout=5)
        except requests.RequestException as exc:
            print(f"! console unreachable: {exc}", file=sys.stderr)
            return 1
        if r.status_code == 201:
            posted += 1
            print(f"[{event['severity']:>8}] {event['layer']:<6} {event['summary']}")
            print(f"           {caption}")
        else:
            print(f"! {r.status_code} {r.text[:300]}", file=sys.stderr)

    print(f"\n{posted}/{len(STORY)} events posted. "
          f"Open the console UI -- they should be one incident.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
