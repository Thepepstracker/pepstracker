#!/usr/bin/env python3
"""
sync_site_counts.py - keep site-wide vendor counts in sync with index.html.

Generated pages bake in "all N vendors" phrasing at build time, so every time a
vendor is added the published artifacts drift. This rewrites ONLY an explicit
whitelist of site-wide phrases.

It deliberately does NOT touch:
  - per-compound counts ("12 vendors compared" on a BPC-157 page)
  - prices ($25), CSS (rgba(...,.25)), half-lives (~26 min), SNAP-25, doses
Anything not matched by a rule below is left exactly as-is.

Usage:
  DRY_RUN=1 python sync_site_counts.py   # report only, write nothing
  python sync_site_counts.py             # apply
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "pepstracker_fixed")
INDEX = os.path.join(SITE, "index.html")
DRY = os.environ.get("DRY_RUN") == "1"

# Each rule is (label, regex). The regex must use lookbehind/lookahead so that
# the ONLY thing captured is the number, and the surrounding text must be
# specific enough that the number can only ever mean "total vendors tracked".
STALE_TOTALS = {"22", "23", "24", "25", "26"}

RULES = [
    ("compare-page CTA",     re.compile(r"(?<=against all )\d+(?= vendors in real time)")),
    ("cost-per-mg CTA",      re.compile(r"(?<=Compare all )\d+(?= vendors on live \$/mg)")),
    ("vendor-page nav",      re.compile(r"(?<=All )\d+(?= Vendors (?:→|&rarr;))")),
    ("vendors-tracked stat", re.compile(r"(?<=\U0001F3EA )\d+(?= Vendors Tracked)")),
    ("track-all-daily",      re.compile(r"(?<=we track all )\d+(?= vendors daily)")),
    ("discount-code index",  re.compile(r"(?<=discount code for all )\d+(?= vendors)")),
    ("guide boilerplate",     re.compile(r"(?<=how to compare prices across )\d+(?= vendors)")),
    ("meta price comparison", re.compile(r"(?<=peptide price comparison across )\d+(?= vendors)")),
    ("about: track pricing",  re.compile(r"(?<=We track pricing across )\d+(?= vendors)")),
    ("faq: all of these",     re.compile(r"(?<=tracks prices for all of these across )\d+(?= vendors)")),
    ("publicly listed",       re.compile(r"(?<=compares publicly listed prices across )\d+(?= vendors)")),
    # Directory and ranking headings. "Sources" and "Peptide Vendors" never
    # appear in a per-compound context, so these are safe on their own.
    ("vendor directory head", re.compile(r"(?<=All )\d+(?= Peptide Vendors)")),
    ("vendor ranking head",   re.compile(r"(?<=Top )\d+(?= Peptide Vendors)")),
    ("vendor sources head",   re.compile(r"(?<=Top )\d+(?= Research Peptide Sources)")),
    # "Top 22 Ranked" / "All 22 Ranked" -- the og:title, h1 and breadcrumb on
    # best-peptide-vendors, which the two rules above did not reach because
    # they anchor on the word "Vendors"/"Sources" that this phrasing omits.
    ("ranked heading",        re.compile(r"(?<=Top )\d+(?= Ranked)")),
    ("ranked heading alt",    re.compile(r"(?<=All )\d+(?= Ranked)")),
    # An adjective between the number and "vendors" hides the claim from the
    # sweep's base pattern, which requires the two to be adjacent. "PepsTracker
    # tracks all N major vendors daily" is site-wide by its own wording, so the
    # per-compound values some pages carried there ("tracks all 5 major
    # vendors") were simply false.
    ("tracks-all-major",      re.compile(r"(?<=all )\d+(?= major vendors)")),
    ("all-tracked-vendors",   re.compile(r"(?<=all )\d+(?= tracked vendors)")),
    ("across-tracked",        re.compile(r"(?<=across )\d+(?= tracked vendors)")),
    ("from-trusted",          re.compile(r"(?<=from )\d+(?= trusted vendors)")),
    ("all-trusted",           re.compile(r"(?<=across all )\d+(?= trusted vendors)")),
    ("stat card vendors",     re.compile(r"\b\d+(?= vendors<br>)")),
    # Guide and hub meta/schema descriptions. Each lead-in below belongs to a
    # page covering several compounds, so the number is site coverage. None of
    # them match blog-bpc157-price's per-compound wording ("all 24 vendors
    # compared by $/mg", "checked all 24 vendors after discounts", "among all
    # 24 vendors that carry it"), which stays correct at 24.
    ("guide: mechanism+price", re.compile(r"(?<=and price across )\d+(?= vendors)")),
    ("guide: blend prices",    re.compile(r"(?<=blend prices across )\d+(?= vendors)")),
    ("guide: compared both",   re.compile(r"(?<=compared both across )\d+(?= vendors)")),
    ("guide: price comparison",re.compile(r"(?<=price comparison across )\d+(?= vendors)")),
    ("guide: vs semaglutide",  re.compile(r"(?<=vs Semaglutide across )\d+(?= vendors)")),
    ("guide: and more",        re.compile(r"(?<=and more across )\d+(?= vendors)")),
    ("hub: link list",         re.compile(r"(?<=</a> across )\d+(?= vendors)")),
    ("b12: checked all",       re.compile(r"(?<=checked all )\d+(?= vendors on PepsTracker)")),
    ("b12: verified across",   re.compile(r"(?<=verified across )\d+(?= vendors)")),
]


# ---------------------------------------------------------------------------
# Compound-count claims.
#
# "N+ compounds" is NOT reliably site-wide: vendor cards legitimately say
# "Platinum stocks 40+ compounds", "60+ compounds including hard-to-find",
# "Every vendor pair that shares 10+ compounds". A blanket rule would rewrite
# all of those to the site total and make them false.
#
# So every rule below is anchored to text that can only be a claim about our
# whole catalogue -- almost always sitting next to "27 vendors" or
# "PepsTracker tracks/compares". The "+" is kept, so "82+ compounds" stays
# true as the catalogue grows and the digit-only invariant still holds.
COMPOUND_RULES = [
    ("cmp: compares",     re.compile(r"(?<=PepsTracker compares )\d+(?=\+ compounds across)")),
    ("cmp: for all",      re.compile(r"(?<=for all )\d+(?=\+ compounds and)")),
    ("cmp: vendors and",  re.compile(r"(?<=vendors and )\d+(?=\+ compounds daily)")),
    ("cmp: vendors for",  re.compile(r"(?<=vendors for )\d+(?=\+ compounds)")),
    ("cmp: vendors comma",re.compile(r"(?<=vendors, )\d+(?=\+ compounds)")),
    ("cmp: vendors dot",  re.compile(r"(?<=vendors \u00b7 )\d+(?=\+ compounds)")),
    ("cmp: and sorted",   re.compile(r"(?<=and )\d+(?=\+ compounds \u2014 sorted)")),
    ("cmp: trusted",      re.compile(r"(?<=trusted vendors across )\d+(?=\+ compounds)")),
    ("cmp: stat card",    re.compile(r"(?<=<br>)\d+(?=\+ compounds)")),
    ("cmp: daily across", re.compile(r"(?<=vendors daily across )\d+(?=\+ compounds)")),
    ("cmp: across daily", re.compile(r"(?<=vendors across )\d+(?=\+ compounds daily)")),
    ("pep: tracked",      re.compile(r"(?<=\u00b7 )\d+(?=\+ peptides tracked)")),
    ("pep: across daily", re.compile(r"(?<=vendors across )\d+(?=\+ peptides daily)")),
    ("pep: compare for",  re.compile(r"(?<=Compare prices for )\d+(?=\+ peptides)")),
]


def compound_count():
    """Number of top-level keys in the PRICES object."""
    with open(INDEX, encoding="utf-8") as fh:
        names = compound_names(fh.read())
    n = len(set(names))
    if not 20 <= n <= 500:
        sys.exit("FATAL: implausible compound count %d; refusing to run" % n)
    return n


# ---------------------------------------------------------------------------
# Site-wide override for the compound guard.
#
# The guard below skips any "N vendors" claim with a compound name nearby,
# because a compound may genuinely have that many vendors. That is right for
# "the lowest cost per mg for BPC-157 among all 24 vendors that carry it"
# (BPC-157 really does have 24) but wrong for
# "PepsTracker normalizes Epithalon prices to cost-per-milligram across 25
# vendors", which is a claim about our coverage that merely happens to name a
# compound. The proof is that every guide page carries the identical number
# regardless of which compound it covers.
#
# Only these two shapes bypass the guard. Anything else stays protected.
SITEWIDE_PREFIX = re.compile(
    r"PepsTracker\s+(?:normalizes|compares|tracks)\b[^.<>]{0,130}$", re.I)
SITEWIDE_SUFFIX = re.compile(
    r"^\s*\+?\s*(?:research\s+peptide\s+)?vendors?\s+"
    r"(?:we\s+(?:track|monitor)|at\s+PepsTracker|on\s+PepsTracker)\b", re.I)


# Pages that are regenerated from data (cheapest-*, compare-*) and the
# per-compound dictionary pages carry legitimate per-compound vendor counts.
# Never touch those; only hand-written site-wide claims are in scope.
GENERATED = ("cheapest-", "compare-")


def compound_names(html):
    """Top-level keys of the PRICES object, i.e. the compound names.

    Deliberately does not import scraper.py: that pulls in `requests`, which
    this script does not otherwise need and which is not installed in the
    sync workflow. Keeping this file dependency-free is the point.
    """
    i = html.find("const PRICES")
    if i < 0:
        return []
    start = html.find("{", i)
    depth = 0
    in_str = None
    end = -1
    k = start
    while k < len(html):
        ch = html[k]
        if in_str:
            if ch == "\\":
                k += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in "\"'":
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = k
                break
        k += 1
    if end < 0:
        return []
    body = html[start + 1:end]
    names = []
    depth = 0
    in_str = None
    k = 0
    while k < len(body):
        ch = body[k]
        if in_str:
            if ch == "\\":
                k += 2
                continue
            if ch == in_str:
                in_str = None
            k += 1
            continue
        if ch in "\"'":
            if depth == 0:
                mo = re.match(r'"([^"]+)"\s*:', body[k:])
                if mo:
                    names.append(mo.group(1))
                    k += mo.end()
                    continue
            in_str = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        k += 1
    return names


COMPOUND_RX = None


def build_compound_rx(compounds):
    """Word-boundary matcher for compound names. Names shorter than 4 chars are
    dropped: they are too collision-prone to use as a guard."""
    names = sorted({c for c in compounds if len(c) >= 4}, key=len, reverse=True)
    if not names:
        return None
    return re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z])", re.I)


def site_wide_sweep(site, target, compounds):
    """Update hand-written 'N vendors' claims on non-generated pages.

    These were written when the site total was different and nothing updates
    them. They are identifiable because they all carry the same stale value.
    A sentence that names a specific compound is skipped: a few compounds
    genuinely have that many vendors, so those numbers may be correct.
    """
    rx = re.compile(r"\b(\d{1,3})(\s*\+?\s*(?:research\s+peptide\s+)?vendors?)\b", re.I)
    changed = []
    for path in sorted(glob.glob(os.path.join(site, "*.html"))):
        base = os.path.basename(path)
        if base.startswith(GENERATED):
            continue
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        hits = []

        def repl(m):
            n = m.group(1)
            if n == target or n not in STALE_TOTALS:
                return m.group(0)
            lo = max(0, m.start() - 90)
            ctx = m.string[lo:m.end() + 40]
            # An explicit statement about PepsTracker's own coverage is
            # site-wide even when a compound is named in the same sentence.
            before = m.string[max(0, m.start() - 140):m.start()]
            tail = m.group(2) + m.string[m.end():m.end() + 40]
            sitewide = bool(SITEWIDE_PREFIX.search(before)
                            or SITEWIDE_SUFFIX.match(tail))
            # Word-boundary match. A plain substring test is wrong here: short
            # compound names hide inside ordinary words ("PDA" in "updated"),
            # which silently skipped legitimate site-wide claims.
            if COMPOUND_RX and COMPOUND_RX.search(ctx) and not sitewide:
                return m.group(0)          # names a compound: may be per-compound
            hits.append(n)
            return target + m.group(2)

        out = rx.sub(repl, src)
        if out != src:
            if re.sub(r"\d", "", out) != re.sub(r"\d", "", src):
                sys.exit("FATAL: non-digit change in %s" % path)
            changed.append((base, len(hits)))
            if not DRY:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(out)
    return changed


def vendor_count():
    with open(INDEX, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"const\s+VENDORS\s*=\s*\[(.*?)\n\s*\];", src, re.S)
    if not m:
        sys.exit("FATAL: could not locate VENDORS array in index.html")
    ids = re.findall(r'id\s*:\s*"([^"]+)"', m.group(1))
    n = len(set(ids))
    if not 5 <= n <= 200:
        sys.exit("FATAL: implausible vendor count %d; refusing to run" % n)
    return n


def main():
    n = vendor_count()
    target = str(n)
    # .js is included because advisor-widget.js renders its own
    # "N vendors / N+ compounds" stat card, which drifted the same way the
    # pages did. The rules are anchored and the digit-only invariant still
    # guards every write, so widening the glob is safe.
    files = sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True) +
                   glob.glob(os.path.join(SITE, "**", "*.js"), recursive=True))
    changed_files = 0
    changed_nums = 0
    cn = str(compound_count())
    per_rule = dict((label, 0) for label, _ in RULES + COMPOUND_RULES)

    for path in files:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        out = src
        edits = []
        for label, rx, want in ([(l, r, target) for l, r in RULES] +
                                [(l, r, cn) for l, r in COMPOUND_RULES]):
            def repl(m, label=label, want=want):
                old = m.group(0)
                if old == want:
                    return old
                edits.append((label, old, want))
                return want
            out = rx.sub(repl, out)
        if out == src:
            continue

        # Invariant: strip every digit from both versions. If anything other
        # than digits moved, the edit is unsafe and we abort the whole run.
        if re.sub(r"\d", "", out) != re.sub(r"\d", "", src):
            sys.exit("FATAL: non-digit change detected in %s; aborting" % path)

        changed_files += 1
        changed_nums += len(edits)
        for label, _old, _want in edits:
            per_rule[label] += 1
        rel = os.path.relpath(path, ROOT)
        detail = ", ".join("%s %s->%s" % (l, o, w) for l, o, w in edits)
        print("%s: %s" % (rel, detail))
        if not DRY:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(out)

    # hand-written site-wide claims on non-generated pages
    with open(INDEX, encoding="utf-8") as fh:
        compounds = compound_names(fh.read())
    global COMPOUND_RX
    COMPOUND_RX = build_compound_rx(compounds)
    prose = site_wide_sweep(SITE, target, compounds)
    for base, cnt in prose:
        print("%s: %d site-wide vendor claim(s) -> %s" % (base, cnt, target))
    print("")
    print("hand-written pages updated: %d (%d claims)"
          % (len(prose), sum(c for _b, c in prose)))

    print("")
    print("vendor count read from index.html: %d" % n)
    for label, count in per_rule.items():
        print("  %-22s %d" % (label, count))
    print("%s %d numbers in %d files" % ("WOULD CHANGE" if DRY else "CHANGED", changed_nums, changed_files))


if __name__ == "__main__":
    main()
