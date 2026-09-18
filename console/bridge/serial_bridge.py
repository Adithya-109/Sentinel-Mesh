"""Gateway serial bridge: USB serial <-> console API (contracts/CONTRACT.md).

Reads one message per line at 115200 baud:
    EVT <Event JSON>   -> POST :8000/events
    TRC <Trace JSON>   -> POST :8000/traces  (appended to a trace file if recording)
    LOG <text>         -> ignored, echoed with -v

Writes back:
    LABEL <normal|weak_link|replay|flood|impersonation>

The bridge holds no state of its own: it polls GET /recording and sends a
LABEL line whenever `label_version` changes, so the operator sets the label in
the UI and the gateway hears about it. That keeps one writer on the serial
port and one owner of the trace files (the API).

Three input sources, so the demo never depends on hardware being alive:
    --port COM5        a real gateway
    --replay FILE      a recorded serial log, at wall-clock pace (--speed to hurry)
    --stdin            a pipe, e.g. `python tools/mock_serial.py | ... --stdin`
"""
import argparse
import json
import sys
import time

import requests

# 127.0.0.1, never "localhost": on Windows "localhost" tries ::1 first and costs
# ~2s per request before falling back to IPv4. The bridge makes one request per
# serial line, so that would put it minutes behind a live gateway.
DEFAULT_CONSOLE = "http://127.0.0.1:8000"

# One session, so the bridge reuses the TCP connection instead of reopening it
# for every EVT/TRC line.
HTTP = requests.Session()


class Stats:
    def __init__(self):
        self.evt = self.trc = self.log = self.bad = self.rejected = 0

    def line(self) -> str:
        return (f"EVT {self.evt}  TRC {self.trc}  LOG {self.log}  "
                f"unparseable {self.bad}  rejected {self.rejected}")


def post(console_url: str, path: str, payload: dict, timeout: float = 5.0):
    try:
        return HTTP.post(f"{console_url}{path}", json=payload, timeout=timeout)
    except requests.RequestException as exc:
        print(f"  ! console unreachable ({exc.__class__.__name__}); dropped", file=sys.stderr)
        return None


def handle_line(line: str, console_url: str, stats: Stats, verbose: bool) -> None:
    line = line.strip()
    if not line:
        return
    kind, _, rest = line.partition(" ")

    if kind == "LOG":
        stats.log += 1
        if verbose:
            print(f"  LOG {rest}")
        return

    if kind not in ("EVT", "TRC"):
        stats.bad += 1
        if verbose:
            print(f"  ? unrecognised line: {line[:80]}", file=sys.stderr)
        return

    try:
        payload = json.loads(rest)
    except json.JSONDecodeError as exc:
        stats.bad += 1
        print(f"  ! {kind} line is not JSON ({exc}); dropped", file=sys.stderr)
        return

    if kind == "EVT":
        stats.evt += 1
        r = post(console_url, "/events", payload)
        if r is not None and r.status_code == 422:
            stats.rejected += 1
            print(f"  ! gateway EVT rejected by the contract schema: "
                  f"{r.json().get('errors')}", file=sys.stderr)
        elif verbose and r is not None:
            print(f"  EVT {payload.get('type')} -> {r.status_code}")
    else:
        stats.trc += 1
        r = post(console_url, "/traces", payload)
        if r is not None and r.status_code == 422:
            stats.rejected += 1
            print(f"  ! gateway TRC rejected: {r.json().get('errors')}", file=sys.stderr)
        elif verbose and r is not None:
            body = r.json() if r.content else {}
            print(f"  TRC stored={body.get('stored')} label={body.get('label')}")


def poll_label(console_url: str, state: dict, write) -> None:
    """Send `LABEL <x>` when the UI changes the recording label."""
    try:
        r = HTTP.get(f"{console_url}/recording", timeout=2)
        rec = r.json()
    except (requests.RequestException, ValueError):
        return
    version = rec.get("label_version")
    if version != state.get("label_version"):
        state["label_version"] = version
        label = rec.get("label", "normal")
        if write is not None:
            write(f"LABEL {label}\n")
        print(f"  -> LABEL {label}")


def run_serial(args, stats: Stats) -> None:
    import serial  # imported here so --replay/--stdin work without pyserial

    print(f"opening {args.port} at {args.baud} baud")
    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        state: dict = {}

        def write(text: str):
            ser.write(text.encode("ascii"))

        last_poll = 0.0
        while True:
            raw = ser.readline()
            if raw:
                handle_line(raw.decode("utf-8", errors="replace"), args.console, stats, args.verbose)
            now = time.monotonic()
            if now - last_poll >= args.label_poll:
                last_poll = now
                poll_label(args.console, state, write)


def run_stream(lines, args, stats: Stats, paced: bool) -> None:
    """Replay a log or a pipe. `paced` honours the leading timestamp if present."""
    state: dict = {}
    last_poll = 0.0
    prev_ts = None
    for raw in lines:
        # a replay log may carry a `+<ms> ` prefix recording the original gap
        if paced and raw.startswith("+"):
            gap, _, raw = raw.partition(" ")
            try:
                delay = int(gap[1:]) / 1000.0 / max(args.speed, 0.01)
                if prev_ts is not None and delay > 0:
                    time.sleep(min(delay, 10))
                prev_ts = True
            except ValueError:
                pass
        handle_line(raw, args.console, stats, args.verbose)
        now = time.monotonic()
        if now - last_poll >= args.label_poll:
            last_poll = now
            poll_label(args.console, state, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="serial port, e.g. COM5 or /dev/ttyUSB0")
    src.add_argument("--replay", help="a recorded serial log to replay (hardware fallback)")
    src.add_argument("--stdin", action="store_true", help="read lines from stdin")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--console", default=DEFAULT_CONSOLE)
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed multiplier")
    ap.add_argument("--label-poll", type=float, default=2.0, help="seconds between /recording polls")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    stats = Stats()
    try:
        if args.port:
            run_serial(args, stats)
        elif args.replay:
            with open(args.replay, encoding="utf-8") as f:
                run_stream(f, args, stats, paced=True)
        else:
            run_stream(sys.stdin, args, stats, paced=True)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\nbridge stopped -- {stats.line()}")


if __name__ == "__main__":
    main()
