#!/usr/bin/env python3
"""Count Claude Code tokens from local session logs and publish only sums.

Reads  ~/.claude/projects/**/*.jsonl  (only: message id, requestId, usage,
timestamp - never any text/paths/prompts), de-duplicates streamed duplicates,
keeps a local ledger so sums survive Claude Code's log clean-up, and writes
data/tokens.json + assets/tokens.svg.

Stdlib only (no dependencies = no supply-chain surface). No network access.
Nothing but integers and dates is ever written to the repo files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cards import render_tokens_card  # noqa: E402
from common import (  # noqa: E402
    FIELDS, MACHINE_RE, atomic_write, dump_json, validate_tokens,
)

ROOT = Path(__file__).resolve().parent.parent
MAX_LINE = 50 * 1024 * 1024  # skip absurdly long lines (defence against odd files)


def load_config() -> dict:
    return json.loads((ROOT / "config" / "stats.config.json").read_text())


def scan(claude_dir: Path, since: str):
    """Yield (key, day, [in, out, cache_read, cache_creation]) per usage record."""
    for dirpath, dirnames, filenames in os.walk(claude_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for fn in filenames:
            if not fn.endswith(".jsonl"):
                continue
            p = os.path.join(dirpath, fn)
            if os.path.islink(p):
                continue
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if len(line) > MAX_LINE or '"usage"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    m = d.get("message") if isinstance(d, dict) else None
                    if not isinstance(m, dict) or not isinstance(m.get("usage"), dict):
                        continue
                    mid, rid, ts = m.get("id"), d.get("requestId"), d.get("timestamp")
                    if not (isinstance(mid, str) and isinstance(ts, str) and len(ts) >= 10):
                        continue
                    day = ts[:10]
                    if day < since:
                        continue
                    u = m["usage"]
                    vals = []
                    for k in ("input_tokens", "output_tokens",
                              "cache_read_input_tokens", "cache_creation_input_tokens"):
                        v = u.get(k, 0)
                        vals.append(v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10**9 else 0)
                    yield f"{mid}|{rid}", day, vals


def main() -> int:
    cfg = load_config()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--machine", default=os.environ.get("CLAUDE_STATS_MACHINE", cfg["tokens"]["default_machine"]))
    ap.add_argument("--claude-dir", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--state-dir", default=os.path.expanduser("~/.claude-profile-stats"))
    ap.add_argument("--data", default=str(ROOT / "data" / "tokens.json"))
    ap.add_argument("--svg-dir", default=str(ROOT / "assets"))
    ap.add_argument("--no-write", action="store_true", help="only print the sums")
    a = ap.parse_args()

    if not MACHINE_RE.match(a.machine):
        print("invalid machine name", file=sys.stderr)
        return 2
    since = cfg["since"]

    # 1) ledger (local only, outside the repo): key -> [day, in, out, cr, cc]
    state_dir = Path(a.state_dir)
    ledger_path = state_dir / f"ledger-{a.machine}.json"
    ledger: dict = {}
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())

    for key, day, vals in scan(Path(a.claude_dir), since):
        old = ledger.get(key)
        if old is None:
            ledger[key] = [day, *vals]
        else:  # streamed duplicates can only grow -> keep the max per field
            ledger[key] = [old[0], *(max(x, y) for x, y in zip(old[1:], vals))]

    # 2) aggregate per day
    daily: dict[str, list[int]] = {}
    for day, *vals in ledger.values():
        acc = daily.setdefault(day, [0, 0, 0, 0])
        for i, v in enumerate(vals):
            acc[i] += v
    mach = {f: sum(v[i] for v in daily.values()) for i, f in enumerate(FIELDS)}
    mach["daily"] = dict(sorted(daily.items()))

    # 3) merge into the public JSON (keeps other machines untouched)
    data_path = Path(a.data)
    machines = {}
    if data_path.exists():
        machines = json.loads(data_path.read_text()).get("machines", {})
    machines[a.machine] = mach
    total = {f: sum(m[f] for m in machines.values()) for f in FIELDS}
    out = validate_tokens({
        "schema": 1,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "since": since,
        "machines": machines,
        "total": total,
    })

    print(f"[{a.machine}] messages={len(ledger)} days={len(daily)} "
          f"input={mach['input']} output={mach['output']} "
          f"cache_read={mach['cache_read']} cache_creation={mach['cache_creation']}")
    if a.no_write:
        return 0

    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    atomic_write(ledger_path, json.dumps(ledger), mode=0o600)
    atomic_write(data_path, dump_json(out))
    svg_dir = Path(a.svg_dir)
    atomic_write(svg_dir / "tokens.svg", render_tokens_card(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
