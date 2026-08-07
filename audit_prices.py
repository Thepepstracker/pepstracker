#!/usr/bin/env python3
"""
audit_prices.py - data-quality gate for pepstracker_fixed/index.html.

Catches the classes of bug that make a price-comparison site quietly wrong.
The one that motivated this file: WooCommerce variable products expose only
their cheapest variant, so every vial size got the small-vial price and the
biggest vial always looked like the best cost-per-mg. That put the wrong
vendor at #1 on 22 of 82 compounds and nothing flagged it.

Checks
  E1 flat-set        every size of a vendor/compound shares one price + URL
  E2 non-monotonic   a larger vial costs materially less than a smaller one
  E3 orphan vendor   listings under a vendor id that is not in VENDORS
  W1 duplicate       same vendor + compound + mg listed twice
  W2 incomplete      listing missing price or mg
  E4 no attribution a vendor's deep links drop the ref/coupon param that its
                    own configured URL uses, so those clicks earn nothing

E* are errors (exit 1). W* are reported but do not fail.
Known-legitimate exceptions live in audit_allowlist.txt, one "vendor|compound"
per line, # for comments.

Usage:
  python audit_prices.py              # fail on errors
  python audit_prices.py --warn-only  # report, always exit 0
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(ROOT, "pepstracker_fixed", "index.html")
ALLOW = os.path.join(ROOT, "audit_allowlist.txt")

DROP_TOLERANCE = 0.85


def load_allowlist():
    out = set()
    if not os.path.exists(ALLOW):
        return out
    with open(ALLOW, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#")[0].strip()
            if line:
                out.add(line)
    return out


def main():
    warn_only = "--warn-only" in sys.argv
    import importlib.util
    for key in ("GITHUB_TOKEN", "SCRAPERAPI_KEY", "GITHUB_REPOSITORY"):
        os.environ.setdefault(key, "audit")
    spec = importlib.util.spec_from_file_location("scr", os.path.join(ROOT, "scraper.py"))
    scr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scr)

    with open(INDEX, encoding="utf-8") as fh:
        html = fh.read()

    vm = re.search(r"const\s+VENDORS\s*=\s*\[(.*?)\n\s*\];", html, re.S)
    if not vm:
        sys.exit("FATAL: VENDORS array not found")
    vendor_ids = set(re.findall(r'id\s*:\s*"([^"]+)"', vm.group(1)))

    data = scr.parse_all_listings(html)
    allow = load_allowlist()
    errors, warns = [], []

    for comp in sorted(data):
        for vid, listings in sorted((data[comp] or {}).items()):
            tag = "%s|%s" % (vid, comp)
            ls = [l for l in (listings or []) if l.get("price") and l.get("mg")]

            if vid not in vendor_ids:
                errors.append("E3 orphan vendor  %-14s %s (%d listings)" % (vid, comp, len(ls)))
                continue
            for l in (listings or []):
                if not l.get("price") or not l.get("mg"):
                    warns.append("W2 incomplete     %-14s %-24s %s" % (vid, comp, l.get("listing")))
            seen = set()
            for l in ls:
                if l["mg"] in seen:
                    warns.append("W1 duplicate      %-14s %-24s %gmg" % (vid, comp, l["mg"]))
                seen.add(l["mg"])
            if tag in allow or len(ls) < 2:
                continue

            sizes = {l["mg"] for l in ls}
            prices = {round(l["price"], 2) for l in ls}
            urls = {l.get("url") for l in ls}
            if len(sizes) >= 2 and len(prices) == 1 and len(urls) == 1:
                errors.append(
                    "E1 flat-set       %-14s %-24s %d sizes all $%s"
                    % (vid, comp, len(ls), list(prices)[0])
                )
                continue

            ordered = sorted(ls, key=lambda x: x["mg"])
            for a, b in zip(ordered, ordered[1:]):
                if b["price"] < a["price"] * DROP_TOLERANCE:
                    errors.append(
                        "E2 non-monotonic  %-14s %-24s %gmg $%s -> %gmg $%s"
                        % (vid, comp, a["mg"], a["price"], b["mg"], b["price"])
                    )

    # E4: affiliate attribution. Each vendor's configured `url` carries the
    # param that identifies us (ref=, coupon=, sld=, aff=, rfsn=). If the
    # per-product deep links drop it, every click through those rows is
    # unattributed. Labsourced shipped 54 bare links this way.
    vendor_url = {}
    for blk in re.finditer(r"\{([^{}]*)\}", vm.group(1)):
        t = blk.group(1)
        i = re.search(r'id\s*:\s*"([^"]+)"', t)
        u = re.search(r'url\s*:\s*"([^"]+)"', t)
        if i and u:
            vendor_url[i.group(1)] = u.group(1)
    for vid, vurl in sorted(vendor_url.items()):
        mo = re.search(r"[?&]([A-Za-z_]+)=", vurl)
        if not mo:
            continue                      # vendor has no query-param attribution
        key = mo.group(1) + "="
        bare = []
        for comp, vs in data.items():
            for l in ((vs or {}).get(vid) or []):
                if l.get("url") and key not in l["url"]:
                    bare.append(comp)
        if bare:
            errors.append(
                "E4 no attribution %-14s %d links missing '%s' (e.g. %s)"
                % (vid, len(bare), key, bare[0])
            )

    # W4: duplicate vendor keys inside one compound. A JS object keeps only the
    # last value, so an earlier duplicate is silently dead data that the parser
    # cannot see. Brace-matched on purpose: regex segmentation of this block
    # misattributes arrays from neighbouring objects and invents false dupes.
    block_s, block_e = scr.find_prices_block(html)
    block = html[block_s:block_e + 1]

    def obj_end(text, open_idx):
        depth = 0
        in_str = None
        i = open_idx
        while i < len(text):
            ch = text[i]
            if in_str:
                if ch == "\\":
                    i += 2
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
                    return i
            i += 1
        return -1

    for mo in re.finditer(r'[\s,{]"?([A-Za-z0-9_$+\-./() ]+?)"?\s*:\s*\{', block):
        try:
            open_idx = block.index("{", mo.end() - 1)
        except ValueError:
            continue
        close = obj_end(block, open_idx)
        if close < 0:
            continue
        body = block[open_idx:close + 1]
        if "price" not in body:
            continue
        counts = {}
        for vk in re.findall(r'[\s,{]"?([A-Za-z_$][\w$]*)"?\s*:\s*\[', body):
            counts[vk] = counts.get(vk, 0) + 1
        for vk, c in sorted(counts.items()):
            if c > 1 and vk in vendor_ids:
                warns.append("W4 duplicate key  %-14s %-24s appears %d times"
                             % (vk, mo.group(1).strip(), c))

    total = sum(len(v or []) for c in data.values() for v in c.values())
    print("audited %d listings / %d compounds / %d vendors" % (total, len(data), len(vendor_ids)))
    print("")
    for w in warns:
        print("  " + w)
    if warns:
        print("")
    for e in errors:
        print("  " + e)
    print("")
    print("%d errors, %d warnings" % (len(errors), len(warns)))
    if errors and not warn_only:
        print("")
        print("Prices look wrong. If a finding is legitimate, add 'vendor|compound'")
        print("to audit_allowlist.txt with a note explaining why.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
