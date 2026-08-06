#!/usr/bin/env python3
"""
build_price_history.py - turn git history into a price time series.

The scraper commits pepstracker_fixed/index.html every day, so the repo already
holds a daily snapshot of every price we track. Nothing reads it. This walks
that history and emits pepstracker_fixed/price-history.json:

  {"generated": "...", "days": 57, "series": {
     "Retatrutide": [{"d": "2026-06-02", "mg": 3.915, "v": "retaone"}, ...]}}

  d  = date of the snapshot (one entry per day, the last commit that day)
  mg = cheapest cost per milligram across all vendors, discounts applied
  v  = vendor id holding that price

Out-of-stock listings are excluded, matching what the live tracker ranks on.

Two modes:
  --rebuild   walk the whole git history and build the file from scratch.
              Needs a full clone (git fetch --unshallow on CI).
  (default)   append today's point from the working-tree index.html to the
              existing file. O(1) per day, works on a shallow checkout.

Usage:
  python build_price_history.py            # append today
  python build_price_history.py --rebuild  # full backfill from git
  python build_price_history.py --check    # summary only, write nothing
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX = "pepstracker_fixed/index.html"
OUT = os.path.join(ROOT, "pepstracker_fixed", "price-history.json")
# A snapshot yielding fewer than this many compounds means the file was
# mid-edit or structurally broken that day; skip rather than record a spike.
MIN_COMPOUNDS = 20


def git(*args):
    return subprocess.run(["git"] + list(args), capture_output=True, text=True,
                          cwd=ROOT).stdout


def snapshots():
    """One commit per calendar day (the last one that day), oldest first."""
    out = git("log", "--format=%H %ad", "--date=short", "--", INDEX)
    by_day = {}
    for line in out.strip().split("\n"):
        if not line.strip():
            continue
        sha, day = line.split()
        by_day.setdefault(day, sha)   # git log is newest-first, so this keeps the last
    return sorted(by_day.items())


def vendor_discounts(html):
    m = re.search(r"const\s+VENDORS\s*=\s*\[(.*?)\n\s*\];", html, re.S)
    if not m:
        return None
    out = {}
    for blk in re.finditer(r"\{([^{}]*)\}", m.group(1)):
        t = blk.group(1)
        i = re.search(r'id\s*:\s*"([^"]+)"', t)
        if not i:
            continue
        d = re.search(r"discount\s*:\s*([\d.]+)", t)
        out[i.group(1)] = float(d.group(1)) if d else 0.0
    return out


def append_today(scr):
    """Add one point per compound for the working-tree index.html."""
    with open(os.path.join(ROOT, INDEX), encoding="utf-8") as fh:
        html = fh.read()
    disc = vendor_discounts(html)
    if disc is None:
        sys.exit("FATAL: VENDORS not found in working tree index.html")
    data = scr.parse_all_listings(html)
    if len(data) < MIN_COMPOUNDS:
        sys.exit("FATAL: only %d compounds parsed; refusing to record" % len(data))
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        payload = {"days": 0, "compounds": 0, "coverage": [], "series": {}}
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if payload["coverage"] and payload["coverage"][-1]["d"] == day:
        print("already recorded %s - nothing to do" % day)
        return payload, False
    payload["coverage"].append({"d": day, "vendors": len(disc), "compounds": len(data)})
    added = 0
    for comp, vs in data.items():
        best = None
        for vid, listings in (vs or {}).items():
            if vid not in disc:
                continue
            for l in (listings or []):
                if not l.get("price") or not l.get("mg") or l.get("oos"):
                    continue
                per_mg = l["price"] * (1 - disc[vid]) / l["mg"]
                if best is None or per_mg < best[0]:
                    best = (per_mg, vid)
        if best:
            payload["series"].setdefault(comp, []).append(
                {"d": day, "mg": round(best[0], 4), "v": best[1]})
            added += 1
    payload["days"] = len(payload["coverage"])
    payload["compounds"] = len(payload["series"])
    payload["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("appended %s: %d compounds, %d vendors" % (day, added, len(disc)))
    return payload, True


def main():
    check = "--check" in sys.argv
    rebuild = "--rebuild" in sys.argv
    sys.path.insert(0, ROOT)
    import importlib.util
    for k in ("GITHUB_TOKEN", "SCRAPERAPI_KEY", "GITHUB_REPOSITORY"):
        os.environ.setdefault(k, "history")
    spec = importlib.util.spec_from_file_location("scr", os.path.join(ROOT, "scraper.py"))
    scr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scr)

    if not rebuild and not check:
        payload, changed = append_today(scr)
        if changed:
            with open(OUT, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, separators=(",", ":"))
            print("wrote %s (%d bytes)" % (OUT, os.path.getsize(OUT)))
        return 0

    series = {}
    coverage = []          # per-day vendor/compound counts, so a step change in
                           # the floor can be told apart from a market move
    days = skipped = 0
    for day, sha in snapshots():
        html = git("show", "%s:%s" % (sha, INDEX))
        if not html:
            skipped += 1
            continue
        disc = vendor_discounts(html)
        if disc is None:
            skipped += 1
            continue
        try:
            data = scr.parse_all_listings(html)
        except Exception:
            skipped += 1
            continue
        if len(data) < MIN_COMPOUNDS:
            skipped += 1
            continue
        days += 1
        coverage.append({"d": day, "vendors": len(disc), "compounds": len(data)})
        for comp, vs in data.items():
            best = None
            for vid, listings in (vs or {}).items():
                if vid not in disc:          # vendor not in VENDORS that day
                    continue
                for l in (listings or []):
                    if not l.get("price") or not l.get("mg") or l.get("oos"):
                        continue
                    per_mg = l["price"] * (1 - disc[vid]) / l["mg"]
                    if best is None or per_mg < best[0]:
                        best = (per_mg, vid)
            if best:
                series.setdefault(comp, []).append(
                    {"d": day, "mg": round(best[0], 4), "v": best[1]})

    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
        "compounds": len(series),
        "coverage": coverage,
        "series": series,
    }
    print("days: %d  skipped: %d  compounds: %d" % (days, skipped, len(series)))
    longest = sorted(series.items(), key=lambda kv: -len(kv[1]))[:5]
    for comp, pts in longest:
        first, last = pts[0], pts[-1]
        chg = (last["mg"] - first["mg"]) / first["mg"] * 100 if first["mg"] else 0
        print("  %-24s %s $%-8s -> %s $%-8s (%+.0f%%)  %d points"
              % (comp, first["d"], first["mg"], last["d"], last["mg"], chg, len(pts)))
    if not check:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        print("wrote %s (%d bytes)" % (OUT, os.path.getsize(OUT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
