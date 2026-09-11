#!/usr/bin/env python3
"""Catalog sync: pull every vendor's live catalog and add untracked products
to the PRICES block as new listings. Dry-run by default; --apply commits edits.

Mapping is deliberately conservative: a product is only added when it maps to
an EXISTING compound with high confidence. Everything else lands in the
report as UNMAPPED for human review. Vials only - capsules, sprays, topicals
and cosmetic raws are excluded so $/mg stays meaningful.
"""
import json, re, sys, time
import requests

import os
os.environ.setdefault("GITHUB_TOKEN", "unused-for-sync")
os.environ.setdefault("SCRAPERAPI_KEY", "unused-for-sync")

import scraper  # reuse the site parser (module guards main behind __name__)

HTML_PATH = "pepstracker_fixed/index.html"
JUNK = re.compile(
    r"insurance|opener|syringe|needle|swab|gift|merch|apparel|shirt|hat|sticker"
    r"|storage|case\b|caps\b|capsule|tabs?\b|tablet|spray|serum|topical|cream"
    r"|mist|patch|raffle|upgrade|priority|protection|packaging|build your own"
    r"|shipping|1g\b|1 ?gram|ampule", re.I)
BLENDY = re.compile(r"blend|stack|/|\+|klow|glow\b|wolverine|mito", re.I)

ALIASES = {
    "epitalon": "Epithalon", "epithalon": "Epithalon",
    "mt-1": "Melanotan I", "mt1": "Melanotan I", "melanotan 1": "Melanotan I", "melanotan i": "Melanotan I",
    "mt-2": "Melanotan II", "mt2": "Melanotan II", "melanotan 2": "Melanotan II", "melanotan ii": "Melanotan II",
    "tb4": "TB-500", "tb-4": "TB-500", "thymosin beta-4": "TB-500", "thymosin beta 4": "TB-500", "tb-500": "TB-500", "tb500": "TB-500",
    "pt-141": "PT-141 (Bremelanotide)", "pt141": "PT-141 (Bremelanotide)", "bremelanotide": "PT-141 (Bremelanotide)",
    "ta1": "Thymosin Alpha-1", "ta-1": "Thymosin Alpha-1", "thymosin alpha 1": "Thymosin Alpha-1", "thymosin alpha-1": "Thymosin Alpha-1",
    "nad": "NAD+", "nad+": "NAD+",
    "bacteriostatic": "Bacteriostatic Water", "bac water": "Bacteriostatic Water",
    "reconstitution solution": "Bacteriostatic Water", "research diluent": "Bacteriostatic Water",
    "sterile preserved solvent": "Bacteriostatic Water",
    "aod-9604": "AOD-9604", "aod 9604": "AOD-9604", "aod9604": "AOD-9604",
    "5-amino-1mq": "5-Amino-1MQ", "5 amino 1mq": "5-Amino-1MQ", "5-amino 1mq": "5-Amino-1MQ", "5 amino": "5-Amino-1MQ", "5-amino-1-mq": "5-Amino-1MQ",
    "hcg": "HCG", "igf-1 lr3": "IGF-1 LR3", "igf1-lr3": "IGF-1 LR3", "igf1 lr3": "IGF-1 LR3", "igf-1lr3": "IGF-1 LR3",
    "ss-31": "SS-31", "ss31": "SS-31", "s-31": "SS-31", "s-31-s": "SS-31", "\u00a7-31": "SS-31", "elamipretide": "SS-31",
    "cagrilintide": "Cagrilintide", "cagri": "Cagrilintide",
    "cjc-1295 no dac": "CJC-1295 (No DAC)", "cjc-1295 (no dac)": "CJC-1295 (No DAC)",
    "cjc-1295 w/o dac": "CJC-1295 (No DAC)", "cjc1295 no dac": "CJC-1295 (No DAC)",
    "cjc-1295 w/ dac": "CJC-1295 (with DAC)", "cjc-1295 with dac": "CJC-1295 (with DAC)",
    "cjc-1295 w/dac": "CJC-1295 (with DAC)", "cjc-1295 (with dac)": "CJC-1295 (with DAC)",
    "oxytocin": "Oxytocin", "kisspeptin": "Kisspeptin", "vip": "VIP", "dsip": "DSIP",
    "adamax": "Adamax", "pinealon": "Pinealon", "cartalax": "Cartalax", "vilon": "Vilon",
    "semax": "Semax", "selank": "Selank", "glutathione": "Glutathione",
    "mots-c": "MOTS-c", "motsc": "MOTS-c", "mots c": "MOTS-c",
    "ghk-cu": "GHK-Cu", "ghkcu": "GHK-Cu", "ghk cu": "GHK-Cu",
    "bpc-157": "BPC-157", "bpc157": "BPC-157", "bpc 157": "BPC-157",
    "testagen": "Testagen", "tesofensine": "Tesofensine", "methylene blue": "Methylene Blue",
    "acetic acid": "Acetic Acid", "l-carnitine": "L-Carnitine", "kpv": "KPV",
    "snap-8": "SNAP-8", "snap8": "SNAP-8", "ll-37": "LL-37", "ll37": "LL-37",
    "ara-290": "ARA-290", "ara 290": "ARA-290", "pe-22-28": "PE-22-28",
    "slu-pp-332": "SLU-PP-332", "slupp332": "SLU-PP-332", "slu-pp332": "SLU-PP-332",
    "thymalin": "Thymalin", "sermorelin": "Sermorelin", "tesamorelin": "Tesamorelin",
    "ipamorelin": "Ipamorelin", "hexarelin": "Hexarelin", "ghrp-2": "GHRP-2", "ghrp-6": "GHRP-6",
    "aicar": "AICAR", "foxo4-dri": "FOXO4-DRI", "fox04-dri": "FOXO4-DRI",
    "semaglutide": "Semaglutide", "tirzepatide": "Tirzepatide", "retatrutide": "Retatrutide",
    "survodutide": None, "bronchogen": None, "pnc-27": None, "fgl": None,
    "cortagen": None, "prostamax": None, "thymagen": None, "cerebrolysin": None,
}

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

_USE_PROXY = os.environ.get("SYNC_USE_PROXY") == "1"
_SA_KEY = os.environ.get("SCRAPERAPI_KEY", "")

def _http_get(url, params):
    """Direct GET; falls back to ScraperAPI for bot-blocked stores (CI only)."""
    try:
        r = requests.get(url, params=params, timeout=30,
                         headers={"User-Agent": "Mozilla/5.0 (pepstracker sync)"})
        if r.status_code == 200:
            try:
                r.json()
                return r
            except Exception:
                pass
    except Exception:
        pass
    if not (_USE_PROXY and _SA_KEY):
        return None
    try:
        from urllib.parse import urlencode
        r = requests.get("http://api.scraperapi.com",
                         params={"api_key": _SA_KEY, "url": url + "?" + urlencode(params)},
                         timeout=120)
        if r.status_code == 200:
            r.json()
            return r
    except Exception:
        pass
    return None


def fetch_catalog(domain):
    """Return list of dicts {name, url, price, mg?} or None if unreachable."""
    out = []
    base = "https://" + domain
    try:
        for page in range(1, 6):
            r = _http_get(base + "/wp-json/wc/store/v1/products",
                          {"per_page": 100, "page": page})
            if r is None:
                break
            js = r.json()
            if not js:
                break
            for p in js:
                price = None
                try:
                    pr = p.get("prices") or {}
                    mu = int(pr.get("currency_minor_unit", 2))
                    price = float(pr.get("price")) / (10 ** mu)
                except Exception:
                    pass
                out.append({"name": p.get("name") or "", "url": p.get("permalink") or "",
                            "price": price, "id": p.get("id"),
                            "type": p.get("type"), "variations": p.get("variations") or []})
            if len(js) < 100:
                break
            time.sleep(0.5)
        if out:
            return out, "woo"
    except Exception:
        pass
    try:
        r = _http_get(base + "/products.json", {"limit": 250})
        if r is not None:
            js = r.json()
            for p in js.get("products", []):
                v0 = (p.get("variants") or [{}])[0]
                out.append({"name": p.get("title") or "",
                            "url": base + "/products/" + (p.get("handle") or ""),
                            "price": float(v0.get("price") or 0) or None,
                            "id": p.get("id"), "type": "simple", "variations": []})
            if out:
                return out, "shopify"
    except Exception:
        pass
    return None, None

def parse_mg(name):
    """Return (mg_total, bulk_n) or (None, None). IU/1000; mL as-is; packs multiply."""
    n = name
    pack = 1
    pm = re.search(r"(?:\u00d7|(?<=[\d\s)(])x)\s*(\d+)|\(?box of (\d+)\)?|(\d+)[- ]?pack|\((\d+)\s*vials?\)", n, re.I)
    if pm:
        pack = int(pm.group(1) or pm.group(2) or pm.group(3) or pm.group(4))
        if pack > 25:
            return None, None
    iu = re.search(r"([\d,.]+)\s*iu", n, re.I)
    if iu:
        return float(iu.group(1).replace(",", "")) / 1000.0 * pack, (pack if pack > 1 else None)
    mgs = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*m[gl]\b", n, re.I)]
    if mgs:
        return sum(mgs) * pack, (pack if pack > 1 else None)
    return None, None

def main():
    html = open(HTML_PATH, encoding="utf-8").read()
    listings = scraper.parse_all_listings(html)
    compounds = {norm(c): c for c in listings}
    tracked_slugs = {}   # vid -> set of slugs
    vendor_suffix = {}   # vid -> affiliate query suffix
    slug_compound = {}   # (vid, slugprefix) -> compound
    for comp, vm in listings.items():
        for vid, arr in vm.items():
            arr = arr if isinstance(arr, list) else [arr]
            for el in arr:
                if not isinstance(el, dict):
                    continue
                u = el.get("url") or ""
                m = re.search(r"/products?/([a-z0-9-]+)", u)
                if m:
                    slug = m.group(1)
                    tracked_slugs.setdefault(vid, set()).add(slug)
                    pref = re.sub(r"-?\d.*$", "", slug)
                    if len(pref) >= 5:
                        slug_compound[(vid, pref)] = comp
                q = re.search(r"\?(.+)$", u)
                if q and vid not in vendor_suffix:
                    vendor_suffix[vid] = "?" + q.group(1)

    additions = {}   # compound -> vid -> [entry,...]
    unmapped = []
    report = []
    for vid, domain in sorted(scraper.VENDOR_DOMAIN.items()):
        cat, src = fetch_catalog(domain)
        if not cat:
            report.append("%-14s UNREACHABLE" % vid)
            continue
        have = tracked_slugs.get(vid, set())
        new = 0
        for p in cat:
            name, url = p["name"], p["url"]
            if not name or not url or JUNK.search(name):
                continue
            m = re.search(r"/products?/([a-z0-9-]+)", url)
            slug = m.group(1) if m else None
            if slug and slug in have:
                continue
            mg, bulk = parse_mg(name)
            comp = None
            nn = name.lower()
            if BLENDY.search(name):
                for key in ("klow", "glow blend", "wolverine", "bpc-157 + tb-500", "bpc/tb"):
                    if key in nn:
                        cn = {"klow": "Klow Blend", "glow blend": "Glow Blend",
                              "wolverine": "BPC-157 + TB-500 Blend",
                              "bpc-157 + tb-500": "BPC-157 + TB-500 Blend",
                              "bpc/tb": "BPC-157 + TB-500 Blend"}[key]
                        if cn in listings:
                            comp = cn
                        break
                if comp is None:
                    unmapped.append("%s | %s" % (vid, name[:60]))
                    continue
            if comp is None and slug:
                pref = re.sub(r"-?\d.*$", "", slug)
                comp = slug_compound.get((vid, pref))
            if comp is None:
                for alias in sorted(ALIASES, key=len, reverse=True):
                    if alias in nn:
                        comp = ALIASES[alias]
                        break
                else:
                    cguess = norm(re.sub(r"\d.*$", "", name))
                    comp = compounds.get(cguess)
            if comp is None:
                unmapped.append("%s | %s" % (vid, name[:60]))
                continue
            if comp not in listings:
                unmapped.append("%s | %s -> unknown compound %s" % (vid, name[:50], comp))
                continue
            if mg is None or p["price"] is None or p["price"] <= 0:
                unmapped.append("%s | %s (no mg/price)" % (vid, name[:55]))
                continue
            full_url = url + (vendor_suffix.get(vid, "") if "?" not in url else "")
            entry = {"price": round(p["price"], 2), "mg": mg,
                     "listing": name.strip()[:60], "url": full_url}
            if bulk:
                entry["bulk"] = bulk
            additions.setdefault(comp, {}).setdefault(vid, []).append(entry)
            new += 1
        report.append("%-14s %s: %d live, %d new listings" % (vid, src, len(cat), new))

    # ---- audit-grade prechecks (2026-09-11): never propose a listing the daily
    # audit would reject. Skips same-size duplicates and non-monotonic prices
    # against everything already tracked, unless vendor|Compound is allowlisted.
    allow = set()
    try:
        for _ln in open("audit_allowlist.txt", encoding="utf-8"):
            _ln = _ln.split("#")[0].strip()
            if _ln:
                allow.add(_ln)
    except FileNotFoundError:
        pass
    skipped = []
    for comp in list(additions):
        for vid in list(additions[comp]):
            if "%s|%s" % (vid, comp) in allow:
                continue
            existing = [x for x in (listings.get(comp, {}).get(vid) or [])
                        if isinstance(x, dict)]
            kept = []
            for e in additions[comp][vid]:
                combined = existing + kept
                if any(abs(x.get("mg", 0) - e["mg"]) < 0.01
                       and x.get("bulk", 0) == e.get("bulk", 0) for x in combined):
                    skipped.append("DUP  %-12s %-22s %7.1fmg $%.2f" % (vid, comp[:22], e["mg"], e["price"]))
                    continue
                bad = False
                for x in combined:
                    if x.get("oos"):
                        continue
                    xm, xp = x.get("mg", 0), x.get("price", 0)
                    if (e["mg"] >= xm and e["price"] < xp) or (xm >= e["mg"] and xp < e["price"]):
                        bad = True
                        break
                if bad:
                    skipped.append("MONO %-12s %-22s %7.1fmg $%.2f" % (vid, comp[:22], e["mg"], e["price"]))
                    continue
                kept.append(e)
            if kept:
                additions[comp][vid] = kept
            else:
                del additions[comp][vid]
        if not additions[comp]:
            del additions[comp]
    if skipped:
        print("PRECHECK: skipped %d listings that would fail the daily audit" % len(skipped))
        for s in skipped[:120]:
            print("  SKIP " + s)

    total = sum(len(v) for c in additions.values() for v in c.values())
    print("=" * 70)
    print("CATALOG SYNC %s - %d proposed additions" %
          ("DRY RUN" if "--apply" not in sys.argv else "APPLY", total))
    print("=" * 70)
    for line in report:
        print("  " + line)
    print("-" * 70)
    for comp in sorted(additions):
        for vid, ents in sorted(additions[comp].items()):
            for e in ents:
                print("  ADD %-24s %-12s $%-8.2f %6.1fmg%s  %s" %
                      (comp[:24], vid, e["price"], e["mg"],
                       (" x%d" % e["bulk"]) if e.get("bulk") else "",
                       e["listing"][:38]))
    print("-" * 70)
    print("UNMAPPED (%d) - manual review:" % len(unmapped))
    for u in unmapped[:150]:
        print("  ? " + u)

    if "--apply" not in sys.argv:
        return
    out = html
    def insert_one(cur, comp, vid, objs):
        esc = re.escape(comp)
        for m in re.finditer('"' + esc + '"\\s*:\\s*\\{', cur):
            brace = m.end() - 1
            depth, end = 0, -1
            for j in range(brace, len(cur)):
                if cur[j] == "{":
                    depth += 1
                elif cur[j] == "}":
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            if end < 0 or "price:" not in cur[brace:end]:
                continue
            span = cur[m.start():end]
            vm2 = re.search(r"\b" + re.escape(vid) + r"\s*:\s*\[", span)
            if vm2:
                arr_open = m.start() + vm2.end() - 1
                return cur[:arr_open + 1] + objs + "," + cur[arr_open + 1:]
            return cur[:end] + "," + vid + ":[" + objs + "]" + cur[end:]
        return cur
    for comp, vmap in additions.items():
        for vid, ents in vmap.items():
            objs = ",".join(
                "{price:%s,mg:%s,listing:%s,url:%s%s}" % (
                    ("%g" % e["price"]), ("%g" % e["mg"]),
                    json.dumps(e["listing"]), json.dumps(e["url"]),
                    (",bulk:%d" % e["bulk"]) if e.get("bulk") else "")
                for e in ents)
            out = insert_one(out, comp, vid, objs)
    # verify before writing
    check = scraper.parse_all_listings(out)
    n_before = sum(len(a) for vm in listings.values() for a in vm.values() if a)
    n_after = sum(len(a) for vm in check.values() for a in vm.values() if a)
    print("VERIFY: compounds %d -> %d, listings %d -> %d" %
          (len(listings), len(check), n_before, n_after))
    if len(check) != len(listings) or n_after < n_before + total * 0.8:
        print("ABORT: verification failed, not writing")
        sys.exit(1)
    open(HTML_PATH, "w", encoding="utf-8").write(out)
    print("WROTE %s" % HTML_PATH)

if __name__ == "__main__":
    main()
