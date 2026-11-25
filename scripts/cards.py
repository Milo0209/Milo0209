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
  .seg, .leg, .shine { animation: none; }
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
<rect class="card" x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10"/>
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
<rect class="card" x=".5" y=".5" width="{LW - 1}" height="{LH - 1}" rx="10"/>
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
.blob {{ animation: drift 14s ease-in-out infinite alternate; }}
.blob2 {{ animation: drift 18s ease-in-out infinite alternate-reverse; }}
.cursor {{ animation: blink 1s steps(1) infinite; }}
.name {{ fill: url(#tg); font-size: 54px; font-weight: 800; letter-spacing: -1px; }}
.sub {{ font-size: 17px; fill: var(--text); }}
.tag {{ font-size: 13px; fill: var(--muted); }}
@keyframes drift {{ to {{ transform: translate(60px, 18px); }} }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .blob, .blob2, .cursor {{ animation: none; }} }}
</style>
<defs>
<clipPath id="hc"><rect x="0" y="0" width="{HW}" height="{HH}" rx="12"/></clipPath>
<linearGradient id="tg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:var(--title)"/><stop offset="1" style="stop-color:var(--num)"/></linearGradient>
<radialGradient id="b1"><stop offset="0" style="stop-color:var(--title)" stop-opacity=".30"/><stop offset="1" style="stop-color:var(--title)" stop-opacity="0"/></radialGradient>
<radialGradient id="b2"><stop offset="0" style="stop-color:var(--accent)" stop-opacity=".26"/><stop offset="1" style="stop-color:var(--accent)" stop-opacity="0"/></radialGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" style="fill:var(--grid)"/></pattern>
</defs>
<g clip-path="url(#hc)">
<rect width="{HW}" height="{HH}" class="card" style="stroke:none"/>
<rect width="{HW}" height="{HH}" fill="url(#dots)"/>
<circle class="blob" cx="170" cy="40" r="200" fill="url(#b1)"/>
<circle class="blob2" cx="800" cy="210" r="220" fill="url(#b2)"/>
</g>
<rect class="card" x=".5" y=".5" width="{HW - 1}" height="{HH - 1}" rx="12" style="fill:none"/>
<text class="tag" x="42" y="52">Hi, I'm</text>
<text class="name leg" x="38" y="104" style="animation-delay:.1s">Emilio</text>
<text class="sub leg" x="42" y="134" style="animation-delay:.4s">Computer Science student @ Fontys Venlo</text>
<text class="tag leg" x="42" y="156" style="animation-delay:.6s">I build systems that run 24/7 and learn from their own data.</text>
{"".join(chip_svg)}
<rect x="570" y="38" width="380" height="154" rx="10" class="card" style="fill:var(--bg);fill-opacity:.7"/>
<circle cx="590" cy="56" r="4.5" fill="#f85149"/><circle cx="606" cy="56" r="4.5" fill="#f0b429"/><circle cx="622" cy="56" r="4.5" fill="#56d364"/>
<line class="grid" x1="570" y1="72" x2="950" y2="72"/>
{term}
<text class="cursor" x="600" y="192" style="{mono}font-size:13px;fill:var(--num)">▌</text>
</svg>
"""
