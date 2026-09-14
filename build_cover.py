#!/usr/bin/env python3
"""
build_cover.py - render PepsTracker's Facebook page cover (fb-cover.png).

Facebook shows a page cover at 820x312 on desktop, crops the sides on mobile,
and overlaps the page's profile picture onto the bottom-left (desktop) or
bottom-centre (mobile). So the canvas is rendered at 2x (1640x624) and every
piece of text is kept inside the region that survives both crops:

    text safe box   x 180..1460, y 40..380
    desktop avatar  x 0..430,   y 380..624   (kept clear of text)
    mobile avatar   x 620..1020, y 400..624  (kept clear of text)

The index line deliberately occupies the lower band: it is the one element that
can be partly covered by the avatar without losing meaning.

Typography is Geist / Geist Mono - the same faces the site loads - fetched by
the workflow into .fonts/ so nothing binary lives in the repo.

Every number is read from what the site already publishes (api/v1/summary.json
and price-history.json), so the cover can never claim something the site does
not. Run after build_api.py.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import numpy as np
from matplotlib import patheffects as pe
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap, to_rgb, to_rgba
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "pepstracker_fixed")
FONTS = os.path.join(ROOT, ".fonts")
OUT = os.path.join(SITE, "fb-cover.png")

W, H = 1640, 624

# Deeper and cooler than the site's #07090f: on a large flat field a near-black
# with a slight blue cast reads as depth rather than as "off".
BG = "#04060b"
INK = "#f2f6fb"
BLUE = "#3b9eff"
GREEN = "#2fd977"
GREEN_WM = "#35cf74"    # wordmark green, a step down so bloom cannot clip it
TEAL = "#00e5cc"
MUTED = "#8ea3bf"
DIM = "#4e5e77"
FAINT = "#2a374b"

# ---------------------------------------------------------------- fonts
_CAND = {
    "black":  [f"{FONTS}/geist-sans/Geist-Black.ttf",
               "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "semi":   [f"{FONTS}/geist-sans/Geist-SemiBold.ttf",
               "/usr/share/fonts/truetype/lato/Lato-Semibold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "medium": [f"{FONTS}/geist-sans/Geist-Medium.ttf",
               "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "reg":    [f"{FONTS}/geist-sans/Geist-Regular.ttf",
               "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "mono":   [f"{FONTS}/geist-mono/GeistMono-Medium.ttf",
               "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
    "monosb": [f"{FONTS}/geist-mono/GeistMono-SemiBold.ttf",
               "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"],
}
_FILES = {k: next((p for p in v if os.path.exists(p)), None) for k, v in _CAND.items()}
for _k, _p in _FILES.items():
    if _p is None:
        print("note: no font file for %r - falling back to matplotlib default" % _k)
    elif not _p.startswith(FONTS):
        print("note: %r using fallback %s" % (_k, os.path.basename(_p)))


def fp(kind, size):
    path = _FILES.get(kind)
    if path:
        return fm.FontProperties(fname=path, size=size)
    bold = kind in ("black", "semi", "monosb")
    fam = "monospace" if kind.startswith("mono") else "sans-serif"
    return fm.FontProperties(family=fam, weight="bold" if bold else "normal",
                             size=size)


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


# ---------------------------------------------------------------- atmosphere
def backdrop():
    """Base plate: deep ground, soft light sources, vignette, film grain.

    Built as one float array rather than stacked translucent axes - compositing
    in one pass keeps the glows from turning milky, and a single grain pass over
    the finished plate is what stops large dark gradients from banding on
    Facebook's re-encode.
    """
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = xs / W, ys / H
    img = np.zeros((H, W, 3), np.float32)
    img[:] = np.array(to_rgb(BG), np.float32)

    def glow(cx, cy, rx, ry, color, strength, power=2.0):
        d = np.sqrt(((nx - cx) / rx) ** 2 + ((ny - cy) / ry) ** 2)
        f = np.clip(1.0 - d, 0.0, 1.0) ** power
        img[:] += f[..., None] * np.array(to_rgb(color), np.float32) * strength

    # key light behind the wordmark, cool and wide
    glow(0.50, 0.22, 0.62, 0.86, "#17518f", 0.125)
    glow(0.50, 0.17, 0.26, 0.34, "#2f8ae0", 0.050)
    # the index line's own bloom rising off the floor
    glow(0.34, 1.02, 0.95, 0.62, "#0a7a4c", 0.165, power=2.2)
    # a whisper of warmth far right so the frame is not one flat temperature
    glow(0.99, 0.62, 0.30, 0.55, "#1d3a63", 0.060)

    # vignette
    d = np.sqrt((nx - .5) ** 2 * 1.25 + (ny - .5) ** 2)
    img *= (1.0 - np.clip((d - .44) * 0.80, 0, 1) ** 2.0 * 0.38)[..., None]

    # film grain - kills banding and reads as print rather than screenshot
    rng = np.random.default_rng(7)
    img += rng.normal(0, 0.0065, (H, W, 1)).astype(np.float32)
    img += rng.normal(0, 0.0032, (H, W, 3)).astype(np.float32)
    return np.clip(img, 0, 1)


# ---------------------------------------------------------------- bloom
def bloom(path, thresh=0.62, radii=(7, 30), gains=(0.26, 0.22)):
    """Physically-shaped bloom: isolate highlights, blur, add back.

    This is the difference between "premium" and "Photoshop outer glow".
    A per-glyph stroke traces the letterform and reads as a halo/outline; real
    bloom is light spilling off bright pixels into their neighbourhood, so it
    softens with distance and never follows an edge.
    """
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        print("note: Pillow missing - skipped bloom")
        return
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a.max(axis=2)
    mask = np.clip((lum - thresh) / max(1e-6, 1.0 - thresh), 0, 1) ** 1.25
    hi = (a * mask[..., None] * 255).astype(np.uint8)
    hi_im = Image.fromarray(hi)
    out = a.copy()
    for r, g in zip(radii, gains):
        b = np.asarray(hi_im.filter(ImageFilter.GaussianBlur(r))
                       ).astype(np.float32) / 255.0
        out += b * g
    out = np.clip(out, 0, 1)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(path, "PNG",
                                                             optimize=True)


# ---------------------------------------------------------------- helpers
def px(x, y):
    return x / W, 1.0 - y / H


def text(fig, x, y, s, kind, size, color, ha="left", va="baseline",
         spacing=0.0, alpha=1.0, zorder=20):
    """Text at pixel coords. `spacing` is tracking in px (matplotlib has none)."""
    props = fp(kind, size)
    if not spacing:
        fx, fy = px(x, y)
        return fig.text(fx, fy, s, fontproperties=props, color=color, ha=ha,
                        va=va, alpha=alpha, zorder=zorder,
                        transform=fig.transFigure)
    rend = fig.canvas.get_renderer()
    widths = []
    for ch in s:
        t = fig.text(0, -5, ch, fontproperties=props)
        widths.append(t.get_window_extent(rend).width)
        t.remove()
    total = sum(widths) + spacing * (len(s) - 1)
    cx = x - total / 2.0 if ha == "center" else (x - total if ha == "right" else x)
    for ch, w in zip(s, widths):
        fx, fy = px(cx, y)
        fig.text(fx, fy, ch, fontproperties=props, color=color, ha="left",
                 va=va, alpha=alpha, zorder=zorder, transform=fig.transFigure)
        cx += w + spacing
    return total


def measure(fig, s, kind, size, spacing=0.0):
    rend = fig.canvas.get_renderer()
    t = fig.text(0, -5, s, fontproperties=fp(kind, size))
    w = t.get_window_extent(rend).width
    t.remove()
    return w + (spacing * (len(s) - 1) if spacing else 0)


def fading_rule(fig, x1, x2, y, color=FAINT, peak=1.0, h=1.4, zorder=14):
    """A hairline that fades out at both ends. Flat rules look like borders;
    fading ones look drawn."""
    n = 256
    a = np.sin(np.linspace(0, np.pi, n)) ** 1.35 * peak
    strip = np.zeros((1, n, 4), np.float32)
    strip[0, :, :3] = to_rgb(color)
    strip[0, :, 3] = a
    ax = fig.add_axes([x1 / W, 1 - y / H, (x2 - x1) / W, h / H], zorder=zorder)
    ax.imshow(strip, aspect="auto", interpolation="bilinear")
    ax.axis("off")
    ax.patch.set_alpha(0)


def logo(fig, left, top, size, zorder=22):
    """The site's own mark, drawn from its SVG geometry, with a soft bloom.

    A dedicated equal-aspect axes keeps the circles circular - drawing in
    figure-fraction coordinates squashes them by the 2.6:1 canvas ratio.
    """
    ax = fig.add_axes([left / W, 1 - (top + size) / H, size / W, size / H],
                      zorder=zorder)
    ax.set_xlim(0, 200)
    ax.set_ylim(200, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.patch.set_alpha(0)
    lw = size * 0.052
    halo = [pe.Stroke(linewidth=lw * 2.6, foreground=GREEN, alpha=.10),
            pe.Normal()]

    t = np.linspace(0, 1, 90)
    bx = (1 - t) ** 2 * 20 + 2 * (1 - t) * t * 100 + t ** 2 * 180
    by = (1 - t) ** 2 * 140 + 2 * (1 - t) * t * 195 + t ** 2 * 120
    ax.plot(bx, by, color=BLUE, lw=lw, solid_capstyle="round", alpha=.92,
            zorder=2, path_effects=halo)
    for (x1, y1), (x2, y2), c in (((20, 128), (82, 82), BLUE),
                                  ((82, 82), (128, 105), TEAL),
                                  ((128, 105), (168, 48), GREEN)):
        ax.plot([x1, x2], [y1, y2], color=c, lw=lw, solid_capstyle="round",
                zorder=3, path_effects=halo)
    ax.add_patch(Polygon([(178, 38), (152, 46), (168, 64)], closed=True,
                         facecolor=GREEN, edgecolor="none", zorder=4))
    for (x, y), c in (((20, 128), BLUE), ((82, 82), TEAL), ((128, 105), GREEN)):
        ax.add_patch(Circle((x, y), 18, facecolor=c, edgecolor="none", zorder=5))


# ---------------------------------------------------------------- build
def build():
    days, idx = index_series()
    nv, nc, nl = stats()
    latest = idx[-1] if idx else None
    change = (latest - 100.0) if latest is not None else None

    fig = Figure(figsize=(W / 100.0, H / 100.0), dpi=100)
    FigureCanvasAgg(fig)
    fig.patch.set_facecolor(BG)

    base = fig.add_axes([0, 0, 1, 1], zorder=0)
    base.imshow(backdrop(), interpolation="bilinear", aspect="auto")
    base.axis("off")

    # ---- the index line ------------------------------------------------
    if len(idx) > 2:
        band_r, band_t, band_b = W, 355, 624
        ax = fig.add_axes([0, 1 - band_b / H, band_r / W,
                           (band_b - band_t) / H], zorder=6)
        ax.axis("off")
        ax.patch.set_alpha(0)
        ax.set_xlim(-0.5, len(idx) - 1 + 0.5)
        lo, hi = min(idx), max(idx)
        span = max(hi - lo, 1.0)
        ylo, yhi = lo - span * 0.62, hi + span * .22
        ax.set_ylim(ylo, yhi)
        xs = np.arange(len(idx))
        ys = np.array(idx, float)

        # area fill: alpha ramp clipped to the curve, so the band dissolves
        # instead of ending on a hard vertical edge
        area = ax.fill_between(xs, ys, ylo, facecolor="none", edgecolor="none",
                               lw=0, zorder=2)
        ramp = np.linspace(0, 1, 512).reshape(1, -1)
        im = ax.imshow(ramp, aspect="auto", origin="lower", zorder=2,
                       extent=[0, len(idx) - 1, ylo, yhi],
                       cmap=LinearSegmentedColormap.from_list("g", [
                           (0.00, to_rgba("#18c96b", .210)),
                           (0.50, to_rgba("#16bd66", .150)),
                           (0.74, to_rgba("#0f9a5a", .070)),
                           (1.00, to_rgba("#0f9a5a", .000))]))
        im.set_clip_path(area.get_paths()[0], transform=ax.transData)

        # Wide haze, mid bloom, crisp core - each fading away across the last
        # quarter so the readout on the right sits on clean ground. A
        # LineCollection is what allows per-segment alpha; a single plot()
        # call can only take one alpha for the whole stroke.
        from matplotlib.collections import LineCollection
        pts = np.array([xs, ys]).T.reshape(-1, 1, 2)
        segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
        xf = xs[:-1] / max(1.0, len(idx) - 1.0)
        fade = np.clip((0.86 - xf) / 0.20, 0, 1) ** 1.2
        for lwid, al, col in ((22, .035, GREEN), (10, .060, GREEN),
                              (2.6, 1.00, "#7cf0a8")):
            r, g, b = to_rgb(col)
            ax.add_collection(LineCollection(
                segs, linewidths=lwid, capstyle="round", joinstyle="round",
                zorder=4 if al == 1.0 else 3,
                colors=[(r, g, b, a * al) for a in fade]))

    # ---- top hairline (a chunky gradient bar reads cheap at this size) ---
    n = 512
    strip = np.zeros((1, n, 4), np.float32)
    ramp = np.linspace(0, 1, n)
    cols = np.array([to_rgb(BLUE), to_rgb(TEAL), to_rgb(GREEN)], np.float32)
    strip[0, :, :3] = np.stack([np.interp(ramp, [0, .5, 1], cols[:, i])
                                for i in range(3)], -1)
    strip[0, :, 3] = np.clip(np.sin(ramp * np.pi) ** .55, 0, 1) * .95
    top = fig.add_axes([0, 1 - 2.4 / H, 1, 2.4 / H], zorder=30)
    top.imshow(strip, aspect="auto", interpolation="bilinear")
    top.axis("off")

    # ---- brand lockup ---------------------------------------------------
    cx = W / 2.0
    wm, track = 94, -2.2          # Geist Black wants tightening at display size
    w_peps = measure(fig, "Peps", "black", wm, track)
    w_trac = measure(fig, "Tracker", "black", wm, track)
    # No mark here on purpose: on a Facebook page the profile picture is the
    # logo and sits inches away, so repeating it crowds the wordmark for no
    # gain. The wordmark carries the brand alone and gets the whole width.
    tx = cx - (w_peps + w_trac) / 2.0
    text(fig, tx, 176, "Peps", "black", wm, INK, spacing=track)
    text(fig, tx + w_peps + track, 176, "Tracker", "black", wm, GREEN_WM,
         spacing=track)

    text(fig, cx, 220, "Research peptide prices, compared daily.",
         "medium", 18, MUTED, ha="center", alpha=.80)

    fading_rule(fig, cx - 270, cx + 270, 258, peak=.75)

    # ---- proof line: monochrome and small, not four shouting colours ----
    cells = [(str(nv), "VENDORS"), (str(nc), "COMPOUNDS")]
    if nl:
        cells.append((f"{nl:,}", "LISTINGS"))
    step = 292
    start = cx - step * (len(cells) - 1) / 2.0
    for i, (val, lab) in enumerate(cells):
        x = start + i * step
        text(fig, x, 312, val, "monosb", 26, INK, ha="center", alpha=.94)
        text(fig, x, 338, lab, "semi", 10, DIM, ha="center", spacing=2.8)

    # ---- index readout, right (clear of both avatar zones) --------------
    rx = 1412
    if latest is not None:
        text(fig, rx, 446, "PEPS INDEX", "semi", 11, DIM, ha="right",
             spacing=3.0)
        val = f"{latest:.1f}"
        w_val = measure(fig, val, "monosb", 54)
        text(fig, rx, 504, val, "monosb", 54, INK, ha="right")
        arrow = "▼" if change < 0 else "▲"
        text(fig, rx - w_val - 18, 500, f"{arrow} {abs(change):.1f}%",
             "monosb", 19, GREEN, ha="right")
        m = int(days[0][5:7])
        text(fig, rx, 534, "since %s %s" % (MONTHS[m - 1], days[0][:4]),
             "reg", 13, DIM, ha="right", alpha=.95)

    fading_rule(fig, rx - 300, rx, 566, peak=.9)
    text(fig, rx, 598, "pepstracker.com", "semi", 22, INK, ha="right",
         alpha=.96)

    fig.savefig(OUT, dpi=100, facecolor=BG)
    bloom(OUT)

    # matplotlib can land a pixel short of the requested figsize, and writes
    # RGBA; Facebook is happier with an exact, flat RGB image.
    try:
        from PIL import Image
        im = Image.open(OUT)
        if im.mode != "RGB" or im.size != (W, H):
            im = im.convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            im.save(OUT, "PNG", optimize=True)
        print("wrote %s %dx%d: %s vendors, %s compounds, %s listings, index %s"
              % (OUT, im.size[0], im.size[1], nv, nc, nl,
                 ("%.1f" % latest) if latest else "n/a"))
    except ImportError:
        print("wrote %s (Pillow missing; skipped exact-size/RGB pass)" % OUT)


if __name__ == "__main__":
    build()
