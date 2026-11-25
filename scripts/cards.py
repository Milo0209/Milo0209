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
.grade { animation: grade 20s ease-in-out infinite; }
.blob { animation: drift 14s ease-in-out infinite alternate; }
.blob2 { animation: drift 18s ease-in-out infinite alternate-reverse; }
@keyframes grade { 0%, 100% { filter: hue-rotate(-40deg); } 50% { filter: hue-rotate(45deg); } }
@keyframes drift { to { transform: translate(60px, 18px); } }
.seg { transform-box: fill-box; transform-origin: 0 50%;
       animation: grow .9s cubic-bezier(.2,.8,.2,1) backwards; }
.leg { animation: rise .6s ease-out backwards; }
.shine { fill: url(#sh); transform-box: fill-box; animation: sweep 1.5s ease-in-out 1.5s backwards; }
@keyframes sweep { from { transform: translateX(0); } to { transform: translateX(1100px); } }
@keyframes grow { from { transform: scaleX(0); } }
@keyframes rise { from { opacity: 0; transform: translateY(5px); } }
@keyframes draw { to { stroke-dashoffset: 0; } }
@keyframes fade { to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .spark { animation: none; stroke-dashoffset: 0; }
  .area, .dot { animation: none; opacity: 1; }
  .seg, .leg, .shine, .grade, .blob, .blob2 { animation: none; }
}
"""


def _frame(w: int, h: int, rx: int = 10) -> str:
    """Shared card look: base, dot grid, drifting colour blobs with slow hue 'grading', border."""
    return (
        f'<rect class="card" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" style="stroke:none"/>'
        f'<defs><clipPath id="hc"><rect width="{w}" height="{h}" rx="{rx}"/></clipPath>'
        '<radialGradient id="b1"><stop offset="0" style="stop-color:var(--title)" stop-opacity=".30"/>'
        '<stop offset="1" style="stop-color:var(--title)" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="b2"><stop offset="0" style="stop-color:var(--accent)" stop-opacity=".26"/>'
        '<stop offset="1" style="stop-color:var(--accent)" stop-opacity="0"/></radialGradient>'
        '<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        '<circle cx="2" cy="2" r="1" style="fill:var(--grid)"/></pattern></defs>'
        f'<g clip-path="url(#hc)"><rect width="{w}" height="{h}" fill="url(#dots)"/>'
        f'<g class="grade"><circle class="blob" cx="{w * 0.17:.0f}" cy="{h * 0.15:.0f}" r="{max(h, w * 0.22):.0f}" fill="url(#b1)"/>'
        f'<circle class="blob2" cx="{w * 0.82:.0f}" cy="{h * 0.95:.0f}" r="{max(h, w * 0.24):.0f}" fill="url(#b2)"/></g></g>'
        f'<rect class="card" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" style="fill:none"/>'
    )


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
{_frame(W, H)}
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
    """data must already be validated (validate_loc). Cumulative lines added (deleted lines are intentionally not shown)."""
    tot = data["total"]
    weeks = []
    if data["weekly"]:  # continuous weekly axis (empty weeks keep the line flat)
        wk, last = date.fromisoformat(min(data["weekly"])), date.fromisoformat(data["updated"])
        while wk <= last:
            weeks.append(wk.isoformat())
            wk += timedelta(days=7)
    pre, weeks = weeks[:-26], weeks[-26:]  # graph window: last 26 weeks, totals stay all-time
    ca = sum(data["weekly"].get(w, [0, 0])[0] for w in pre)
    add_s = []
    for wk in weeks:
        ca += data["weekly"].get(wk, [0, 0])[0]
        add_s.append(ca)
    if len(add_s) < 2:  # a line needs at least two points
        add_s = [0] + (add_s or [0])
    top = max(add_s[-1], 1)  # window may start above 0 (pre-window total)
    x0, y0, w, h = 25, 128, 445, 48
    n = len(add_s)

    def path(vals):
        pts = [(x0 + w * i / (n - 1), y0 + h - h * v / top) for i, v in enumerate(vals)]
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), pts[-1]

    l_add, (ax, ay) = path(add_s)
    area = f"{l_add} L{x0 + w},{y0 + h} L{x0},{y0 + h} Z"
    rows = [("Repositories", str(data["repos"])), ("Commits", str(data["commits"])),
            ("Since", data["since"][:7])]
    rows_svg = "".join(
        f'<text class="lbl" x="300" y="{66 + i * 17}">{k}</text>'
        f'<text class="val" x="470" y="{66 + i * 17}" text-anchor="end">{v}</text>'
        for i, (k, v) in enumerate(rows)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Lines of code: {fmt(tot['added'])} added">
<title>Lines of code across my repositories</title>
{_style(force)}
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="var(--line)" stop-opacity=".28"/><stop offset="1" stop-color="var(--line)" stop-opacity="0"/>
</linearGradient></defs>
{_frame(W, H)}
<text class="title" x="25" y="33">Lines of Code · all repositories</text>
<text class="big" x="25" y="82">+{fmt(tot['added'])}</text>
<text class="lbl" x="25" y="102">lines added</text>
{rows_svg}
<line class="grid" x1="25" y1="{y0 + h}" x2="470" y2="{y0 + h}"/>
<path class="area" d="{area}"/>
<path class="spark" d="{l_add}"/>
<circle class="dot" cx="{ax:.1f}" cy="{ay:.1f}" r="3.5"/>
<text class="tiny" x="25" y="196">cumulative lines added · last 26 weeks · forks &amp; dependencies excluded</text>
<text class="tiny" x="470" y="196" text-anchor="end">{data['updated']}</text>
</svg>
"""


LANG_COLORS = {
    "TypeScript": "#3b82f6", "Python": "#ffd43b", "JavaScript": "#f0883e", "Shell": "#56d364",
    "HTML": "#f85149", "CSS": "#a371f7", "SQL": "#2dd4bf", "Swift": "#ff7eb6", "Java": "#d29922",
    "Kotlin": "#bc8cff", "Go": "#00ADD8", "Rust": "#dea584", "C": "#8b949e", "C++": "#f34b7d",
    "C#": "#3fb950", "Ruby": "#CC342D", "PHP": "#7a86b8", "Dart": "#00B4AB", "Lua": "#4d6bff",
    "Other": "#6e7681",
}
LW, LH = 990, 205


def render_languages_card(data: dict, force: str | None = None) -> str:
    """Wide card: share of lines added per language. data must be validated."""
    langs = data.get("languages", {})
    total = sum(langs.values())
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    top, rest = ranked[:6], sum(v for _, v in ranked[6:])
    if rest:
        top.append(("Other", rest))
    if not total:
        top = [("Other", 1)]
        total = 1
    shares = [(k, v, 100.0 * v / total) for k, v in top]

    def pct(p: float) -> str:
        return f"{p:.0f}%" if p >= 10 else f"{p:.1f}%"

    x0, bw, by, bh, gap = 30, 930, 112, 14, 2
    segs, x = [], float(x0)
    usable = bw - gap * (len(shares) - 1)
    for i, (k, v, p) in enumerate(shares):
        w = max(usable * p / 100, 4)
        segs.append(
            f'<rect class="seg" x="{x:.1f}" y="{by}" width="{w:.1f}" height="{bh}" '
            f'fill="{LANG_COLORS.get(k, LANG_COLORS["Other"])}" style="animation-delay:{i * 0.12:.2f}s"/>'
        )
        x += w + gap
    n = len(shares)
    colw = bw / n
    legend = []
    for i, (k, v, p) in enumerate(shares):
        cx = x0 + colw * i
        col = LANG_COLORS.get(k, LANG_COLORS["Other"])
        legend.append(
            f'<g class="leg" style="animation-delay:{0.5 + i * 0.1:.2f}s">'
            f'<circle cx="{cx + 5:.1f}" cy="153" r="5" fill="{col}"/>'
            f'<text class="lbl" x="{cx + 17:.1f}" y="157">{k.replace("&", "&amp;")}</text>'
            f'<text class="val" x="{cx + 17:.1f}" y="176" style="font-size:15px">{pct(p)}</text></g>'
        )
    lead_k, _, lead_p = shares[0]
    lead_col = LANG_COLORS.get(lead_k, LANG_COLORS["Other"])
    n_lang = len(langs)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{LW}" height="{LH}" viewBox="0 0 {LW} {LH}" role="img" aria-label="Most used language: {lead_k} with {pct(lead_p)} of lines written">
<title>Programming languages by lines written</title>
{_style(force)}
{_frame(LW, LH)}
<text class="title" x="30" y="36">Languages · by lines written</text>
<text class="tiny" x="960" y="36" text-anchor="end">{n_lang} languages · {fmt(total if langs else 0)} lines</text>
<text class="big" x="30" y="86" style="fill:{lead_col}">{pct(lead_p)}</text>
<text class="lbl" x="{30 + 24 + 20 * len(pct(lead_p))}" y="86" style="font-size:15px">of my code is <tspan class="val" style="font-size:15px">{lead_k.replace("&", "&amp;")}</tspan></text>
<defs>
<clipPath id="bar"><rect x="{x0}" y="{by}" width="{bw}" height="{bh}" rx="7"/></clipPath>
<linearGradient id="sh" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<g clip-path="url(#bar)">{"".join(segs)}<rect class="shine" x="-140" y="{by}" width="120" height="{bh}"/></g>
{"".join(legend)}
<text class="tiny" x="30" y="197">lines added per language · forks &amp; dependencies excluded</text>
<text class="tiny" x="960" y="197" text-anchor="end">{data['updated']}</text>
</svg>
"""


HW, HH = 990, 230


def render_header_card(force: str | None = None) -> str:
    """Static profile banner (no data, no external resources). Animated via CSS only."""
    chips = [("Data Science", 118, "#3b82f6"), ("AI", 52, "#a371f7"), ("Cyber Security", 128, "#2dd4bf")]
    chip_svg, cx = [], 40
    for i, (label, w, col) in enumerate(chips):
        chip_svg.append(
            f'<g class="leg" style="animation-delay:{0.9 + i * 0.12:.2f}s">'
            f'<rect x="{cx}" y="172" width="{w}" height="28" rx="14" fill="{col}" fill-opacity=".14" stroke="{col}" stroke-opacity=".55"/>'
            f'<circle cx="{cx + 14}" cy="186" r="3.5" fill="{col}"/>'
            f'<text class="lbl" x="{cx + 24}" y="190" style="font-size:12px;font-weight:600">{label}</text></g>'
        )
        cx += w + 12
    mono = "font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;"
    lines = [
        (0.4, '<tspan style="fill:var(--accent)">$</tspan> whoami'),
        (0.9, "emilio — student, builder"),
        (1.5, '<tspan style="fill:var(--accent)">$</tspan> ./now'),
        (2.0, "bots · pipelines · security"),
    ]
    term = "".join(
        f'<text class="leg" x="600" y="{96 + i * 24}" style="{mono}font-size:13px;fill:var(--text);animation-delay:{d}s">{t}</text>'
        for i, (d, t) in enumerate(lines)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{HW}" height="{HH}" viewBox="0 0 {HW} {HH}" role="img" aria-label="Emilio – Computer Science student. Data Science, AI, Cyber Security.">
<title>Emilio – Computer Science student</title>
{_style(force)}
<style>
.cursor {{ animation: blink 1s steps(1) infinite; }}
.name {{ fill: url(#tg); font-size: 54px; font-weight: 800; letter-spacing: -1px; }}
.sub {{ font-size: 17px; fill: var(--text); }}
.tag {{ font-size: 13px; fill: var(--muted); }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .cursor {{ animation: none; }} }}
</style>
<defs><linearGradient id="tg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:var(--title)"/><stop offset="1" style="stop-color:var(--num)"/></linearGradient></defs>
{_frame(HW, HH, 12)}
<text class="tag" x="42" y="52">Hi, I'm</text>
<g class="grade"><text class="name leg" x="38" y="104" style="animation-delay:.1s">Emilio</text></g>
<text class="sub leg" x="42" y="134" style="animation-delay:.4s">Computer Science student @ Fontys Venlo</text>
<text class="tag leg" x="42" y="156" style="animation-delay:.6s">I build systems that run 24/7 and learn from their own data.</text>
{"".join(chip_svg)}
<rect x="570" y="38" width="380" height="172" rx="10" class="card" style="fill:var(--bg);fill-opacity:.72"/>
<circle cx="590" cy="56" r="4.5" fill="#f85149"/><circle cx="606" cy="56" r="4.5" fill="#f0b429"/><circle cx="622" cy="56" r="4.5" fill="#56d364"/>
<line class="grid" x1="570" y1="72" x2="950" y2="72"/>
{term}
<text class="cursor" x="600" y="192" style="{mono}font-size:13px;fill:var(--num)">▌</text>
</svg>
"""


AW, AH = 990, 235


def render_activity_card(data: dict, force: str | None = None) -> str:
    """Commit heatmap, last 53 weeks (Mon-Sun rows). data must be validated."""
    act = data.get("activity", {})
    end = date.fromisoformat(data["updated"])
    first = min((date.fromisoformat(k) for k in act), default=end)
    nweeks = max(36, min(53, (end - first).days // 7 + 5))  # grows with history, 36..53 weeks
    start = end - timedelta(days=end.weekday()) - timedelta(weeks=nweeks - 1)
    win = [(start + timedelta(days=i)) for i in range((end - start).days + 1)]
    counts = {d: act.get(d.isoformat(), 0) for d in win}
    total, active, best = sum(counts.values()), sum(1 for v in counts.values() if v), max(counts.values() or [0])
    streak, d = 0, end
    if counts.get(d, 0) == 0:
        d -= timedelta(days=1)  # today may still be empty
    while counts.get(d, 0) > 0:
        streak += 1
        d -= timedelta(days=1)

    pitch = min(19, 880 // nweeks)
    cell = pitch - 3
    x0, y0 = (AW - nweeks * pitch) // 2 + 20, 62

    def level(n: int) -> int:
        if n <= 0:
            return 0
        return min(4, 1 + int(3 * (n / max(best, 1)) ** 0.5))  # sqrt scale: 1 commit stays visible

    cells, months, last_m = [], [], None
    for d in win:
        col, row = (d - start).days // 7, d.weekday()
        x, y = x0 + col * pitch, y0 + row * pitch
        lv = level(counts[d])
        delay = f"{col * 0.018 + row * 0.01:.3f}"
        extra = ' stroke="var(--accent)" stroke-width="1.6" class="c today"' if d == end else ' class="c"'
        cells.append(
            f'<rect{extra} x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{"var(--grid)" if lv == 0 else "var(--num)"}" fill-opacity="{[0.7, 0.28, 0.5, 0.75, 1][lv]}" '
            f'style="animation-delay:{delay}s"/>'
        )
        if row == 0 and d.day <= 7 and (d.year, d.month) != last_m:
            months.append(f'<text class="tiny" x="{x}" y="{y0 - 8}">{d.strftime("%b")}</text>')
            last_m = (d.year, d.month)
    days_lbl = "".join(
        f'<text class="tiny" x="{x0 - 34}" y="{y0 + i * pitch + cell - 2}">{n}</text>'
        for i, n in ((0, "Mon"), (2, "Wed"), (4, "Fri"))
    )
    lx = 735
    legend = "".join(
        f'<rect x="{lx + 38 + i * 18}" y="205" width="13" height="13" rx="3" '
        f'fill="{"var(--grid)" if i == 0 else "var(--num)"}" fill-opacity="{[0.7, 0.28, 0.5, 0.75, 1][i]}"/>'
        for i in range(5)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{AW}" height="{AH}" viewBox="0 0 {AW} {AH}" role="img" aria-label="Commit activity: {total} commits in the last {nweeks} weeks, {active} active days">
<title>Commit activity</title>
{_style(force)}
<style>
.c {{ animation: pop .5s ease-out backwards; }}
.today {{ animation: pop .5s ease-out backwards, ring 2.4s ease-in-out 1.4s infinite; }}
@keyframes pop {{ from {{ opacity: 0; transform: scale(.4); }} }}
@keyframes ring {{ 50% {{ stroke-opacity: .25; }} }}
.c {{ transform-box: fill-box; transform-origin: center; }}
@media (prefers-reduced-motion: reduce) {{ .c, .today {{ animation: none; }} }}
</style>
{_frame(AW, AH)}
<text class="title" x="30" y="36">Activity · commits per day</text>
<text class="val" x="960" y="36" text-anchor="end"><tspan style="fill:var(--num);font-size:15px">{total}</tspan> commits · <tspan style="fill:var(--num);font-size:15px">{active}</tspan> active days · <tspan style="fill:var(--num);font-size:15px">{streak}</tspan>-day streak</text>
{"".join(months)}{days_lbl}
{"".join(cells)}
<text class="tiny" x="30" y="215">last {nweeks} weeks · private repositories included, names never shown · updated {data['updated']}</text>
<text class="tiny" x="{lx}" y="215">Less</text>{legend}<text class="tiny" x="{lx + 38 + 5 * 18 + 4}" y="215">More</text>
</svg>
"""


# ---------------------------------------------------------------------------
# Static design assets (no data): section titles, project cards, workflow,
# security tiles, footer, LinkedIn pill. Same look: dot grid, colour blobs,
# slow hue "grading", staggered entrances. Pure CSS animation, no scripts.
# ---------------------------------------------------------------------------
import textwrap  # noqa: E402

MONO = "font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;"
_EXTRA = f"""<style>
.h2 {{ font-size: 26px; font-weight: 800; letter-spacing: -.5px; fill: url(#tg); }}
.sweep {{ animation: sweepx 4.5s ease-in-out infinite; }}
@keyframes sweepx {{ from {{ transform: translateX(-300px); }} to {{ transform: translateX(1100px); }} }}
.flow {{ stroke-dasharray: 3 9; animation: flow 1.4s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -24; }} }}
.travel {{ animation: travel 7s ease-in-out infinite; }}
@keyframes travel {{ from {{ transform: translateX(0); }} to {{ transform: translateX(790px); }} }}
.ping {{ transform-box: fill-box; transform-origin: center; animation: ping 3.2s ease-out infinite backwards; }}
@keyframes ping {{ 0% {{ transform: scale(1); opacity: .7; }} 70%, 100% {{ transform: scale(2.2); opacity: 0; }} }}
.pulse {{ transform-box: fill-box; transform-origin: center; animation: pulse 3s ease-in-out infinite; }}
@keyframes pulse {{ 50% {{ transform: scale(1.12); }} }}
@media (prefers-reduced-motion: reduce) {{ .sweep, .flow, .travel, .ping, .pulse {{ animation: none; }} }}
</style>
<defs><linearGradient id="tg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:var(--title)"/><stop offset="1" style="stop-color:var(--num)"/></linearGradient>
<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:var(--num)" stop-opacity="0"/><stop offset=".5" style="stop-color:var(--num)" stop-opacity="1"/><stop offset="1" style="stop-color:var(--num)" stop-opacity="0"/></linearGradient></defs>"""


def _svg(w: int, h: int, body: str, label: str, force: str | None, rx: int = 10, frame: bool = True) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}">'
        f"<title>{label}</title>{_style(force)}{_EXTRA}"
        f'{_frame(w, h, rx) if frame else ""}{body}</svg>\n'
    )


def render_section(title: str, sub: str, force: str | None = None) -> str:
    body = (
        '<g class="grade"><rect class="leg" x="22" y="16" width="6" height="34" rx="3" style="fill:url(#tg);animation-delay:.1s"/></g>'
        f'<text class="h2 leg" x="42" y="38" style="animation-delay:.2s">{title}</text>'
        f'<text class="tiny leg" x="42" y="56" style="animation-delay:.4s">{sub}</text>'
        '<g clip-path="url(#sc)"><rect class="sweep" x="0" y="68" width="260" height="2" fill="url(#beam)"/></g>'
        '<defs><clipPath id="sc"><rect x="0" y="66" width="990" height="4"/></clipPath></defs>'
    )
    return _svg(990, 72, body, title, force, rx=12)


ICONS = {  # 24x24 line icons
    "chart": '<path d="M3 17l5-6 4 3 8-10" /><path d="M3 21h18" /><circle cx="20" cy="4" r="1.6"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5.5 9.5A2 2 0 006.3 21h11.4a2 2 0 001.8-2.5L14 9V3"/><path d="M7.5 15h9"/>',
    "film": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M10 9l5 3-5 3z"/><path d="M3 9h2M3 15h2M19 9h2M19 15h2"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
    "pin": '<path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z"/><path d="M12 14v7"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "sigma": '<path d="M18 5H6l6 7-6 7h12"/>',
}


def _icon(name: str, x: float, y: float, size: float, col: str = "var(--title)") -> str:
    k = size / 24
    return (f'<g transform="translate({x} {y}) scale({k:.3f})" fill="none" stroke="{col}" '
            f'stroke-width="{1.7:.2f}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')


def render_project_card(name: str, desc: str, tags: list[str], status: str, icon: str,
                        force: str | None = None) -> str:
    w, h = 320, 236
    lines = textwrap.wrap(desc, 38)[:4]
    desc_svg = "".join(
        f'<text class="lbl leg" x="24" y="{128 + i * 18}" style="animation-delay:{0.5 + i * 0.1:.2f}s">{ln}</text>'
        for i, ln in enumerate(lines)
    )
    tx, tag_svg = 24, []
    for i, t in enumerate(tags):
        tw = int(len(t) * 6.3 + 22)
        tag_svg.append(
            f'<g class="leg" style="animation-delay:{0.9 + i * 0.1:.2f}s"><rect x="{tx}" y="200" width="{tw}" height="22" rx="11" '
            f'style="fill:var(--title);fill-opacity:.12;stroke:var(--title);stroke-opacity:.45"/>'
            f'<text class="tiny" x="{tx + tw / 2:.0f}" y="215" text-anchor="middle" style="fill:var(--text);font-size:10.5px">{t}</text></g>'
        )
        tx += tw + 8
    sw = int(len(status) * 6.4 + 24)
    body = (
        f'<g class="grade"><rect class="pulse" x="24" y="24" width="48" height="48" rx="13" style="fill:var(--title);fill-opacity:.14;stroke:var(--title);stroke-opacity:.5"/></g>'
        f'{_icon(icon, 36, 36, 24)}'
        f'<rect x="{w - 24 - sw}" y="30" width="{sw}" height="22" rx="11" style="fill:var(--num);fill-opacity:.14;stroke:var(--num);stroke-opacity:.5"/>'
        f'<circle class="ping" cx="{w - 24 - sw + 12}" cy="41" r="3" style="fill:var(--num)"/><circle cx="{w - 24 - sw + 12}" cy="41" r="3" style="fill:var(--num)"/>'
        f'<text class="tiny" x="{w - 24 - sw + 21}" y="45" style="fill:var(--text);font-size:10.5px">{status}</text>'
        f'<text class="leg" x="24" y="104" style="{MONO}font-size:17px;font-weight:700;fill:var(--title);animation-delay:.3s">{name}</text>'
        f'{desc_svg}{"".join(tag_svg)}'
        f'<g clip-path="url(#cb)"><rect class="sweep" x="0" y="{h - 3}" width="200" height="3" fill="url(#beam)"/></g>'
        f'<defs><clipPath id="cb"><rect x="0" y="{h - 4}" width="{w}" height="4"/></clipPath></defs>'
    )
    return _svg(w, h, body, f"Project {name}: {desc}", force)


STEPS = [
    ("Spec first", "write it down before code"),
    ("Staged delivery", "small, shippable slices"),
    ("Tests as gate", "tests + benchmarks must pass"),
    ("Deploy over SSH", "auto-rollback on failure"),
    ("Observable", "everything reports to my phone"),
]


def render_workflow(force: str | None = None) -> str:
    w, h, y = 990, 150, 58
    xs = [100 + i * 197.5 for i in range(5)]
    nodes = []
    for i, (t, s_) in enumerate(STEPS):
        x = xs[i]
        nodes.append(
            f'<g class="leg" style="animation-delay:{0.2 + i * 0.15:.2f}s">'
            f'<circle class="ping" cx="{x}" cy="{y}" r="15" style="fill:none;stroke:var(--title);animation-delay:{i * 1.2:.1f}s"/>'
            f'<circle cx="{x}" cy="{y}" r="15" style="fill:var(--bg);stroke:var(--title);stroke-width:1.6"/>'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" style="{MONO}font-size:13px;font-weight:700;fill:var(--num)">{i + 1}</text>'
            f'<text class="val" x="{x}" y="{y + 44}" text-anchor="middle" style="font-size:14px">{t}</text>'
            f'<text class="tiny" x="{x}" y="{y + 62}" text-anchor="middle">{s_}</text></g>'
        )
    body = (
        f'<line class="flow" x1="{xs[0]}" y1="{y}" x2="{xs[-1]}" y2="{y}" style="stroke:var(--muted);stroke-width:2;stroke-linecap:round;opacity:.6"/>'
        f'<g class="grade"><circle class="travel" cx="{xs[0]}" cy="{y}" r="5" style="fill:var(--num)"/>'
        f'<circle class="travel" cx="{xs[0]}" cy="{y}" r="11" style="fill:var(--num);fill-opacity:.25"/></g>'
        + "".join(nodes)
    )
    return _svg(w, h, body, "How I work: spec first, staged delivery, tests as gate, deploy over SSH with auto-rollback, observable", force)


TILES = [
    ("key", "Least privilege", "scoped, read-only tokens"),
    ("pin", "Pinned CI", "actions locked to hashes"),
    ("shield", "No secrets in code", "env & secret stores only"),
    ("sigma", "Sums only", "only aggregates are public"),
]


def render_security(force: str | None = None) -> str:
    w, h = 990, 150
    tw, gap = 228, 12
    tiles = []
    for i, (ic, t, s_) in enumerate(TILES):
        x = 24 + i * (tw + gap)
        tiles.append(
            f'<g class="leg" style="animation-delay:{0.2 + i * 0.15:.2f}s">'
            f'<rect x="{x}" y="22" width="{tw}" height="106" rx="12" style="fill:var(--bg);fill-opacity:.72;stroke:var(--border)"/>'
            f'<g class="grade"><circle class="pulse" cx="{x + 38}" cy="62" r="20" style="fill:var(--num);fill-opacity:.14;stroke:var(--num);stroke-opacity:.5;animation-delay:{i * .5:.1f}s"/></g>'
            f'{_icon(ic, x + 26, 50, 24, "var(--num)")}'
            f'<text class="val" x="{x + 70}" y="58" style="font-size:14px">{t}</text>'
            f'<text class="tiny" x="{x + 70}" y="76">{s_}</text>'
            f'<line class="grid" x1="{x + 18}" y1="98" x2="{x + tw - 18}" y2="98"/>'
            f'<rect x="{x + 18}" y="104" width="{tw - 36}" height="3" rx="1.5" style="fill:var(--num);fill-opacity:.35"/></g>'
        )
    return _svg(w, h, "".join(tiles), "Security mindset: least privilege, pinned CI, no secrets in code, only sums published", force)


def render_footer(force: str | None = None) -> str:
    w, h = 990, 96
    body = (
        '<g class="grade"><circle class="ping" cx="495" cy="30" r="5" style="fill:var(--num)"/><circle cx="495" cy="30" r="5" style="fill:var(--num)"/></g>'
        '<text class="val leg" x="495" y="60" text-anchor="middle" style="font-size:15px;animation-delay:.3s">Private by default – if you want to know more, get in touch.</text>'
        '<text class="tiny leg" x="495" y="80" text-anchor="middle" style="animation-delay:.6s">stats update themselves · Python + GitHub Actions · only sums are published</text>'
    )
    return _svg(w, h, body, "Private by default – if you want to know more, get in touch.", force, rx=12)


def render_linkedin(force: str | None = None) -> str:
    w, h = 230, 46
    body = (
        '<defs><clipPath id="lp"><rect x="1" y="1" width="228" height="44" rx="22"/></clipPath></defs>'
        '<rect x="1" y="1" width="228" height="44" rx="22" class="card" style="stroke:none"/>'
        '<rect x="1" y="1" width="228" height="44" rx="22" style="fill:var(--title);fill-opacity:.12;stroke:var(--title);stroke-opacity:.6"/>'
        '<g clip-path="url(#lp)"><rect class="sweep" x="0" y="0" width="90" height="46" fill="url(#beam)" fill-opacity=".35"/></g>'
        '<text class="val" x="115" y="28" text-anchor="middle" style="font-size:14px;fill:var(--title)">Connect on LinkedIn  ↗</text>'
    )
    return _svg(w, h, body, "Connect on LinkedIn", force, rx=22, frame=False)


PROJECTS = [
    ("signal-scanner", "24/7 scanner that scores live market data from 0 to 100 and alerts in real time. "
     "Strategy variants compete in paper trading.", ["24/7", "scoring", "paper trading"], "paper mode", "chart"),
    ("strategy-research-lab", "Cost-aware idea finder: 100 competing strategy variants, a dashboard and a "
     "strict paper-first release gate.", ["748 tests", "100 variants"], "in development", "flask"),
    ("explainer-video-pipeline", "Automated pipeline for short vertical videos: React scenes, local speech "
     "synthesis and recognition, procedural music.", ["zero cloud cost", "local TTS"], "first reel shipped", "film"),
]
