#!/usr/bin/env python3
"""
build_api.py - generate PepsTracker's open-data endpoints (api/v1/).

Reads the live catalog out of pepstracker_fixed/index.html (the PRICES and
VENDORS blocks) plus price-history.json, and writes static, versioned
JSON/CSV endpoints under pepstracker_fixed/api/v1/. Everything here is data
the site already publishes on its pages - this just makes it machine-readable
at stable URLs. Any parse failure aborts the run so a bad build never ships.
"""
import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "pepstracker_fixed")
OUT = os.path.join(SITE, "api", "v1")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def balanced(src, marker):
    """Return the balanced {...} or [...] block that follows marker."""
    i = src.find(marker)
    if i < 0:
        sys.exit("FATAL: marker %r not found in index.html" % marker)
    k = i
    while src[k] not in "[{":
        k += 1
    depth = 0
    in_str = None
    m = k
    while m < len(src):
        ch = src[m]
        if in_str:
            if ch == "\\":
                m += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch == '"' or ch == "'":
            in_str = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                return src[k:m + 1]
        m += 1
    sys.exit("FATAL: unbalanced block at %r" % marker)


KEY_RX = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")


def js_to_obj(txt):
    """Convert the site's JS object literal to Python via JSON.

    The only JS-isms in these blocks are unquoted identifier keys and
    trailing commas; strings are double-quoted. Keys get quoted by a
    string-aware walk (never inside strings), then json.loads validates
    the whole thing - if the shape ever changes, this aborts rather than
    publishing garbage.
    """
    out = []
    last = ""
    i = 0
    n = len(txt)
    in_str = False
    while i < n:
        ch = txt[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(txt[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if last in "{[," or last == "":
            m = KEY_RX.match(txt, i)
            if m:
                out.append(txt[i:m.start(1)])
                out.append('"%s":' % m.group(1))
                i = m.end()
                last = ":"
                continue
        out.append(ch)
        if not ch.isspace():
            last = ch
        i += 1
    s = "".join(out)
    s = re.sub(r",(\s*[\]\}])", r"\1", s)
    return json.loads(s)


def write_json(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
    print("wrote api/v1/%s" % name)


def main():
    src = read(os.path.join(SITE, "index.html"))
    prices = js_to_obj(balanced(src, "const PRICES"))
    vendors = js_to_obj(balanced(src, "const VENDORS"))
    hist = json.loads(read(os.path.join(SITE, "price-history.json")))

    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "https://pepstracker.com",
        "docs": "https://pepstracker.com/data",
        "license": "Free to use with attribution to PepsTracker (pepstracker.com).",
        "disclaimer": ("Research compounds, research use only. Informational data; "
                       "not an endorsement of any vendor or product."),
    }

    vend_out = []
    for v in vendors:
        if isinstance(v, dict) and v.get("id"):
            vend_out.append({"id": v["id"], "name": v.get("name"),
                             "domain": v.get("domain"),
                             "code": v.get("code") or None,
                             "discount": v.get("discount") or None})
    o = dict(meta)
    o["count"] = len(vend_out)
    o["vendors"] = vend_out
    write_json("vendors.json", o)

    comp_out = {}
    n_listings = 0
    vmap = dict((v["id"], v) for v in vend_out)
    for comp, book in prices.items():
        if not isinstance(book, dict):
            continue
        rows = []
        for vid, listings in book.items():
            if not isinstance(listings, list):
                continue
            for L in listings:
                if not isinstance(L, dict):
                    continue
                price = L.get("price")
                mg = L.get("mg")
                if not isinstance(price, (int, float)) or price <= 0:
                    continue
                # `mg` already holds the TOTAL milligrams of the purchase.
                # `bulk`, where present, is the NUMBER OF VIALS in the pack -
                # not a milligram figure. Dividing by it inflated $/mg by the
                # vial count on every bulk listing (a 10x10mg pack came out 10x
                # too expensive). The site always divided by `mg` and was
                # right; only this builder was wrong.
                vials = L.get("bulk")
                vials = int(vials) if isinstance(vials, (int, float)) and vials >= 2 else None
                upm = None
                if isinstance(mg, (int, float)) and mg > 0:
                    upm = round(float(price) / float(mg), 4)
                rows.append({"vendor": vid,
                             "vendor_name": (vmap.get(vid) or {}).get("name"),
                             "listing": L.get("listing"),
                             "price_usd": price,
                             "total_mg": mg,
                             "vials": vials,
                             "mg_per_vial": (round(float(mg) / vials, 4)
                                             if vials and isinstance(mg, (int, float)) else mg),
                             "usd_per_mg": upm,
                             "in_stock": not L.get("oos", False),
                             "url": L.get("url")})
                n_listings += 1
        rows.sort(key=lambda r: (r["usd_per_mg"] is None, r["usd_per_mg"]))
        if rows:
            comp_out[comp] = rows
    o = dict(meta)
    o["note"] = ("price_usd is the listed store price recorded by the daily scan; "
                 "the on-site ranking additionally applies vendor discount codes "
                 "(see vendors.json). total_mg is the milligrams in the whole "
                 "purchase and is what usd_per_mg divides by; for a multi-vial "
                 "pack, vials gives the count and mg_per_vial the size of each.")
    o["compounds"] = len(comp_out)
    o["listings"] = n_listings
    o["prices"] = comp_out
    write_json("prices.json", o)

    o = dict(meta)
    for k in hist:
        o[k] = hist[k]
    write_json("price-history.json", o)

    series = hist.get("series") or {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["compound", "date", "best_usd_per_mg", "vendor"])
    first = None
    for comp in sorted(series):
        for pt in series[comp]:
            w.writerow([comp, pt.get("d"), pt.get("mg"), pt.get("v")])
            d = pt.get("d")
            if d and (first is None or d < first):
                first = d
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "price-history.csv"), "w", encoding="utf-8",
              newline="") as fh:
        fh.write(buf.getvalue())
    print("wrote api/v1/price-history.csv")

    o = dict(meta)
    o["vendors"] = len(vend_out)
    o["compounds"] = len(comp_out)
    o["listings"] = n_listings
    o["history_days"] = hist.get("days")
    o["history_start"] = first
    write_json("summary.json", o)
    print("api build ok: %d vendors, %d compounds, %d listings"
          % (len(vend_out), len(comp_out), n_listings))


if __name__ == "__main__":
    main()
