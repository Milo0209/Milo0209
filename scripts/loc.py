#!/usr/bin/env python3
"""Lines of code (added / deleted) across all my own repositories, public and private.

Why clone + `git log --numstat` instead of the stats API: the contributor-stats
API cannot exclude dependencies, lockfiles or generated files. With numstat the
exclusion rules in config/stats.config.json apply per file.

Security notes
- Token comes from the environment (GITHUB_TOKEN / .env), never from code, and is
  passed to git via GIT_CONFIG_* env vars (not on the command line, not in .git/config).
- Repos are cloned bare (no checkout => no hooks/filters run) into a temp dir that
  is deleted afterwards.
- Output is restricted to integers and dates. Repo names, paths, commit subjects
  and author data are never printed, logged or written. git's own stderr is
  swallowed because it contains repo URLs.
- If any repo fails or the total drops sharply, nothing is written.

Stdlib only. Needs: git, network access to api.github.com / github.com.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cards import render_activity_card, render_languages_card, render_loc_card  # noqa: E402
from common import atomic_write, dump_json, validate_loc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FULLNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+$")
API = "https://api.github.com"


class Fail(Exception):
    """Raised with a generic, name-free message."""


def load_env_file(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE). Does not override existing env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def api_get(url: str, token: str, retries: int = 6):
    """GET with backoff. Handles 202 (still computing) and rate limiting."""
    delay = 2.0
    for _ in range(retries):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "profile-stats",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 202:
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                return json.loads(r.read()), r.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 502, 503):
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise Fail(f"API error {e.code}") from None
        except (urllib.error.URLError, TimeoutError):
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise Fail("API unavailable after retries")


def list_repos(token: str, cfg: dict) -> list[str]:
    repos, page = [], 1
    while True:
        data, _ = api_get(
            f"{API}/user/repos?affiliation=owner&visibility=all&per_page=100&page={page}", token)
        if not data:
            break
        for r in data:
            if cfg["exclude_forks"] and r.get("fork"):
                continue
            name = r.get("full_name", "")
            if not FULLNAME_RE.match(name):
                continue
            repos.append(name)
        page += 1
    return repos


def excluded(path: str, cfg: dict) -> bool:
    parts = path.split("/")
    base = parts[-1]
    for pat in cfg["exclude_path_patterns"]:
        seg = pat.rstrip("/")
        if seg in parts[:-1]:
            return True
    return any(fnmatch.fnmatch(base, pat) for pat in cfg["exclude_file_patterns"])


def monday(d: str) -> str:
    dt = date.fromisoformat(d)
    return (dt - timedelta(days=dt.weekday())).isoformat()


def git_env(token: str) -> dict:
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR")}
    env.update({
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    return env


def author_matchers(login: str) -> tuple[set[str], re.Pattern]:
    emails = {e.strip().lower() for e in os.environ.get("STATS_AUTHOR_EMAILS", "").split(",") if e.strip()}
    noreply = re.compile(rf"^(\d+\+)?{re.escape(login.lower())}@users\.noreply\.github\.com$")
    return emails, noreply


def count_repo(full: str, token: str, since: str, cfg: dict, tmp: Path,
               emails: set[str], noreply: re.Pattern, cap: int):
    """Returns (commits, {week: [added, deleted]}) for one repo."""
    dest = tmp / "r.git"
    env = git_env(token)
    p = subprocess.run(
        ["git", "clone", "--bare", "--quiet", "--no-tags", f"https://github.com/{full}.git", str(dest)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    if p.returncode != 0:
        raise Fail("clone failed")
    try:
        proc = subprocess.run(
            ["git", "-C", str(dest), "log", "--all", "--no-merges", "--no-renames",
             f"--since={since}", "--numstat", "--format=@@%x01%ae%x01%as"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=600)
        if proc.returncode != 0:
            raise Fail("log failed")
    finally:
        shutil.rmtree(dest, ignore_errors=True)

    commits, weekly, langs, days = 0, {}, {}, {}
    ext_map = cfg.get("languages", {})
    mine, wk = False, ""
    for raw in proc.stdout.decode("utf-8", errors="ignore").splitlines():
        if raw.startswith("@@\x01"):
            _, email, day = raw.split("\x01")
            email = email.lower()
            mine = email in emails or bool(noreply.match(email))
            wk = monday(day)
            if mine:
                commits += 1
                days[day] = days.get(day, 0) + 1
            continue
        if not mine or not raw:
            continue
        parts = raw.split("\t", 2)
        if len(parts) != 3 or parts[0] == "-":  # binary
            continue
        try:
            a, d = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if excluded(parts[2], cfg) or a > cap:  # cap: huge single-file adds = generated/data
            continue
        acc = weekly.setdefault(wk, [0, 0])
        acc[0] += a
        acc[1] += d
        ext = parts[2].rsplit(".", 1)[-1].lower() if "." in parts[2].split("/")[-1] else ""
        lang = ext_map.get(ext)
        if lang:
            langs[lang] = langs.get(lang, 0) + a
    return commits, weekly, langs, days


def main() -> int:
    cfg_all = json.loads((ROOT / "config" / "stats.config.json").read_text())
    cfg = cfg_all["loc"]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=str(ROOT / "data" / "loc.json"))
    ap.add_argument("--svg-dir", default=str(ROOT / "assets"))
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--allow-decrease", action="store_true")
    a = ap.parse_args()

    load_env_file(ROOT / ".env")
    token = os.environ.get("STATS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("STATS_GITHUB_LOGIN", "Milo0209")
    if not token:
        print("no token in environment (STATS_GITHUB_TOKEN)", file=sys.stderr)
        return 2

    since = cfg_all["since"]
    emails, noreply = author_matchers(login)
    cap = cfg.get("max_added_per_file_per_commit", 20000)

    try:
        repos = list_repos(token, cfg)
        total_commits, weekly, languages, activity = 0, {}, {}, {}
        for i, full in enumerate(repos, 1):
            tmp = Path(tempfile.mkdtemp(prefix="loc-"))
            try:
                c, w, lg, dy = count_repo(full, token, since, cfg, tmp, emails, noreply, cap)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            total_commits += c
            for k, v in lg.items():
                languages[k] = languages.get(k, 0) + v
            for k, v in dy.items():
                activity[k] = activity.get(k, 0) + v
            for wk, (x, y) in w.items():
                acc = weekly.setdefault(wk, [0, 0])
                acc[0] += x
                acc[1] += y
            print(f"repo {i}/{len(repos)} ok")  # numbers only, never names
    except Fail as e:
        print(f"aborted: {e}; nothing written", file=sys.stderr)
        return 1

    added = sum(v[0] for v in weekly.values())
    deleted = sum(v[1] for v in weekly.values())
    out = validate_loc({
        "schema": 1,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "since": since,
        "repos": len(repos),
        "commits": total_commits,
        "total": {"added": added, "deleted": deleted},
        "weekly": dict(sorted(weekly.items())),
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
        "activity": dict(sorted(activity.items())[-400:]),
    })
    print(f"total: repos={len(repos)} commits={total_commits} added={added} deleted={deleted}")
    if a.no_write:
        return 0

    p = Path(a.data)
    if p.exists() and not a.allow_decrease:
        old = json.loads(p.read_text())["total"]["added"]
        if old and added < old * 0.9:
            print("aborted: total dropped by >10% (token/permission problem?); nothing written",
                  file=sys.stderr)
            return 1
    atomic_write(p, dump_json(out))
    atomic_write(Path(a.svg_dir) / "loc.svg", render_loc_card(out))
    atomic_write(Path(a.svg_dir) / "languages.svg", render_languages_card(out))
    atomic_write(Path(a.svg_dir) / "activity.svg", render_activity_card(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
