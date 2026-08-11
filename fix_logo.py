#!/usr/bin/env python3
"""
fix_logo.py — one logo everywhere.

The site was carrying four different marks in the header, so the brand changed
as a customer moved between pages:

  245 pages  simplified polyline + a single dot   (all 190 compare-*, 45 cheapest-*)
  137 pages  the real mark: 3 nodes + arrowhead
   34 pages  wordmark only, no icon at all
    5 pages  3 nodes but no arrowhead

This normalises every indexable page to the canonical mark. The <svg> tag's own
attributes (class, width, height, style) are preserved so each template keeps
its existing size and CSS hooks -- only the artwork and the viewBox are
replaced, because the old variants used incompatible coordinate systems
(0 0 44 44 vs 0 0 200 200) and injecting 200-scale paths into a 44 viewBox
would render a logo 4x too large and clipped.

Gradient ids are made unique per file and per occurrence. Two SVGs on one page
sharing an id makes the browser resolve both to the first definition, which
silently breaks the second logo's gradient.

Usage:  python3 fix_logo.py [--apply]
        DRY_RUN=0 python3 fix_logo.py     (CI form)
"""
import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "pepstracker_fixed")

RX_NOINDEX = re.compile(r'<meta name="robots"[^>]*noindex', re.I)
RX_LOGO_A = re.compile(r'(<a[^>]*class="[^"]*\blogo\b[^"]*"[^>]*>)([\s\S]*?)(</a>)', re.I)
RX_SVG = re.compile(r'<svg([^>]*)>[\s\S]*?</svg>', re.I)
RX_VIEWBOX = re.compile(r'\s*viewBox="[^"]*"', re.I)
RX_FILL = re.compile(r'\s*fill="[^"]*"', re.I)


def canonical(attrs, uid):
    """Canonical mark at a 0 0 200 200 coordinate system."""
    a = RX_VIEWBOX.sub("", attrs)
    a = RX_FILL.sub("", a).rstrip()
    g1, g2 = "ptl%sa" % uid, "ptl%sb" % uid
    return (
        '<svg%s viewBox="0 0 200 200" fill="none">'
        '<defs>'
        '<linearGradient id="%s" x1="20" y1="130" x2="180" y2="40" gradientUnits="userSpaceOnUse">'
        '<stop offset="0%%" stop-color="#1a7fe8"/><stop offset="50%%" stop-color="#00e5cc"/>'
        '<stop offset="100%%" stop-color="#4de87a"/></linearGradient>'
        '<linearGradient id="%s" x1="20" y1="150" x2="180" y2="150" gradientUnits="userSpaceOnUse">'
        '<stop offset="0%%" stop-color="#1a7fe8"/><stop offset="100%%" stop-color="#4de87a"/>'
        '</linearGradient></defs>'
        '<path d="M20 140 Q100 195 180 120" fill="none" stroke="url(#%s)" stroke-width="10" stroke-linecap="round"/>'
        '<line x1="20" y1="128" x2="82" y2="82" stroke="url(#%s)" stroke-width="10" stroke-linecap="round"/>'
        '<line x1="82" y1="82" x2="128" y2="105" stroke="url(#%s)" stroke-width="10" stroke-linecap="round"/>'
        '<line x1="128" y1="105" x2="168" y2="48" stroke="#4de87a" stroke-width="10" stroke-linecap="round"/>'
        '<polygon points="178,38 152,46 168,64" fill="#4de87a"/>'
        '<circle cx="20" cy="128" r="18" fill="#1a7fe8"/>'
        '<circle cx="82" cy="82" r="18" fill="#00e5cc"/>'
        '<circle cx="128" cy="105" r="18" fill="#4de87a"/>'
        '</svg>' % (a, g1, g2, g2, g1, g1)
    )


def classify(svg_body):
    circles = len(re.findall(r"<circle", svg_body))
    return ("canonical" if circles == 3 and "<polygon" in svg_body else
            "simplified" if "polyline" in svg_body else
            "variant")


def fix_file(path, rel, stats):
    src = open(path, encoding="utf-8", errors="replace").read()
    if RX_NOINDEX.search(src):
        return None
    end = src.find("</header>")
    if end < 0:
        stats["no header"] = stats.get("no header", 0) + 1
        return None
    head, tail = src[:end], src[end:]
    n = [0]

    def repl(m):
        open_a, inner, close_a = m.groups()
        n[0] += 1
        uid = "%s%d" % (re.sub(r"[^a-z0-9]", "", rel.lower())[-10:] or "x", n[0])
        sm = RX_SVG.search(inner)
        if sm:
            kind = classify(sm.group(0))
            if kind == "canonical":
                stats["already canonical"] = stats.get("already canonical", 0) + 1
                return m.group(0)
            stats[kind] = stats.get(kind, 0) + 1
            new_inner = inner[:sm.start()] + canonical(sm.group(1), uid) + inner[sm.end():]
        else:
            # wordmark only: prepend the icon, keep the existing text node
            stats["icon added"] = stats.get("icon added", 0) + 1
            new_inner = canonical(' class="logo-icon" width="30" height="30"', uid) + inner
        return open_a + new_inner + close_a

    out = RX_LOGO_A.sub(repl, head, count=0) + tail
    if out == src:
        return None

    # invariants
    ids = re.findall(r'<linearGradient[^>]*\bid="([^"]+)"', out)
    assert len(ids) == len(set(ids)), "%s: duplicate gradient ids" % rel
    assert out.count("<header") == src.count("<header"), "%s: header count changed" % rel
    assert out.count("</a>") == src.count("</a>"), "%s: anchor count changed" % rel
    return out


def main(apply_changes):
    stats = {}
    changed = []
    for path in sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True)):
        rel = os.path.relpath(path, SITE).replace(os.sep, "/")
        out = fix_file(path, rel, stats)
        if out is None:
            continue
        changed.append(rel)
        if apply_changes:
            open(path, "w", encoding="utf-8").write(out)

    print("%s: %d files" % ("APPLIED" if apply_changes else "DRY RUN", len(changed)))
    for k in sorted(stats):
        print("   %-18s %d" % (k, stats[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv or os.environ.get("DRY_RUN") == "0"))
