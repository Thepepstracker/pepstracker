#!/usr/bin/env python3
"""
sync_dictionary.py — keep peptides/*.html dictionary pages truthful.

These 82 pages were hand-written once and never updated. Three defects:

  D1  vendor counts frozen at write time, and inconsistent *within* a page
      (bpc157.html states 15, 11 and 12 in three places; actual is 24)
  D2  compound name in the meta description was title-cased from the slug,
      so search results read "Compare Ahkcu prices" / "Compare Bpc157 prices"
  D3  72 of 82 meta descriptions were hard-truncated at 158 chars, cutting
      mid-word ("...with discount codes o")

Vendor counts come from regenerate_pages.rank_vendors -- the same function the
price pages use -- so a dictionary page can never disagree with the cheapest-*
page for the same compound.

Usage:  python3 sync_dictionary.py [--apply]
        DRY_RUN=0 python3 sync_dictionary.py     (CI form)
Default is a dry run.

NOTE: this imports regenerate_pages, which imports `requests`. Any workflow
running this script must pip-install requests first.
"""
import importlib.util
import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "pepstracker_fixed")
MAX_DESC = 160          # Google truncates around here; stay under it
MIN_BLURB = 40          # never trim the biology blurb below this


def load_regen():
    """Import regenerate_pages without tripping its env-var requirements."""
    for k in ("GITHUB_TOKEN", "SCRAPERAPI_KEY", "GITHUB_REPOSITORY"):
        os.environ.setdefault(k, "x")
    spec = importlib.util.spec_from_file_location(
        "regen", os.path.join(HERE, "regenerate_pages.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def trim_to_sentence(text, budget):
    """Drop whole trailing sentences until the text fits.

    Only ever cuts on a sentence boundary. Cutting on a word boundary would
    leave a dangling fragment ("drives fat reduction via.") -- grammatically
    worse than the mid-word truncation this script exists to remove. If no
    sentence boundary fits, the caller keeps the blurb whole and shortens its
    own claim instead.
    """
    text = text.strip()
    if len(text) <= budget:
        return text
    parts = re.findall(r'[^.!?]*[.!?]', text)
    out = ""
    for p in parts:
        if len(out) + len(p) > budget:
            break
        out += p
    return out.strip()


# ---- the three rewritable regions -------------------------------------------
RX_DESC = re.compile(r'(<meta name="description" content=")([^"]*)(")')
RX_TITLE = re.compile(r'(<title>)([^<]*)(</title>)')
TITLE_LIMIT = 60        # Google truncates a result title around here
BRAND_SUFFIX = re.compile(r'\s*\|\s*PepsTracker\s*$')
RX_BODY = re.compile(
    r'(<p>Real-time prices across )(\d+ vendors?)( with discount codes already applied\.</p>)')
RX_DIV = re.compile(
    r'(color:#7a8ba8;">)(\d+ vendors?)( compared, discount codes applied</div>)')
# Trailing claim shapes this script may have produced, in any generation.
# Every one must be strippable or the script appends a second copy on the next
# run and the description grows without bound.
RX_CLAIMS = [
    re.compile(r'\s*Compare\b.*$', re.S),      # any "Compare ..." tail
    # Any trailing sentence that mentions vendors. Broad on purpose: it must
    # catch every short fallback form. Safe because a peptide biology blurb
    # never ends with a sentence about vendors -- and the idempotency assert
    # in main() fails loudly if a form ever escapes this.
    re.compile(r'\s*[^.!?]*\bvendors?\b[^.!?]*[.!?]\s*$'),
]


def strip_claim(text):
    """Remove trailing generated claims until the text stops shrinking."""
    prev = None
    while prev != text:
        prev = text
        for rx in RX_CLAIMS:
            text = rx.sub("", text).strip()
    return text


def rebuild_desc(old, name, n):
    """Replace the trailing 'Compare ... vendors ...' claim with a correct one."""
    blurb = strip_claim(old)
    if not blurb:                      # no biology blurb -- leave the page alone
        return None
    if not blurb.endswith((".", "!", "?")):
        blurb += "."
    v = plural(n, "vendor")
    # Longest claim that fits wins; the biology blurb stays intact.
    variants = [
        f" Compare {name} prices across {v} with discount codes on PepsTracker.",
        f" Compare {name} prices across {v} with discount codes.",
        f" Compare {name} prices across {v} on PepsTracker.",
        f" Compare {name} prices across {v}.",
        f" Compare {name} across {v}.",
        f" {name}: {v} compared.",
        # Last resort only -- loses the compound name, which is the page's
        # primary keyword, so every named form above is tried first.
        f" Compare prices across {v}.",
    ]
    for claim in variants:
        if len(blurb) + len(claim) <= MAX_DESC:
            return blurb + claim
    # Blurb alone is enormous -- drop whole trailing sentences, never words.
    claim = variants[-1]
    blurb = trim_to_sentence(blurb, MAX_DESC - len(claim))
    return (blurb + claim) if blurb else None


# Blog posts written about one compound. Their vendor counts are per-compound,
# not site-wide, so sync_site_counts.py deliberately leaves them alone -- and
# nothing else owned them, so blog-cheapest-semaglutide sat at "25 Vendors
# Compared" in six places and "11 research peptide vendors" in two others while
# Semaglutide actually had 21.
#
# Only the per-compound phrasings below are rewritten. Site-wide sentences on
# the same pages ("across all 27 vendors we monitor", "23 of the 27 vendors on
# PepsTracker publish COAs") do not match any of them and stay untouched.
BLOG_COMPOUND = {
    "blog-cheapest-semaglutide-2026.html": "Semaglutide",
    "blog-bpc157-price-2026.html": "BPC-157",
}

BLOG_CLAIMS = [
    re.compile(r"(?<=— )(\d+)(?= Vendors Compared)"),
    re.compile(r"(?<=Comparison Across )(\d+)(?= Vendors)"),
    re.compile(r"(?<=all )(\d+)(?= vendors compared by)"),
    re.compile(r"(?<=checked all )(\d+)(?= vendors after discounts)"),
    re.compile(r"(?<=among all )(\d+)(?= vendors that carry it)"),
    re.compile(r"(?<=prices across )(\d+)(?= research peptide vendors)"),
    re.compile(r"(?<=prices across )(\d+)(?= vendors after discount)"),
]


def sync_compound_blogs(rg, prices, vendors, apply_changes):
    out = []
    for base, compound in sorted(BLOG_COMPOUND.items()):
        path = os.path.join(SITE, base)
        if not os.path.exists(path) or compound not in prices:
            continue
        src = open(path, encoding="utf-8", errors="replace").read()
        n = str(len(rg.rank_vendors(prices[compound], vendors)))
        text = src
        hits = 0
        for rx in BLOG_CLAIMS:
            text, k = rx.subn(n, text)
            hits += k
        if text == src:
            continue
        # Only digits may move, and every per-compound claim must now agree.
        assert re.sub(r"\d", "", text) == re.sub(r"\d", "", src), \
            f"{base}: non-digit change"
        for rx in BLOG_CLAIMS:
            assert set(rx.findall(text)) <= {n}, f"{base}: {rx.pattern} disagrees"
        if apply_changes:
            open(path, "w", encoding="utf-8").write(text)
        out.append((base, compound, n, hits))
    return out


# Hand-written prose on the cheapest-* pages describing that page's own table.
# The regenerator owns the title, h1 and table but not these sentences, so they
# froze at whatever the counts were when the pages were written. Every one of
# the 45 pages contradicted itself: cheapest-bpc-157 said "24 vendors compared"
# in the heading and "compares all 12 vendors we track" in the body.
#
# These describe the table on the page, so the right number is that compound's
# vendor count, not the site total.
CHEAPEST_PROSE = [
    re.compile(r"(?<=Compare all )\d+(?= vendors sorted by cost-per-mg)"),
    re.compile(r"(?<=compares all )\d+(?= vendors we track)"),
    re.compile(r"(?<=across all )\d+(?= vendors with discount codes already applied)"),
    re.compile(r"(?<=across the )\d+(?= vendors we track)"),
    re.compile(r"(?<=current data across )\d+(?= vendors,)"),
]


def sync_cheapest_prose(rg, prices, vendors, apply_changes):
    out = []
    for path in sorted(glob.glob(os.path.join(SITE, "cheapest-*.html"))):
        base = os.path.basename(path)
        src = open(path, encoding="utf-8", errors="replace").read()
        mo = re.search(r"<h1[^>]*>([^<]+)</h1>", src)
        if not mo:
            continue
        name = re.sub(r"^Cheapest\s+|\s+in \d{4}.*$", "", mo.group(1)).strip()
        key = rg.resolve_compound(name, prices)
        if not key:
            continue
        n = str(len(rg.rank_vendors(prices[key], vendors)))
        text = src
        hits = 0
        for rx in CHEAPEST_PROSE:
            text, k = rx.subn(n, text)
            hits += k
        if text == src:
            continue
        assert re.sub(r"\d", "", text) == re.sub(r"\d", "", src), \
            "%s: non-digit change" % base
        for rx in CHEAPEST_PROSE:
            assert set(rx.findall(text)) <= {n}, "%s: disagreement" % base
        if apply_changes:
            open(path, "w", encoding="utf-8").write(text)
        out.append((base, key, n, hits))
    return out


def main(apply_changes):
    rg = load_regen()
    html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    prices = rg.parse_prices(html)
    vendors = rg.parse_vendors(html)

    changed = skipped = 0
    fixes = {"desc": 0, "body": 0, "div": 0, "title": 0}
    unresolved = []

    for path in sorted(glob.glob(os.path.join(SITE, "peptides", "*.html"))):
        base = os.path.basename(path)
        src = open(path, encoding="utf-8", errors="replace").read()

        mo = re.search(r'<h1[^>]*class="pep-name"[^>]*>([^<]+)</h1>', src) \
            or re.search(r'<h1[^>]*>([^<]+)</h1>', src)
        if not mo:
            unresolved.append((base, "no h1"))
            skipped += 1
            continue
        display = mo.group(1).strip()

        key = rg.resolve_compound(display, prices)
        if not key:
            unresolved.append((base, f"unmatched '{display}'"))
            skipped += 1
            continue

        n = len(rg.rank_vendors(prices[key], vendors))
        if n == 0:
            unresolved.append((base, "zero vendors"))
            skipped += 1
            continue

        name = key                      # canonical name from PRICES
        out = src
        local = []

        m = RX_DESC.search(out)
        if m:
            new_desc = rebuild_desc(m.group(2), name, n)
            if new_desc and new_desc != m.group(2):
                # Idempotency: feeding the result back in must be a fixed point.
                # Without this, a claim variant the stripper does not recognise
                # gets appended again on every run and the description grows.
                assert rebuild_desc(new_desc, name, n) == new_desc, \
                    f"{base}: description rewrite is not idempotent"
                out = out[:m.start(2)] + new_desc + out[m.end(2):]
                fixes["desc"] += 1
                local.append("desc")

        # Over-length title: drop the brand suffix rather than the compound
        # name. Google truncates past ~60 chars, so an over-long title loses
        # its tail anyway -- better to lose "| PepsTracker" deliberately than
        # to have the dictionary label cut mid-word.
        tm = RX_TITLE.search(out)
        if tm and len(tm.group(2)) > TITLE_LIMIT:
            short = BRAND_SUFFIX.sub("", tm.group(2)).strip()
            if short and short != tm.group(2):
                out = out[:tm.start(2)] + short + out[tm.end(2):]
                fixes["title"] = fixes.get("title", 0) + 1
                local.append("title")

        want = plural(n, "vendor")
        new, k = RX_BODY.subn(lambda mm: mm.group(1) + want + mm.group(3), out)
        if k and new != out:
            out = new
            fixes["body"] += 1
            local.append("body")
        new, k = RX_DIV.subn(lambda mm: mm.group(1) + want + mm.group(3), out)
        if k and new != out:
            out = new
            fixes["div"] += 1
            local.append("div")

        if out == src:
            continue

        # --- invariants -----------------------------------------------------
        # every vendor count left on the page must now agree
        counts = set(int(x) for x in re.findall(
            r'(\d+)\s+vendors?\b(?= with discount| compared)', out))
        assert counts <= {n}, f"{base}: disagreeing counts {counts} vs {n}"
        d = RX_DESC.search(out)
        if d:
            assert len(d.group(2)) <= MAX_DESC, f"{base}: desc too long"
            assert d.group(2).rstrip().endswith((".", "!", "?")), \
                f"{base}: desc still truncated mid-sentence"
        # body text outside the rewritten spans must be untouched
        assert len(out) - len(src) < 400, f"{base}: suspicious size delta"

        changed += 1
        if apply_changes:
            open(path, "w", encoding="utf-8").write(out)
        else:
            print(f"  {base:28s} n={n:<3} {'+'.join(local)}")

    prose = sync_cheapest_prose(rg, prices, vendors, apply_changes)
    if prose:
        print("  cheapest-* prose synced on %d pages (%d claims)"
              % (len(prose), sum(h for _, _, _, h in prose)))

    blogs = sync_compound_blogs(rg, prices, vendors, apply_changes)
    for base, compound, n, hits in blogs:
        print(f"  {base:36s} {compound} -> {n} vendors ({hits} claims)")

    print(f"\n{'APPLIED' if apply_changes else 'DRY RUN'}: "
          f"{changed + len(blogs) + len(prose)} pages changed, {skipped} skipped")
    print(f"  descriptions rebuilt : {fixes['desc']}")
    print(f"  body counts fixed    : {fixes['body']}")
    print(f"  footer counts fixed  : {fixes['div']}")
    if unresolved:
        print(f"  unresolved ({len(unresolved)}):")
        for b, why in unresolved:
            print(f"     {b:28s} {why}")
    return 0


if __name__ == "__main__":
    # --apply for humans; DRY_RUN=0 for CI (matches sync_site_counts.py).
    # Deliberately not driven by a workflow expression like
    # `inputs.dry_run && '' || '--apply'` -- an empty string is falsy in
    # GitHub Actions, so that form always yields '--apply'.
    apply_changes = "--apply" in sys.argv or os.environ.get("DRY_RUN") == "0"
    sys.exit(main(apply_changes))
