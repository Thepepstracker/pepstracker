#!/usr/bin/env python3
"""
seo_hygiene.py — indexing hygiene that nothing else owns.

Four jobs, all idempotent, all pure stdlib:

  1. noindex the utility pages. robots.txt is "Allow: /" for everything, and
     none of these carried a robots meta, so the admin tool that takes a
     GitHub PAT, the admin console, the auth debug page and the raw email
     templates were all publicly indexable.

  2. Shorten over-length <title>s by dropping the " | PepsTracker" suffix,
     and only when that alone brings the title under the limit. Google
     truncates around 60 characters, so an over-long title loses its tail
     anyway; dropping the brand deliberately beats having the real subject
     cut mid-word. Titles that are still too long after that are editorial
     headlines and are left for a human -- this script never rewrites prose.

  3. Point duplicate dictionary pages at the copy the sitemap already
     prefers. Two compounds had two pages each with the same <h1>, both
     self-canonical, which asks Google to pick a winner for us.

  4. Rebuild the sitemap from what is actually on disk: every page that is
     indexable and self-canonical, and nothing else. 27 real content pages
     (including every compare-fusion-* page) were missing, so they had no
     discovery path.

Usage:  python3 seo_hygiene.py [--apply]
        DRY_RUN=0 python3 seo_hygiene.py     (CI form)
Default is a dry run.
"""
import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "pepstracker_fixed")
BASE = "https://pepstracker.com/"
TITLE_LIMIT = 60

NOINDEX = {
    "price-update.html": "admin tool with a GitHub PAT field",
    "admin-live.html": "admin console",
    "auth-test.html": "auth debug page",
    "email_weekly_deals.html": "email template",
    "email_welcome.html": "email template",
    "account.html": "logged-in user page",
    "login.html": "auth page",
    "signup.html": "auth page",
}

# duplicate -> the copy to keep (the one already in the sitemap)
DUPLICATES = {
    "peptides/cjc1295.html": "peptides/cjc1295dac.html",
    "peptides/melanotanii.html": "peptides/melanotan2.html",
}

ROBOTS_TAG = '<meta name="robots" content="noindex, nofollow"/>'
RX_ROBOTS = re.compile(r'<meta name="robots"[^>]*>', re.I)
RX_NOINDEX = re.compile(r'<meta name="robots"[^>]*noindex', re.I)
RX_TITLE = re.compile(r"(<title>)([^<]*)(</title>)")
RX_CANON = re.compile(r'<link rel="canonical"[^>]*>', re.I)
RX_CANON_HREF = re.compile(r'rel="canonical" href="' + re.escape(BASE) + r'([^"]*)"')
BRAND = re.compile(r"\s*\|\s*PepsTracker\s*$")


def read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def apply_noindex(report):
    for rel, why in sorted(NOINDEX.items()):
        path = os.path.join(SITE, rel)
        if not os.path.exists(path):
            continue
        src = read(path)
        if RX_NOINDEX.search(src):
            continue
        if RX_ROBOTS.search(src):
            out = RX_ROBOTS.sub(ROBOTS_TAG, src, count=1)
        else:
            m = re.search(r"<head[^>]*>", src, re.I)
            if not m:
                report.append(("SKIP", rel, "no <head>"))
                continue
            out = src[:m.end()] + "\n  " + ROBOTS_TAG + src[m.end():]
        yield path, out
        report.append(("noindex", rel, why))


def apply_titles(report):
    for path in sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True)):
        rel = os.path.relpath(path, SITE)
        src = read(path)
        if RX_NOINDEX.search(src):
            continue
        m = RX_TITLE.search(src)
        if not m:
            continue
        title = m.group(2).strip()
        if len(title) <= TITLE_LIMIT:
            continue
        short = BRAND.sub("", title).strip()
        # Only act when removing the brand is enough on its own. Anything
        # still over is a headline that needs a human, not a regex.
        if short == title or len(short) > TITLE_LIMIT:
            continue
        yield path, src[:m.start(2)] + short + src[m.end(2):]
        report.append(("title", rel, "%d -> %d" % (len(title), len(short))))


def apply_canonicals(report):
    for rel, target in sorted(DUPLICATES.items()):
        path = os.path.join(SITE, rel)
        if not os.path.exists(path) or not os.path.exists(os.path.join(SITE, target)):
            continue
        src = read(path)
        want = '<link rel="canonical" href="%s%s"/>' % (BASE, target)
        if want in src:
            continue
        if not RX_CANON.search(src):
            report.append(("SKIP", rel, "no canonical tag"))
            continue
        yield path, RX_CANON.sub(want, src, count=1)
        report.append(("canonical", rel, "-> " + target))


def indexable_pages(final):
    """Pages that belong in the sitemap: indexable and canonical to themselves.

    Reads from `final` (the post-edit content) so a page this run has just
    noindexed or re-canonicalised is judged on its new state, not its old one.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True)):
        rel = os.path.relpath(path, SITE).replace(os.sep, "/")
        src = final.get(path) or read(path)
        if RX_NOINDEX.search(src):
            continue
        c = RX_CANON_HREF.search(src)
        if c and c.group(1) not in (rel, ""):
            continue                      # canonical points elsewhere
        out.append(rel)
    return out


def build_sitemap(pages, old):
    """Rebuild, keeping the existing <urlset> header and per-URL metadata."""
    header = re.search(r"<urlset[^>]*>", old)
    header = header.group(0) if header else (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    keep = {}
    for block in re.findall(r"<url>[\s\S]*?</url>", old):
        loc = re.search(r"<loc>([^<]*)</loc>", block)
        if loc:
            keep[loc.group(1)] = block.strip()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', header]
    seen = set()
    for u in [BASE] + [BASE + p for p in pages if p != "index.html"]:
        if u in seen:
            continue
        seen.add(u)
        parts.append("  " + keep.get(u, (
            "<url>\n    <loc>%s</loc>\n"
            "    <changefreq>weekly</changefreq>\n"
            "    <priority>0.7</priority>\n  </url>" % u)))
    parts.append("</urlset>")
    return "\n".join(parts) + "\n"


def main(apply_changes):
    report = []
    writes = {}
    for gen in (apply_noindex(report), apply_titles(report), apply_canonicals(report)):
        for path, out in gen:
            writes[path] = out

    if apply_changes:
        for path, out in writes.items():
            open(path, "w", encoding="utf-8").write(out)

    # Sitemap last: it depends on the noindex and canonical edits above, so it
    # is computed from the post-edit content whether or not we are writing.
    sm_path = os.path.join(SITE, "sitemap.xml")
    old_sm = read(sm_path) if os.path.exists(sm_path) else ""
    new_sm = build_sitemap(indexable_pages(writes), old_sm)
    if new_sm != old_sm:
        if apply_changes:
            open(sm_path, "w", encoding="utf-8").write(new_sm)
        report.append(("sitemap", "sitemap.xml",
                       "%d -> %d urls" % (old_sm.count("<loc>"), new_sm.count("<loc>"))))

    kinds = {}
    for kind, rel, note in report:
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind in ("noindex", "canonical", "sitemap", "SKIP"):
            print("  %-10s %-34s %s" % (kind, rel, note))
    print("\n%s: %d change(s)" % ("APPLIED" if apply_changes else "DRY RUN", len(report)))
    for k in sorted(kinds):
        print("   %-10s %d" % (k, kinds[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv or os.environ.get("DRY_RUN") == "0"))
