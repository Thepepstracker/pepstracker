#!/usr/bin/env python3
"""
build_scorecard.py - per-vendor track-record metrics from PepsTracker's own
daily records. Runs after build_api.py (it reads api/v1/prices.json and
api/v1/vendors.json) and writes api/v1/scoreboard.json.

These are price-data metrics only - coverage, stock, and how often a vendor
holds the market's best price. Deliberately NOT a rating of product quality,
purity or safety; the note field says so and the page repeats it.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "pepstracker_fixed")
API = os.path.join(SITE, "api", "v1")


def load(name):
    with open(os.path.join(API, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    prices = load("prices.json")
    vendors = load("vendors.json")
    with open(os.path.join(SITE, "price-history.json"), encoding="utf-8") as fh:
        hist = json.load(fh)

    stats = {}
    for v in vendors["vendors"]:
        stats[v["id"]] = {
            "id": v["id"], "name": v.get("name"), "domain": v.get("domain"),
            "compounds": 0, "listings": 0, "in_stock": 0,
            "best_price_now": 0, "best_30d_share": 0.0,
            "first_seen": None,
        }

    for comp, rows in (prices.get("prices") or {}).items():
        seen = set()
        for r in rows:
            s = stats.get(r.get("vendor"))
            if not s:
                continue
            s["listings"] += 1
            if r.get("in_stock"):
                s["in_stock"] += 1
            if r["vendor"] not in seen:
                s["compounds"] += 1
                seen.add(r["vendor"])
        for r in rows:
            if r.get("in_stock") and r.get("usd_per_mg") is not None:
                if r["vendor"] in stats:
                    stats[r["vendor"]]["best_price_now"] += 1
                break

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    wins = defaultdict(int)
    total = 0
    for comp, pts in (hist.get("series") or {}).items():
        for pt in pts:
            v = pt.get("v")
            d = pt.get("d")
            if not v or not d:
                continue
            s = stats.get(v)
            if s and (s["first_seen"] is None or d < s["first_seen"]):
                s["first_seen"] = d
            if d >= cutoff:
                wins[v] += 1
                total += 1

    out_vendors = []
    for vid, s in stats.items():
        s["best_30d_share"] = round(wins[vid] / total, 4) if total else 0.0
        s["stock_rate"] = round(s["in_stock"] / s["listings"], 3) if s["listings"] else None
        del s["in_stock"]
        out_vendors.append(s)
    out_vendors.sort(key=lambda s: (-s["best_30d_share"], -s["compounds"], s["id"]))

    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Track-record metrics computed from PepsTracker's own daily "
                 "price records. Price-data metrics only - not a rating of "
                 "product quality, purity or safety."),
        "window_days": 30,
        "best_price_records_in_window": total,
        "vendors": out_vendors,
    }
    os.makedirs(API, exist_ok=True)
    with open(os.path.join(API, "scoreboard.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print("scoreboard ok: %d vendors, %d best-price records in %d-day window"
          % (len(out_vendors), total, 30))


if __name__ == "__main__":
    main()
