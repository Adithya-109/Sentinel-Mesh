"""Walk demo/expected.json in order, score each input against the ML
service, and POST every returned Event to the console (skipped, with a
note, if the console isn't reachable).

Usage:
    python run_demo.py [--ml-url http://127.0.0.1:8001] [--console-url http://127.0.0.1:8000]

Defaults are 127.0.0.1, not localhost: on Windows, localhost resolves to
::1 first and stalls ~2s per request before falling back to IPv4 (measured
in console/, see root CLAUDE.md) -- every other default in this repo is
already 127.0.0.1, this file was the one holdout.

Run build_all.py and build_demo_fixtures.py first.
"""
import argparse
import json
import os

import requests

HERE = os.path.dirname(os.path.abspath(__file__))


def resolve_path(p):
    if os.path.isabs(p) or (len(p) > 1 and p[1] == ":"):
        return p
    return os.path.normpath(os.path.join(HERE, p))


def post_to_console(console_url, event, state):
    """POST one Event to the console. `state['up']` is None until the first
    attempt; after that, False disables further attempts for this run.
    Something merely listening on :8000 (e.g. an unrelated dev server) is
    not enough -- the contract says POST /events -> 201, so anything else
    is treated as "no real console" rather than spammed silently.
    """
    if state["up"] is False:
        return
    try:
        r = requests.post(f"{console_url}/events", json=event, timeout=2)
    except requests.RequestException as exc:
        if state["up"] is None:
            print(f"(console not reachable at {console_url}: {exc}; will score only, not post events)\n")
        state["up"] = False
        return
    if r.status_code != 201:
        if state["up"] is None:
            print(f"(something answered at {console_url} but not as the contract expects "
                  f"-- POST /events returned {r.status_code}, not 201; will score only, not post events)\n")
        state["up"] = False
        return
    state["up"] = True


def score_email_text(ml_url, text):
    r = requests.post(f"{ml_url}/score/email", json={"text": text}, timeout=30)
    r.raise_for_status()
    return r.json()


def score_file_features(ml_url, features):
    r = requests.post(f"{ml_url}/score/file", json={"features": features}, timeout=30)
    r.raise_for_status()
    return r.json()


def score_file_upload(ml_url, path):
    with open(path, "rb") as f:
        r = requests.post(f"{ml_url}/score/file", files={"file": (os.path.basename(path), f)}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-url", default="http://127.0.0.1:8001")
    ap.add_argument("--console-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    expected_path = os.path.join(HERE, "expected.json")
    if not os.path.exists(expected_path):
        raise SystemExit("demo/expected.json not found -- run build_demo_fixtures.py first")
    with open(expected_path) as f:
        entries = json.load(f)

    console_state = {"up": None}  # probed lazily on the first Event

    passed = failed = skipped = 0
    for e in entries:
        try:
            if e["type"] == "email":
                with open(resolve_path(e["path"]), encoding="utf-8") as f:
                    text = f.read()
                event = score_email_text(args.ml_url, text)
            elif e["type"] == "file_features":
                with open(resolve_path(e["path"])) as f:
                    rows = json.load(f)
                event = score_file_features(args.ml_url, rows[e["index"]])
            elif e["type"] == "file_upload":
                path = resolve_path(e["path"])
                if not os.path.exists(path):
                    print(f"[SKIP] {e['id']}: {path} not found on this machine")
                    skipped += 1
                    continue
                event = score_file_upload(args.ml_url, path)
            else:
                raise ValueError(f"unknown entry type {e['type']!r}")
        except Exception as exc:
            print(f"[ERROR] {e['id']}: {exc}")
            failed += 1
            continue

        actual_malicious = event["type"] in ("email_malicious", "email_suspicious", "file_malicious")
        ok = actual_malicious == e["expected_malicious"]
        passed += ok
        failed += not ok
        tag = "OK" if ok else "MISMATCH"
        print(f"[{tag}] {e['id']}: {e['description']} -> {event['type']} (score={event['score']})")
        post_to_console(args.console_url, event, console_state)

    print(f"\n{passed} passed, {failed} failed, {skipped} skipped ({len(entries)} total)")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
