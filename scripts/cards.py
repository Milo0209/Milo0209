"""SVG card renderer. Pure functions: validated numbers in, static SVG out.

The SVG contains no scripts, no external requests, no fonts to download and no
free-form text from outside: every dynamic value is an integer or a date that
went through validate_* first. Theme follows prefers-color-scheme.
"""
from __future__ import annotations

from datetime import date, timedelta

W, H = 495, 210

# Palette: dark = "tokyonight" (matches the streak card), light = GitHub-ish.
CSS_THEME = """
:root {
  --bg:#f6f8fa; --border:#d0d7de; --title:#3b6fd4; --num:#0f8f7f; --text:#57606a;
  --muted:#8c959f; --accent:#8250df; --line:#3b6fd4; --grid:#d8dee4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#1a1b27; --border:#2a2d42; --title:#70a5fd; --num:#38bdae; --text:#a9b1d6;
    --muted:#6b7394; --accent:#bf91f3; --line:#70a5fd; --grid:#2a2d42;
  }
}
"""
CSS_LIGHT = CSS_THEME.split("@media")[0]
CSS_DARK = (
    ":root {--bg:#1a1b27; --border:#2a2d42; --title:#70a5fd; --num:#38bdae; --text:#a9b1d6;"
    "--muted:#6b7394; --accent:#bf91f3; --line:#70a5fd; --grid:#2a2d42;}"
)

CSS_BASE = """
text { font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif; }
.card { fill: var(--bg); stroke: var(--border); stroke-width: 1; }
.title { font-size: 15px; font-weight: 600; fill: var(--title); }
.big { font-size: 36px; font-weight: 700; fill: var(--num); }
.lbl { font-size: 12px; fill: var(--text); }
.val { font-size: 12px; font-weight: 600; fill: var(--text); }
.tiny { font-size: 10px; fill: var(--muted); }
.spark { fill: none; stroke: var(--line); stroke-width: 2; stroke-linejoin: round;
         stroke-linecap: round; stroke-dasharray: 1000; stroke-dashoffset: 1000;
         animation: draw 1.6s ease-out forwards; }
.area { fill: url(#g); opacity: 0; animation: fade 1.2s ease-out .5s forwards; }
.dot { fill: var(--accent); opacity: 0; animation: fade .4s ease-out 1.6s forwards; }
.grid { stroke: var(--grid); stroke-width: 1; }
@keyframes draw { to { stroke-dashoffset: 0; } }
@keyframes fade { to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .spark { animation: none; stroke-dashoffset: 0; }
  .area, .dot { animation: none; opacity: 1; }
}
"""


def fmt(n: int) -> str:
    if n >= 10**9:
        return f"{n / 1e9:.2f}B"
    if n >= 10**6:
        return f"{n / 1e6:.1f}M"
    if n >= 10**3:
        return f"{n / 1e3:.1f}K"
    return str(n)


def _style(force: str | None) -> str:
    if force == "light":
        theme = CSS_LIGHT
    elif force == "dark":
        theme = CSS_DARK
    else:
        theme = CSS_THEME
    return f"<style>{theme}{CSS_BASE}</style>"


def _sparkline(values: list[int], x0: int, y0: int, w: int, h: int):
    n = len(values)
    top = max(values) or 1
    pts = [
        (x0 + (w * i / (n - 1) if n > 1 else 0), y0 + h - h * v / top)
        for i, v in enumerate(values)
    ]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{line} L{x0 + w:.1f},{y0 + h} L{x0},{y0 + h} Z"
    return line, area, pts[-1]


def render_tokens_card(data: dict, force: str | None = None) -> str:
    """data must already be validated (validate_tokens)."""
    tot = data["total"]
    io = tot["input"] + tot["output"]
    cache = tot["cache_read"] + tot["cache_creation"]
    grand = io + cache

    # last 30 days of input+output, summed over all machines
    end = date.fromisoformat(data["updated"])
    days = [(end - timedelta(days=29 - i)).isoformat() for i in range(30)]
    series = []
    for d in days:
        s = 0
        for m in data["machines"].values():
            a = m["daily"].get(d)
            if a:
                s += a[0] + a[1]
        series.append(s)
    line, area, (lx, ly) = _sparkline(series, 25, 140, 445, 36)

    machines = ""
    if len(data["machines"]) > 1:
        parts = []
        for name, m in sorted(data["machines"].items()):
            parts.append(f"{name.upper()} {fmt(m['input'] + m['output'] + m['cache_read'] + m['cache_creation'])}")
        machines = " · ".join(parts)

    rows = [
        ("Output", tot["output"]),
        ("Input", tot["input"]),
        ("Cache read", tot["cache_read"]),
        ("Cache write", tot["cache_creation"]),
    ]
    rows_svg = "".join(
        f'<text class="lbl" x="300" y="{66 + i * 17}">{label}</text>'
        f'<text class="val" x="470" y="{66 + i * 17}" text-anchor="end">{fmt(v)}</text>'
        for i, (label, v) in enumerate(rows)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Claude Code token usage: {fmt(grand)} tokens in total">
<title>Claude Code token usage</title>
{_style(force)}
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="var(--line)" stop-opacity=".28"/><stop offset="1" stop-color="var(--line)" stop-opacity="0"/>
</linearGradient></defs>
<rect class="card" x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10"/>
<text class="title" x="25" y="33">Claude Code · Tokens</text>
<text class="big" x="25" y="88">{fmt(grand)}</text>
<text class="lbl" x="25" y="108">tokens processed in total</text>
<text class="tiny" x="25" y="124">{fmt(io)} input + output · {fmt(cache)} cached</text>
{rows_svg}
<line class="grid" x1="25" y1="{176}" x2="470" y2="{176}"/>
<path class="area" d="{area}"/>
<path class="spark" d="{line}"/>
<circle class="dot" cx="{lx:.1f}" cy="{ly:.1f}" r="3.5"/>
<text class="tiny" x="25" y="196">input + output per day · last 30 days</text>
<text class="tiny" x="470" y="196" text-anchor="end">{machines + " · " if machines else ""}updated {data["updated"]}</text>
</svg>
"""


def render_loc_card(data: dict, force: str | None = None) -> str:
    """data must already be validated (validate_loc). Cumulative added vs. deleted."""
    tot = data["total"]
    weeks = []
    if data["weekly"]:  # continuous weekly axis (empty weeks keep the line flat)
        wk, last = date.fromisoformat(min(data["weekly"])), date.fromisoformat(data["updated"])
        while wk <= last:
            weeks.append(wk.isoformat())
            wk += timedelta(days=7)
    pre, weeks = weeks[:-26], weeks[-26:]  # graph window: last 26 weeks, totals stay all-time
    ca = sum(data["weekly"].get(w, [0, 0])[0] for w in pre)
    cd = sum(data["weekly"].get(w, [0, 0])[1] for w in pre)
    add_s, del_s = [], []
    for wk in weeks:
        ca += data["weekly"].get(wk, [0, 0])[0]
        cd += data["weekly"].get(wk, [0, 0])[1]
        add_s.append(ca)
        del_s.append(cd)
    if len(add_s) < 2:  # a line needs at least two points
        add_s, del_s = [0] + (add_s or [0]), [0] + (del_s or [0])
    top = max(add_s[-1], 1)  # window may start above 0 (pre-window total)
    x0, y0, w, h = 25, 128, 445, 48
    n = len(add_s)

    def path(vals):
        pts = [(x0 + w * i / (n - 1), y0 + h - h * v / top) for i, v in enumerate(vals)]
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), pts[-1]

    l_add, (ax, ay) = path(add_s)
    l_del, _ = path(del_s)
    area = f"{l_add} L{x0 + w},{y0 + h} L{x0},{y0 + h} Z"
    net = tot["added"] - tot["deleted"]
    sign = "+" if net >= 0 else "−"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Lines of code: {fmt(tot['added'])} added, {fmt(tot['deleted'])} deleted">
<title>Lines of code across my repositories</title>
{_style(force)}
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="var(--line)" stop-opacity=".28"/><stop offset="1" stop-color="var(--line)" stop-opacity="0"/>
</linearGradient></defs>
<rect class="card" x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10"/>
<text class="title" x="25" y="33">Lines of Code · all repositories</text>
<text class="big" x="25" y="82">+{fmt(tot['added'])}</text>
<text class="lbl" x="25" y="102">lines added</text>
<text class="big" x="200" y="82" style="fill:var(--accent)">−{fmt(tot['deleted'])}</text>
<text class="lbl" x="200" y="102">lines deleted</text>
<text class="val" x="470" y="62" text-anchor="end">{sign}{fmt(abs(net))}</text>
<text class="tiny" x="470" y="78" text-anchor="end">net</text>
<line class="grid" x1="25" y1="{y0 + h}" x2="470" y2="{y0 + h}"/>
<path class="area" d="{area}"/>
<path class="spark" d="{l_add}"/>
<path class="spark" d="{l_del}" style="stroke:var(--accent);animation-delay:.3s"/>
<circle class="dot" cx="{ax:.1f}" cy="{ay:.1f}" r="3.5"/>
<text class="tiny" x="25" y="196">cumulative, last 26 weeks · {data['repos']} repos · {data['commits']} commits</text>
<text class="tiny" x="470" y="196" text-anchor="end">{data['updated']}</text>
</svg>
"""
