"""Shared helpers: strict validation and atomic writes.

Security stance: everything that ends up in the public repo (JSON, SVG) goes
through an allow-list validator first. Only integers and ISO dates survive.
Free-form strings (repo names, paths, commit messages) cannot be published.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MACHINE_RE = re.compile(r"^[a-z0-9]{1,8}$")
FIELDS = ("input", "output", "cache_read", "cache_creation")
MAX_INT = 10**13  # sanity cap, far above any realistic token count


class ValidationError(ValueError):
    pass


def _int(v, what: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > MAX_INT:
        raise ValidationError(f"bad integer in {what}")
    return v


def validate_tokens(data: dict) -> dict:
    """Allow-list validation of data/tokens.json. Raises on anything unexpected."""
    if set(data) != {"schema", "updated", "since", "machines", "total"}:
        raise ValidationError("unexpected top-level keys")
    if data["schema"] != 1:
        raise ValidationError("schema")
    for k in ("updated", "since"):
        if not isinstance(data[k], str) or not DATE_RE.match(data[k]):
            raise ValidationError(k)
    if not isinstance(data["machines"], dict) or len(data["machines"]) > 8:
        raise ValidationError("machines")
    for name, m in data["machines"].items():
        if not MACHINE_RE.match(name):
            raise ValidationError("machine name")
        if set(m) != set(FIELDS) | {"daily"}:
            raise ValidationError("machine keys")
        for f in FIELDS:
            _int(m[f], f)
        if len(m["daily"]) > 5000:
            raise ValidationError("too many days")
        for day, arr in m["daily"].items():
            if not DATE_RE.match(day) or not isinstance(arr, list) or len(arr) != 4:
                raise ValidationError("daily entry")
            for x in arr:
                _int(x, "daily")
    if set(data["total"]) != set(FIELDS):
        raise ValidationError("total keys")
    for f in FIELDS:
        _int(data["total"][f], f)
    return data


def validate_loc(data: dict) -> dict:
    """Allow-list validation of data/loc.json (sums only, no repo names)."""
    if set(data) != {"schema", "updated", "since", "repos", "commits", "total", "weekly"}:
        raise ValidationError("unexpected top-level keys")
    if data["schema"] != 1:
        raise ValidationError("schema")
    for k in ("updated", "since"):
        if not isinstance(data[k], str) or not DATE_RE.match(data[k]):
            raise ValidationError(k)
    _int(data["repos"], "repos")
    _int(data["commits"], "commits")
    if set(data["total"]) != {"added", "deleted"}:
        raise ValidationError("total keys")
    _int(data["total"]["added"], "added")
    _int(data["total"]["deleted"], "deleted")
    if len(data["weekly"]) > 1000:
        raise ValidationError("too many weeks")
    for wk, arr in data["weekly"].items():
        if not DATE_RE.match(wk) or not isinstance(arr, list) or len(arr) != 2:
            raise ValidationError("weekly entry")
        _int(arr[0], "weekly")
        _int(arr[1], "weekly")
    return data


def atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
