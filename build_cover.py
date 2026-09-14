#!/usr/bin/env python3
"""
build_cover.py - render PepsTracker's Facebook page cover (fb-cover.png).

Facebook shows a page cover at 820x312 on desktop, crops the sides on mobile,
and overlaps the page's profile picture onto the bottom-left (desktop) or
bottom-centre (mobile). So the canvas is rendered at 2x (1640x624) and every
piece of text is kept inside the region that survives both crops:

    text safe box   x 180..1460, y 40..380
    desktop avatar  x 0..430,   y 380..624   (left clear of text)
    mobile avatar   x 620..1020, y 400..624  (left clear of text)

The index sparkline deliberately occupies the lower-left band: it is the one
element that can be partly covered by the avatar without losing meaning, and
it fades out before the right-hand readout block.

Every number is read from what the site already publishes - the catalogue in
index.html, the published api/v1/summary.json, and price-history.json - so the
cover can never claim something the site does not. Run after build_api.py.
"""
import json
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import numpy as np
from matplotlib import patheffects as pe
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "pepstracker_fixed")
OUT = os.path.join(SITE, "fb-cover.png")

W, H = 1640, 624
BG = "#07090f"
BLUE = "#3b9eff"
GREEN = "#4de87a"
GOLD = "#f5c842"
TEAL = "#00e5cc"
TEXT = "#e8edf5"
MUTED = "#93a6c0"
DIM = "#5a6a82"
RULE = "#1b2739"

# ---------------------------------------------------------------- fonts
# Explicit files beat family lookup: Lato ships its heavy cuts under the same
# family name, so asking for family="Lato", weight="black" silently returns
# the regular cut (or falls back to DejaVu) depending on the box.
_CANDIDATES = {
    "black": ["/usr/share/fonts/truetype/lato/Lato-Black.ttf",
              "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "bold": ["/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "semi": ["/usr/share/fonts/truetype/lato/Lato-Semibold.ttf",
             "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "reg": ["/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "mono": ["/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"],
    "monor": ["/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
}
_FILES = {}
for _k, _paths in _CANDIDATES.items():
    _FILES[_k] = next((p for p in _paths if os.path.exists(p)), None)
    if _FILES[_k] is None:
        print("note: no font file for %r; using matplotlib default" % _k)


def fp(kind, size):
    path = _FILES.get(kind)
    if path:
        return fm.FontProperties(fname=path, size=size)
    weight = "bold" if kind in ("black", "bold", "semi", "mono") else "normal"
    family = "monospace" if kind.startswith("mono") else "sans-serif"
    return fm.FontProperties(family=family, weight=weight, size=size)


# ---------------------------------------------------------------- data
def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def index_series():
    """Base-100 per compound at its first day, forward-filled, daily median.

    Identical method to the /price-index page, so the line on the cover is the
    same line the site publishes.
    """
    hist = json.loads(read(os.path.join(SITE, "price-history.json")))
    series = hist.get("series") or {}
    days = sorted({p["d"] for pts in series.values() for p in pts if p.get("d")})
    cols = []
    for pts in series.values():
        if not pts or len(pts) < 10:
            continue
        by_day = {p["d"]: p.get("mg") for p in pts if p.get("d")}
        base = by_day.get(pts[0]["d"])
        if not isinstance(base, (int, float)) or base <= 0:
            continue
        last, col = None, []
        for d in days:
            v = by_day.get(d)
            if isinstance(v, (int, float)) and v > 0:
                last = v
            col.append(None if last is None else (last / base) * 100.0)
        cols.append(col)
    out, kept = [], []
    for i, d in enumerate(days):
        vals = sorted(c[i] for c in cols if c[i] is not None)
        if not vals:
            continue
        n = len(vals) // 2
        out.append(vals[n] if len(vals) % 2 else (vals[n - 1] + vals[n]) / 2.0)
        kept.append(d)
    return kept, out


def stats():
    """Counts straight from the published API, with a live fallback."""
    p = os.path.join(SITE, "api", "v1", "summary.json")
    if os.path.exists(p):
        s = json.loads(read(p))
        return s.get("vendors"), s.get("compounds"), s.get("listings")
    import re
    src = read(os.path.join(SITE, "index.html"))
    seg = src[src.find("const VENDORS"):]
    seg = seg[:seg.find("];")]
    nv = len(set(re.findall(r'id\s*:\s*"([^"]+)"', seg)))
    sys.path.insert(0, ROOT)
    from sync_site_counts import compound_names
    return nv, len(set(compound_names(src))), None


MONTHS = ("January February March April May June July August September "
          "October November December").split()


# ---------------------------------------------------------------- helpers
def px(x, y):
    """Pixel coords -> figure fraction, y measured from the top."""
    return x / W, 1.0 - y / H


def text(fig, x, y, s, kind, size, color, ha="left", va="baseline",
         spacing=0.0, alpha=1.0, zorder=12):
    """Text at pixel coords. `spacing` is tracking in px (matplotlib has none)."""
    if spacing:
        # draw glyph by glyph so tracking is exact at any size
        canvas = FigureCanvasAgg(fig)
        rend = fig.canvas.get_renderer()
        props = fp(kind, size)
        widths = []
        for ch in s:
            t = fig.text(0, -5, ch, fontproperties=props)
            widths.append(t.get_window_extent(rend).width)
            t.remove()
        total = sum(widths) + spacing * (len(s) - 1)
        if ha == "center":
            cx = x - total / 2.0
        elif ha == "right":
            cx = x - total
        else:
            cx = x
        for ch, w in zip(s, widths):
            fx, fy = px(cx, y)
            fig.text(fx, fy, ch, fontproperties=props, color=color, ha="left",
                     va=va, alpha=alpha, zorder=zorder,
                     transform=fig.transFigure)
            cx += w + spacing
        return total
    fx, fy = px(x, y)
    t = fig.text(fx, fy, s, fontproperties=fp(kind, size), color=color, ha=ha,
                 va=va, alpha=alpha, zorder=zorder, transform=fig.transFigure)
    return t


def measure(fig, s, kind, size):
    FigureCanvasAgg(fig)
    rend = fig.canvas.get_renderer()
    t = fig.text(0, -5, s, fontproperties=fp(kind, size))
    w = t.get_window_extent(rend).width
    t.remove()
    return w


def rule(fig, x1, x2, y, color=RULE, lw=1.2, alpha=1.0):
    fig.add_artist(Line2D([x1 / W, x2 / W], [1 - y / H, 1 - y / H],
                          transform=fig.transFigure, color=color, lw=lw,
                          alpha=alpha, zorder=11))


def vrule(fig, x, y1, y2, color=RULE, lw=1.2):
    fig.add_artist(Line2D([x / W, x / W], [1 - y1 / H, 1 - y2 / H],
                          transform=fig.transFigure, color=color, lw=lw,
                          zorder=11))


def logo(fig, left, top, size):
    """The site's own mark, drawn from its SVG geometry.

    Uses a dedicated equal-aspect axes so the circles stay circles - drawing in
    figure-fraction coordinates squashes them by the 2.6:1 canvas ratio.
    """
    ax = fig.add_axes([left / W, 1 - (top + size) / H, size / W, size / H],
                      zorder=14)
    ax.set_xlim(0, 200)
    ax.set_ylim(200, 0)          # SVG y-down
    ax.set_aspect("equal")
    ax.axis("off")
    ax.patch.set_alpha(0)
    lw = size * 0.052            # SVG stroke-width 10 at 200 units

    t = np.linspace(0, 1, 80)
    bx = (1 - t) ** 2 * 20 + 2 * (1 - t) * t * 100 + t ** 2 * 180
    by = (1 - t) ** 2 * 140 + 2 * (1 - t) * t * 195 + t ** 2 * 120
    ax.plot(bx, by, color=BLUE, lw=lw, solid_capstyle="round", alpha=.9,
            zorder=2)
    for (x1, y1), (x2, y2), c in (((20, 128), (82, 82), BLUE),
                                  ((82, 82), (128, 105), TEAL),
                                  ((128, 105), (168, 48), GREEN)):
        ax.plot([x1, x2], [y1, y2], color=c, lw=lw, solid_capstyle="round",
                zorder=3)
    ax.add_patch(Polygon([(178, 38), (152, 46), (168, 64)], closed=True,
                         facecolor=GREEN, edgecolor="none", zorder=4))
    for (x, y), c in (((20, 128), BLUE), ((82, 82), TEAL), ((128, 105), GREEN)):
        ax.add_patch(Circle((x, y), 18, facecolor=c, edgecolor="none",
                            zorder=5))


# ---------------------------------------------------------------- build
def build():
    days, idx = index_series()
    nv, nc, nl = stats()
    latest = idx[-1] if idx else None
    change = (latest - 100.0) if latest is not None else None

    fig = Figure(figsize=(W / 100.0, H / 100.0), dpi=100)
    FigureCanvasAgg(fig)
    fig.patch.set_facecolor(BG)

    # ---- faint terminal grid -------------------------------------------
    for gx in range(0, W + 1, 82):
        fig.add_artist(Line2D([gx / W, gx / W], [0, 1],
                              transform=fig.transFigure, color="#ffffff",
                              lw=.6, alpha=.02, zorder=1))
    for gy in range(0, H + 1, 78):
        fig.add_artist(Line2D([0, 1], [1 - gy / H, 1 - gy / H],
                              transform=fig.transFigure, color="#ffffff",
                              lw=.6, alpha=.02, zorder=1))

    # ---- index sparkline, lower-left band -------------------------------
    # Ends at x=1120 so the readout block on the right sits on clean
    # background; the left end is where the profile picture lands.
    if len(idx) > 2:
        band_l, band_r, band_t, band_b = 0, 1120, 408, 596
        ax = fig.add_axes([band_l / W, 1 - band_b / H,
                           (band_r - band_l) / W, (band_b - band_t) / H],
                          zorder=3)
        ax.axis("off")
        ax.patch.set_alpha(0)
        ax.set_xlim(-0.6, len(idx) - 1 + 1.8)   # room for the end marker
        lo, hi = min(idx), max(idx)
        span = max(hi - lo, 1.0)
        ax.set_ylim(lo - span * .45, hi + span * .30)
        xs = np.arange(len(idx))
        ys = np.array(idx, dtype=float)

        # Area fill: a horizontal alpha ramp clipped to the area under the
        # curve. Painting a scrim rectangle over the top instead would leave a
        # visible seam and swallow the tail of the line.
        ylo = lo - span * .45
        band = ax.fill_between(xs, ys, ylo, facecolor="none", edgecolor="none",
                               linewidth=0, zorder=2)
        ramp = np.linspace(0, 1, 256).reshape(1, -1)
        im = ax.imshow(ramp, aspect="auto", origin="lower", zorder=2,
                       extent=[0, len(idx) - 1, ylo, hi + span * .30],
                       cmap=LinearSegmentedColormap.from_list(
                           "g", [(0.0, to_rgba(GREEN, .17)),
                                 (0.74, to_rgba(GREEN, .14)),
                                 (1.0, to_rgba(GREEN, 0))]))
        im.set_clip_path(band.get_paths()[0], transform=ax.transData)

        ax.plot(xs, ys, color=GREEN, lw=3.0, solid_capstyle="round",
                solid_joinstyle="round", zorder=4, alpha=.95,
                path_effects=[pe.Stroke(linewidth=10, foreground=GREEN,
                                        alpha=.13), pe.Normal()])
        ax.plot([xs[-1]], [ys[-1]], "o", ms=9, mfc=GREEN, mec=BG, mew=3,
                zorder=5)

    # ---- top accent bar -------------------------------------------------
    bar = fig.add_axes([0, 1 - 9 / H, 1, 9 / H], zorder=25)
    bar.imshow([[0, .5, 1]], aspect="auto",
               cmap=LinearSegmentedColormap.from_list("a", [BLUE, GREEN, GOLD]))
    bar.axis("off")

    # ---- brand block ----------------------------------------------------
    cx = W / 2.0
    wm_size = 76
    w_peps = measure(fig, "Peps", "black", wm_size)
    w_trac = measure(fig, "Tracker", "black", wm_size)
    mark = 104
    gap = 26
    total = mark + gap + w_peps + w_trac
    x0 = cx - total / 2.0
    logo(fig, x0, 78, mark)
    tx = x0 + mark + gap
    text(fig, tx, 162, "Peps", "black", wm_size, BLUE)
    text(fig, tx + w_peps, 162, "Tracker", "black", wm_size, GREEN)

    text(fig, cx, 212, "LIVE RESEARCH PEPTIDE PRICE COMPARISON · UPDATED EVERY DAY",
         "semi", 15, MUTED, ha="center", spacing=2.4, alpha=.95)
    rule(fig, cx - 250, cx + 250, 244)

    # ---- stat rail ------------------------------------------------------
    cells = [(str(nv), "VENDORS", BLUE), (str(nc), "COMPOUNDS", GREEN)]
    if nl:
        cells.append((f"{nl:,}", "LIVE LISTINGS", TEXT))
    cells.append(("FREE", "ALWAYS", GOLD))

    step = 262
    start = cx - step * (len(cells) - 1) / 2.0
    for i, (val, lab, col) in enumerate(cells):
        x = start + i * step
        text(fig, x, 322, val, "mono", 38, col, ha="center")
        text(fig, x, 352, lab, "bold", 12, DIM, ha="center", spacing=2.2)
        if i:
            vrule(fig, x - step / 2.0, 296, 340)

    # ---- readout block, right (clear of both avatar zones) --------------
    rx = 1412
    if latest is not None:
        text(fig, rx, 452, "PEPS INDEX", "bold", 13, DIM, ha="right",
             spacing=2.4)
        val = f"{latest:.1f}"
        w_val = measure(fig, val, "mono", 52)
        arrow = "▼" if change < 0 else "▲"
        col = GREEN if change < 0 else "#ff5c5c"
        text(fig, rx, 508, val, "mono", 52, TEXT, ha="right")
        text(fig, rx - w_val - 16, 505, f"{arrow} {abs(change):.1f}%",
             "mono", 21, col, ha="right")
        m = int(days[0][5:7])
        text(fig, rx, 540, "since %s %d" % (MONTHS[m - 1], int(days[0][:4])),
             "reg", 14, DIM, ha="right")

    rule(fig, rx - 250, rx, 566, color="#22324a")
    text(fig, rx, 598, "pepstracker.com", "black", 24, TEXT, ha="right")

    fig.savefig(OUT, dpi=100, facecolor=BG)

    # matplotlib can land a pixel short of the requested figsize, and saves
    # RGBA. Facebook is happier with an exact, flat RGB image.
    try:
        from PIL import Image
        im = Image.open(OUT)
        if im.mode != "RGB" or im.size != (W, H):
            im = im.convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            im.save(OUT, "PNG", optimize=True)
    except ImportError:
        print("note: Pillow missing; skipped the exact-size/RGB pass")

    size = ""
    try:
        from PIL import Image
        size = " %dx%d" % Image.open(OUT).size
    except Exception:
        pass
    print("wrote %s%s: %s vendors, %s compounds, %s listings, index %s"
          % (OUT, size, nv, nc, nl, ("%.1f" % latest) if latest else "n/a"))


if __name__ == "__main__":
    build()
