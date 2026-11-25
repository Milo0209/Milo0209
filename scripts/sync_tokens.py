#!/usr/bin/env python3
"""Claude Code SessionEnd hook: count tokens, publish only the sums.

Layout (created by install step, NOT pulled from GitHub):
  ~/.claude-profile-stats/app/    pinned local copy of scripts/ + config/  <- code that runs
  ~/.claude-profile-stats/repo/   dedicated clone of the profile repo       <- data only
  ~/.claude-profile-stats/ledger-<machine>.json                              <- local ledger

Safety properties
- Never executes code from the cloned repo (a hijacked GitHub account cannot run
  code on this machine through this hook).
- Commits only data/tokens.json + assets/tokens.svg, by explicit path, after the
  allow-list validator passed. Anything else in the working tree aborts.
- Commit identity is the GitHub noreply address (no private e-mail in history).
- Throttled (>= 30 min between pushes), non-blocking lock, hard timeouts, and it
  ALWAYS exits 0 so it can never break or delay a Claude Code session.
- Log (sync.log) contains only sums and generic status words.
"""
from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home() / ".claude-profile-stats"
APP, REPO = HOME / "app", HOME / "repo"
STAMP, LOG, LOCK = HOME / "last_push", HOME / "sync.log", HOME / "lock"
MIN_INTERVAL = 30 * 60
ALLOWED = {"data/tokens.json", "assets/tokens.svg"}
IDENT = ["-c", "user.name=Milo0209", "-c", "user.email=217570049+Milo0209@users.noreply.github.com"]
ENV = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "SSH_AUTH_SOCK")}
ENV["GIT_TERMINAL_PROMPT"] = "0"


def log(msg: str) -> None:
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def run(cmd: list[str], timeout: int, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=ENV, timeout=timeout, capture_output=True, text=True, **kw)


def git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(REPO), *IDENT, *args], timeout)


def main() -> None:
    HOME.mkdir(mode=0o700, exist_ok=True)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    if not (APP / "scripts" / "tokens.py").exists() or not (REPO / ".git").exists():
        log("not installed")
        return

    if git("pull", "--ff-only", "--quiet").returncode != 0:
        log("pull failed")
        return

    t = run([sys.executable, "-I", str(APP / "scripts" / "tokens.py"),
             "--data", str(REPO / "data" / "tokens.json"),
             "--svg-dir", str(REPO / "assets")], 120)
    if t.returncode != 0:
        log("count failed")
        return
    log(t.stdout.strip().splitlines()[-1] if t.stdout.strip() else "counted")  # sums only

    if run([sys.executable, "-I", str(APP / "scripts" / "validate.py"), str(REPO)], 30).returncode != 0:
        git("checkout", "--", "data", "assets")
        log("validation failed - reverted")
        return

    changed = {ln[3:].strip() for ln in git("status", "--porcelain", "--untracked-files=all").stdout.splitlines()}
    if not changed:
        return
    if not changed <= ALLOWED:
        git("checkout", "--", "data", "assets")
        log("unexpected files changed - aborted")
        return
    if STAMP.exists() and time.time() - STAMP.stat().st_mtime < MIN_INTERVAL:
        return  # next session end will publish; data is already in the local ledger

    git("add", *sorted(changed))
    if git("commit", "--quiet", "-m", "chore: update token stats").returncode != 0:
        log("commit failed")
        return
    if git("push", "--quiet", timeout=60).returncode != 0:
        git("reset", "--hard", "origin/main")
        log("push failed")
        return
    STAMP.touch()
    log("pushed")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
