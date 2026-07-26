#!/usr/bin/env python3
"""Generate the dark-mode chart SVGs for the CLI benchmarks.

Matches the visual language of the existing img/*-dark.svg charts: same background,
palette, fonts, margins and label conventions. Dark mode only.

    python3 benchmarks/make_charts.py      # writes img/*-dark.svg
"""
from pathlib import Path

OUT = Path(__file__).parent.parent / "img"

BG = "#1a1a19"
FG = "#ffffff"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
FONT = "system-ui,-apple-system,Segoe UI,sans-serif"

# Arm colours are fixed across every chart in this repo.
C = {"none": "#3987e5", "dense": "#d95926", "caveman": "#199e70", "ponytail": "#c98500"}
# Role colours for composition charts.
R = {"file": "#3987e5", "other": "#199e70", "prose": "#c98500"}

W = 780
PLOT_L = 118      # left edge of plot area on horizontal-bar charts
PLOT_R = 756


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def txt(x, y, s, size=10, weight=400, fill=MUTED, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'dominant-baseline="middle">{esc(s)}</text>')


def head(w, h, title, legend=None):
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}" role="img">',
         f'<rect width="{w}" height="{h}" fill="{BG}"/>',
         txt(16, 20, title, 13, 600, FG)]
    if legend:
        x = 16
        for label, colour in legend:
            p.append(f'<rect x="{x}" y="35" width="10" height="10" rx="2" fill="{colour}"/>')
            p.append(txt(x + 16, 40, label, 10, 400, MUTED))
            x += max(96, 26 + len(label) * 6)
    return p


def fmt(n):
    return f"{n:,.0f}"


def hbars(path, title, rows, series, unit="", pct=False, note=None, row_h=None, label_w=118):
    """Horizontal grouped bars. rows = [(label, {series_key: value})]."""
    keys = [k for k, _ in series]
    L = label_w
    bar_h = 11
    gap = 3
    group = len(keys) * (bar_h + gap) + 13
    row_h = row_h or group
    top = 62
    h = top + len(rows) * row_h + (34 if note else 18)
    vmax = max(abs(v) for _, d in rows for v in d.values()) or 1
    step = 10 ** (len(str(int(vmax))) - 1)
    while vmax / step > 6:
        step *= 2
    ticks = [t for t in range(0, int(vmax + step), int(step))]
    scale = (PLOT_R - L) / (ticks[-1] or 1)

    p = head(W, h, title, series)
    for t in ticks:
        x = L + t * scale
        p.append(f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{top + len(rows) * row_h - 8}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        lab = f"{t / 1000:g}k" if t >= 1000 and not pct else (f"{t}%" if pct else str(t))
        p.append(txt(x, top + len(rows) * row_h + 2, lab, 10, 400, MUTED, "middle"))
    p.append(f'<line x1="{L}" y1="{top - 8}" x2="{L}" y2="{top + len(rows) * row_h - 8}" '
             f'stroke="{AXIS}" stroke-width="1"/>')

    for i, (label, d) in enumerate(rows):
        y0 = top + i * row_h
        bold = 600 if label.lower().startswith(("average", "mean")) else 400
        p.append(txt(L - 10, y0 + (len(keys) * (bar_h + gap)) / 2 - 2, label, 10, bold,
                     FG if bold == 600 else MUTED, "end"))
        for j, k in enumerate(keys):
            v = d.get(k)
            if v is None:
                continue
            y = y0 + j * (bar_h + gap)
            wdt = max(1.0, abs(v) * scale)
            p.append(f'<rect x="{L}" y="{y:.1f}" width="{wdt:.1f}" height="{bar_h}" rx="2" '
                     f'fill="{dict(series)[k]}"/>')
            lab = f"{abs(v):.0f}%" if pct else fmt(v)
            p.append(txt(L + wdt + 5, y + bar_h / 2, lab + unit, 9, bold, MUTED))
    if note:
        p.append(txt(16, h - 14, note, 10, 400, MUTED))
    p.append("</svg>")
    OUT.joinpath(path).write_text("".join(p))
    return path


def vbars(path, title, items, note=None, h=267):
    """Vertical bars: items = [(label, value, colour)]."""
    top, base = 62, h - 61
    vmax = max(v for _, v, _ in items) or 1
    step = 10 ** (len(str(int(vmax))) - 1)
    while vmax / step > 6:
        step *= 2
    ticks = list(range(0, int(vmax + step), int(step)))
    scale = (base - top) / (ticks[-1] or 1)
    p = head(W, h, title)
    for t in ticks:
        y = base - t * scale
        p.append(f'<line x1="56" y1="{y:.1f}" x2="{PLOT_R}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(txt(48, y, f"{t:,}", 10, 400, MUTED, "end"))
    slot = (PLOT_R - 56) / len(items)
    bw = min(90, slot * 0.5)
    for i, (label, v, colour) in enumerate(items):
        cx = 56 + slot * (i + 0.5)
        bh = max(1.0, v * scale)
        p.append(f'<rect x="{cx - bw / 2:.1f}" y="{base - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                 f'rx="2" fill="{colour}"/>')
        p.append(txt(cx, base - bh - 10, fmt(v), 11, 600, FG, "middle"))
        p.append(txt(cx, base + 14, label, 10, 400, MUTED, "middle"))
    if note:
        p.append(txt(16, h - 16, note, 10, 400, MUTED))
    p.append("</svg>")
    OUT.joinpath(path).write_text("".join(p))
    return path


def stacked(path, title, rows, parts, note=None):
    """Stacked horizontal bars, normalised to % of row total.

    parts = [(data_key, legend_label, colour)]
    """
    top, row_h, bar_h = 62, 54, 22
    h = top + len(rows) * row_h + (36 if note else 20)
    p = head(W, h, title, [(lbl, col) for _, lbl, col in parts])
    span = PLOT_R - PLOT_L
    for i, (label, d) in enumerate(rows):
        y = top + i * row_h
        total = sum(d.values()) or 1
        p.append(txt(PLOT_L - 10, y + bar_h / 2, label, 11, 600, FG, "end"))
        x = PLOT_L
        for k, _lbl, colour in parts:
            frac = d.get(k, 0) / total
            wdt = span * frac
            if wdt > 0.4:
                p.append(f'<rect x="{x:.1f}" y="{y}" width="{wdt:.1f}" height="{bar_h}" fill="{colour}"/>')
            if frac >= 0.06:
                p.append(txt(x + wdt / 2, y + bar_h / 2, f"{frac * 100:.0f}%", 10, 600, BG, "middle"))
            x += wdt
        small = ", ".join(f"{lbl} {d[k] / total * 100:.2f}%"
                          for k, lbl, _c in parts if d.get(k, 0) / total < 0.06)
        p.append(txt(PLOT_L, y + bar_h + 13, small, 9, 400, MUTED))
    if note:
        p.append(txt(16, h - 14, note, 10, 400, MUTED))
    p.append("</svg>")
    OUT.joinpath(path).write_text("".join(p))
    return path


# ---------------------------------------------------------------- chat benchmark
CHAT = [
    ("react-rerender", 1191, 204, 394), ("auth-middleware-fix", 2978, 342, 387),
    ("postgres-pool", 3264, 594, 984), ("git-rebase-merge", 1322, 225, 595),
    ("async-refactor", 757, 172, 287), ("microservices-monolith", 2103, 420, 1074),
    ("pr-security-review", 1642, 382, 619), ("docker-multi-stage", 2390, 340, 1009),
    ("race-condition-debug", 1677, 260, 664), ("error-boundary", 2190, 441, 1023),
]
ARMS3 = [("none", C["none"]), ("dense", C["dense"]), ("caveman", C["caveman"])]

made = []
made.append(hbars(
    "chat-tokens-by-task-dark.svg",
    "Chat prompts — output tokens per answer (median of 3, opus-5)",
    [(n, {"none": a, "dense": b, "caveman": c}) for n, a, b, c in CHAT]
    + [("Average", {"none": 1951, "dense": 338, "caveman": 704})],
    ARMS3, label_w=168, note="Caveman's own 10-prompt suite. Control arm verified free of skill contamination."))

made.append(hbars(
    "chat-savings-dark.svg",
    "Chat prompts — output-token reduction vs the no-skill control",
    [(n, {"dense": round((1 - b / a) * 100), "caveman": round((1 - c / a) * 100)})
     for n, a, b, c in CHAT]
    + [("Average", {"dense": 82, "caveman": 62})],
    [("dense", C["dense"]), ("caveman", C["caveman"])], pct=True, label_w=168,
    note="DENSE compresses more than caveman on all 10 prompts."))

made.append(vbars(
    "chat-variance-dark.svg",
    "Run-to-run spread on identical prompts (mean max−min across 3 trials)",
    [("none", 605, C["none"]), ("dense", 73, C["dense"]), ("caveman", 153, C["caveman"])],
    note="Output tokens. The uncompressed arm is ~8x noisier than DENSE."))

# ------------------------------------------------------------- agentic benchmark
made.append(hbars(
    "agentic-runs-dark.svg",
    "Agentic build — output tokens per run (21-requirement engine, opus-5)",
    [("none-1", {"none": 50217}), ("none-2", {"none": 66413}), ("none-3", {"none": 62620}),
     ("none-4", {"none": 50421}), ("dense-1", {"dense": 44514}), ("dense-2", {"dense": 49076}),
     ("dense-3", {"dense": 48584}), ("dense-4", {"dense": 43553}),
     ("mean none", {"none": 57418}), ("mean dense", {"dense": 46432})],
    [("none", C["none"]), ("dense", C["dense"])], row_h=30,
    note="All 8 runs passed all 21 hidden requirements. −19.1%, t = −2.50."))

made.append(stacked(
    "agentic-composition-dark.svg",
    "Agentic build — what the model actually emitted, by kind",
    [("none", {"file": 329541, "other": 25046, "prose": 3543}),
     ("dense", {"file": 238690, "other": 53169, "prose": 1509})],
    [("file", "file edits (Write/Edit)", R["file"]), ("other", "other tool payload", R["other"]),
     ("prose", "prose", R["prose"])],
    note="Characters emitted across 4 runs per arm. Prose is ~1% — there is almost no narration to compress."))

made.append(hbars(
    "agentic-toolmix-dark.svg",
    "Agentic build — tool calls per arm (4 runs each)",
    [("Edit", {"none": 205, "dense": 168}), ("Bash", {"none": 109, "dense": 116}),
     ("Read", {"none": 24, "dense": 14}), ("Write", {"none": 10, "dense": 8})],
    [("none", C["none"]), ("dense", C["dense"])], row_h=34,
    note="Write fires ~2x per run, Edit ~42-51x: composed in a few planned writes, then patched."))

# ------------------------------------------------------------------ headline chart
made.append(hbars(
    "effect-by-task-shape-dark.svg",
    "DENSE output-token reduction by task shape",
    [("chat Q&A  ~100% prose", {"output tokens saved": 82}),
     ("coding tasks  (6-model validation)", {"output tokens saved": 55}),
     ("agentic build  ~1% prose", {"output tokens saved": 19})],
    [("output tokens saved", C["dense"])], pct=True, row_h=44, label_w=232,
    note="Separate runs, different models and controls. Validation arm shown at the midpoint of its −47%..−63% range."))

print("wrote:", *made, sep="\n  ")
