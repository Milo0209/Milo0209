#!/usr/bin/env python3
"""Render the static banner to assets/header.svg (run manually; contains no data)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cards import render_header_card  # noqa: E402
from common import atomic_write  # noqa: E402

atomic_write(Path(__file__).resolve().parent.parent / "assets" / "header.svg", render_header_card())
