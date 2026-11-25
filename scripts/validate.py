#!/usr/bin/env python3
"""Pre-commit safety gate (used by the Action and the local hook).

Fails (exit 1) unless
  - data/tokens.json and data/loc.json pass the allow-list validators,
  - the SVGs contain nothing executable or external,
  - no forbidden string from an optional deny-list appears anywhere published.
Optional deny-list: env STATS_DENYLIST (comma separated, e.g. private repo names).
It is only read from the environment/secret, never stored in the repo.
Output never echoes the offending text, only which check failed.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import validate_loc, validate_tokens  # noqa: E402

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
BAD_SVG = re.compile(r"<script|javascript:|onload=|onerror=|<foreignObject|<image|<use|href=|xlink:|@import|url\(\s*['\"]?https?:", re.I)
SECRET_LIKE = re.compile(r"(ghp_|gho_|github_pat_|ghs_|xox[bp]-|AKIA[0-9A-Z]{16}|-----BEGIN)")


def main() -> int:
    ok = True
    for name, fn in (("tokens", validate_tokens), ("loc", validate_loc)):
        p = ROOT / "data" / f"{name}.json"
        if p.exists():
            try:
                fn(json.loads(p.read_text()))
            except Exception:
                print(f"FAIL: data/{name}.json failed schema validation")
                ok = False
    deny = [d.strip().lower() for d in os.environ.get("STATS_DENYLIST", "").split(",") if d.strip()]
    for p in list((ROOT / "assets").glob("*.svg")) + list((ROOT / "data").glob("*.json")):
        text = p.read_text()
        if p.suffix == ".svg":
            if "<!ENTITY" in text or "<!DOCTYPE" in text:
                print(f"FAIL: {p.relative_to(ROOT)} contains a DOCTYPE/ENTITY")
                ok = False
            else:
                try:
                    ET.fromstring(text)
                except ET.ParseError:
                    print(f"FAIL: {p.relative_to(ROOT)} is not well-formed XML")
                    ok = False
        if p.suffix == ".svg" and BAD_SVG.search(text):
            print(f"FAIL: {p.relative_to(ROOT)} contains non-static SVG content")
            ok = False
        if SECRET_LIKE.search(text):
            print(f"FAIL: {p.relative_to(ROOT)} looks like it contains a secret")
            ok = False
        low = text.lower()
        if any(d in low for d in deny):
            print(f"FAIL: {p.relative_to(ROOT)} contains a deny-listed string")
            ok = False
    print("validate: OK" if ok else "validate: FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
