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
]


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
    files = sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True))
    changed_files = 0
    changed_nums = 0
    per_rule = dict((label, 0) for label, _ in RULES)

    for path in files:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        out = src
        edits = []
        for label, rx in RULES:
            def repl(m, label=label):
                old = m.group(0)
                if old == target:
                    return old
                edits.append((label, old))
                return target
            out = rx.sub(repl, out)
        if out == src:
            continue

        # Invariant: strip every digit from both versions. If anything other
        # than digits moved, the edit is unsafe and we abort the whole run.
        if re.sub(r"\d", "", out) != re.sub(r"\d", "", src):
            sys.exit("FATAL: non-digit change detected in %s; aborting" % path)

        changed_files += 1
        changed_nums += len(edits)
        for label, _old in edits:
            per_rule[label] += 1
        rel = os.path.relpath(path, ROOT)
        detail = ", ".join("%s %s->%s" % (l, o, target) for l, o in edits)
        print("%s: %s" % (rel, detail))
        if not DRY:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(out)

    print("")
    print("vendor count read from index.html: %d" % n)
    for label, count in per_rule.items():
        print("  %-22s %d" % (label, count))
    print("%s %d numbers in %d files" % ("WOULD CHANGE" if DRY else "CHANGED", changed_nums, changed_files))


if __name__ == "__main__":
    main()
