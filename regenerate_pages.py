#!/usr/bin/env python3
"""
regenerate_pages.py — refresh the data-derived regions of cheapest-*.html pages
from the live VENDORS/PRICES data in pepstracker_fixed/index.html.

Runs AFTER scraper.py in the daily workflow. scraper.py commits index.html via the
GitHub contents API, so this script reads index.html back from the API (post-scrape
state) rather than the checked-out working copy, which would be stale.

DESIGN: surgical, not template-based.
Only regions computed from price data are replaced. Hand-written editorial prose
(compound explainers, vendor checklists, FAQ bodies) is preserved byte-for-byte.

Each region is replaced ONLY if its anchor matches exactly once. Pages that differ
structurally (e.g. cheapest-vitamin-b12.html) simply skip the regions they lack
instead of being mangled.

Every rewritten page must pass safety gates before it is pushed.
"""
import os, re, json, base64, logging
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("regen")

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "Thepepstracker/pepstracker")
GITHUB_API   = "https://api.github.com"
SITE_DIR     = "pepstracker_fixed"
INDEX_FILE   = f"{SITE_DIR}/index.html"
DRY_RUN      = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

# Minimum sane parse results — guards against a silent parser break rewriting
# every page with empty data.
MIN_VENDORS   = 20
MIN_COMPOUNDS = 50


# ───────────────────────── GitHub helpers ─────────────────────────
def _headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}"}


def gh_get(path):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    d = r.json()
    return base64.b64decode(d["content"]).decode("utf-8"), d["sha"]


def gh_put(path, content, sha, message):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.put(
        url,
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": sha,
            "branch": "main",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def gh_list(path):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    return [x["name"] for x in r.json() if x["type"] == "file"]


# ───────────────────────── parsing ─────────────────────────
def match_pair(s, start, open_ch, close_ch):
    """String-aware bracket matcher. Returns index of the closer, or -1."""
    depth = 0
    i = start
    in_str = False
    esc = False
    while i < len(s):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def parse_vendors(html):
    """VENDORS entries are objects; fields appear in varying order (milehigh has
    an extra `promo:`), so match each field independently within the object."""
    i = html.find("const VENDORS")
    if i < 0:
        return {}
    end = match_pair(html, html.index("[", i), "[", "]")
    seg = html[i:end + 1]
    out = {}
    pos = seg.find("{")
    while pos >= 0:
        close = match_pair(seg, pos, "{", "}")
        if close < 0:
            break
        obj = seg[pos:close + 1]
        vid = re.search(r'id:"([^"]+)"', obj)
        name = re.search(r'name:"([^"]+)"', obj)
        if vid and name:
            code = re.search(r'code:"([^"]*)"', obj)
            disc = re.search(r"discount:([\d.]+)", obj)
            out[vid.group(1)] = {
                "id": vid.group(1),
                "name": name.group(1),
                "code": code.group(1) if code else "",
                "discount": float(disc.group(1)) if disc else 0.0,
            }
        pos = seg.find("{", close + 1)
    return out


def parse_prices(html):
    """PRICES = {"Compound": {vendorId:[{price,mg,listing,url,oos}]}}"""
    i = html.find("const PRICES")
    if i < 0:
        return {}
    start = html.index("{", i)
    body = html[start:match_pair(html, start, "{", "}") + 1]
    out = {}
    for km in re.finditer(r'"([^"]+)"\s*:\s*\{', body):
        obj_start = body.index("{", km.end() - 1)
        fin = match_pair(body, obj_start, "{", "}")
        block = body[obj_start:fin + 1]
        vend = {}
        for vm in re.finditer(r"([A-Za-z_$][\w$]*)\s*:\s*\[", block):
            arr_start = block.index("[", vm.end() - 1)
            bfin = match_pair(block, arr_start, "[", "]")
            arr = block[arr_start:bfin + 1]
            items = []
            for im in re.finditer(r"\{([^{}]*)\}", arr):
                s2 = im.group(1)
                p = re.search(r"price:\s*([\d.]+)", s2)
                m = re.search(r"mg:\s*([\d.]+)", s2)
                oos = re.search(r"oos:\s*true", s2)
                if p and m and not oos:
                    price, mg = float(p.group(1)), float(m.group(1))
                    u = re.search(r'url:\s*"([^"]*)"', s2)
                    if price > 0 and mg > 0:
                        items.append({"price": price, "mg": mg,
                                      "url": u.group(1) if u else ""})
            if items:
                vend[vm.group(1)] = items
        out[km.group(1)] = vend
    return out


# ───────────────────────── ranking ─────────────────────────
def rank_vendors(compound_map, vendors):
    """Best (lowest $/mg after discount) listing per vendor, sorted cheapest first."""
    rows = []
    for vid, items in compound_map.items():
        v = vendors.get(vid)
        if not v:
            continue
        best = None
        for it in items:
            disc = it["price"] * (1 - v["discount"])
            permg = disc / it["mg"]
            if best is None or permg < best["permg"]:
                best = {"price": it["price"], "mg": it["mg"], "disc": disc,
                        "permg": permg, "url": it.get("url", "")}
        if best:
            rows.append({**best, "id": vid, "name": v["name"],
                         "code": v["code"], "discount": v["discount"]})
    rows.sort(key=lambda r: r["permg"])
    return rows


def fmt_money(n):
    return f"${n:,.2f}"


def fmt_permg(n):
    return f"${n:.3f}/mg" if n < 1 else f"${n:.2f}/mg"


def fmt_mg(n):
    return f"{n:g}mg"


# ───────────────────────── safe replace ─────────────────────────
def replace_once(text, pattern, new_text, label, report):
    """Replace only if the anchor matches exactly once. Uses a lambda so the
    replacement is treated literally (no backreference expansion)."""
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        report.append(f"skip:{label}({len(matches)} matches)")
        return text
    m = matches[0]
    report.append(f"ok:{label}")
    return text[:m.start()] + new_text + text[m.end():]


# ───────────────────────── safety gates ─────────────────────────
def safety_check(old, new):
    if len(new) < len(old) * 0.85:
        return False, f"size dropped {len(old)}->{len(new)}"
    if old.rstrip().endswith("</html>") and not new.rstrip().endswith("</html>"):
        return False, "lost closing </html>"
    if old.count("<h2") != new.count("<h2"):
        return False, f"h2 count changed {old.count('<h2')}->{new.count('<h2')}"
    if "<footer" in old and "<footer" not in new:
        return False, "lost footer"
    if new.count("<table") != old.count("<table"):
        return False, "table count changed"
    for bad in ("undefined", "NaN", "[object Object]"):
        if bad in new and bad not in old:
            return False, f"introduced '{bad}'"
    # every ld+json block must still parse
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', new, re.S):
        try:
            json.loads(blk)
        except Exception as e:
            return False, f"invalid JSON-LD ({e})"
    return True, "ok"


# ───────────────────────── region builders ─────────────────────────
MEDALS = ["🥇", "🥈", "🥉"]

BUY_STYLE = ("background:linear-gradient(135deg,#3b9eff,#1e6fcf);color:#fff;padding:5px 11px;"
             "border-radius:7px;text-decoration:none;font-size:.78rem;font-weight:700;white-space:nowrap;")
CODE_STYLE = "background:#141b27;border:1px solid #263347;padding:2px 6px;border-radius:5px;"
LIST_STYLE = "color:#5a6a82;text-decoration:line-through;font-size:.85rem;"
DISC_STYLE = "color:#4de87a;font-weight:700;"


def extract_badges(old_html):
    """Vendor-name decorations (e.g. the 🎁 BOGO tag) are not derivable from
    PRICES, so carry whatever exists forward rather than dropping it."""
    badges = {}
    tbl = re.search(r"<table>.*?</table>", old_html, re.S)
    if not tbl:
        return badges
    for row in re.finditer(r"<tr>(.*?)</tr>", tbl.group(0), re.S):
        cell = re.search(r"<td><strong>([^<]+)</strong>(.*?)</td>", row.group(1), re.S)
        if cell and cell.group(2).strip():
            badges[cell.group(1).strip()] = cell.group(2)
    return badges


def build_table(rows, badges):
    out = ["<table>",
           "        <thead><tr><th>#</th><th>Vendor</th><th>Size</th><th>List Price</th>"
           "<th>After Discount</th><th>$/mg</th><th>Code</th><th>Buy</th></tr></thead>",
           "        <tbody>"]
    for i, r in enumerate(rows):
        rank = MEDALS[i] if i < 3 else f"#{i+1}"
        badge = badges.get(r["name"], "")
        buy = (f'<a href="{r["url"]}" target="_blank" rel="noopener" style="{BUY_STYLE}">Shop →</a>'
               if r["url"] else "—")
        out.append(
            f'          <tr><td>{rank}</td>'
            f'<td><strong>{r["name"]}</strong>{badge}</td>'
            f'<td>{fmt_mg(r["mg"])}</td>'
            f'<td style="{LIST_STYLE}">{fmt_money(r["price"])}</td>'
            f'<td style="{DISC_STYLE}">{fmt_money(r["disc"])}</td>'
            f'<td><strong>{fmt_permg(r["permg"])}</strong></td>'
            f'<td><code style="{CODE_STYLE}">{r["code"]}</code></td>'
            f'<td>{buy}</td></tr>'
        )
    out += ["        </tbody>", "      </table>"]
    return "\n".join(out)


def build_product_ld(compound, rows, url):
    lows = [r["disc"] for r in rows]
    ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": compound,
        "category": "Research Peptide",
        "description": (f"Live price comparison for {compound} across {len(rows)} verified research "
                        "peptide vendors, normalized to cost per milligram with discount codes "
                        "applied. Research use only."),
        "url": url,
        "offers": {
            "@type": "AggregateOffer",
            "priceCurrency": "USD",
            "lowPrice": f"{min(lows):.2f}",
            "highPrice": f"{max(lows):.2f}",
            "offerCount": len(rows),
            "offers": [
                {"@type": "Offer", "price": f"{r['disc']:.2f}", "priceCurrency": "USD",
                 "availability": "https://schema.org/InStock",
                 "seller": {"@type": "Organization", "name": r["name"]}}
                for r in rows
            ],
        },
    }
    return ('<script type="application/ld+json">'
            + json.dumps(ld, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def resolve_compound(title_name, prices):
    """Map a page title's compound to a PRICES key.

    Exact match first so keys that legitimately contain parentheses — e.g.
    "PT-141 (Bremelanotide)" — win before the stripped fallback, which exists
    for titles like "Vitamin B12 (Research Grade)".
    """
    if title_name in prices:
        return title_name
    lower = {k.lower(): k for k in prices}
    if title_name.lower() in lower:
        return lower[title_name.lower()]
    stripped = re.sub(r"\s*\([^)]*\)\s*$", "", title_name).strip()
    if stripped and stripped != title_name:
        if stripped in prices:
            return stripped
        if stripped.lower() in lower:
            return lower[stripped.lower()]
    return None


def compound_for_page(html):
    m = re.search(r"<title>Cheapest\s+(.+?)\s+(?:in\s+)?20\d\d", html)
    return m.group(1).strip() if m else None


# ───────────────────────── per-page update ─────────────────────────
def update_page(name, html, prices, vendors, today):
    compound = compound_for_page(html)
    if not compound:
        return None, "no compound in <title>"
    key = resolve_compound(compound, prices)
    if not key:
        return None, f"'{compound}' not in PRICES"
    compound, cmap = key, prices[key]

    rows = rank_vendors(cmap, vendors)
    if len(rows) < 2:
        return None, f"only {len(rows)} in-stock vendors"

    best = rows[0]
    n = len(rows)
    url = f"https://pepstracker.com/{name}"
    badges = extract_badges(html)
    report = []
    new = html

    # 1. table
    new = replace_once(new, r"<table>[\s\S]*?</table>", build_table(rows, badges), "table", report)

    # 2. Product / AggregateOffer schema
    new = replace_once(
        new,
        r'<script type="application/ld\+json">\{"@context":"https://schema\.org","@type":"Product"[\s\S]*?</script>',
        build_product_ld(compound, rows, url), "product-ld", report)

    # 3. <title>
    new = replace_once(
        new, r"<title>Cheapest [^<]*</title>",
        f"<title>Cheapest {compound} 2026: {fmt_permg(best['permg'])} — {n} Vendors Compared | PepsTracker</title>",
        "title", report)

    # 4. meta description
    new = replace_once(
        new, r'<meta name="description" content="[^"]*"\s*/?>',
        (f'<meta name="description" content="Cheapest {compound} in 2026: {best["name"]} at '
         f'{fmt_permg(best["permg"])}. Use code {best["code"]} — All {n} vendors compared, '
         f'discount codes applied, sorted by $/mg."/>'),
        "meta-desc", report)

    # 5. og:description
    new = replace_once(
        new, r'<meta property="og:description" content="[^"]*"\s*/?>',
        (f'<meta property="og:description" content="Best deal: {best["name"]} at '
         f'{fmt_money(best["disc"])}/{fmt_mg(best["mg"])}. Compare all {n} vendors with '
         f'discount codes applied."/>'),
        "og-desc", report)

    # 6. last-updated line
    new = replace_once(
        new, r"Last updated:\s*<strong[^>]*>[^<]*</strong>\s*·\s*\d+\s*vendors tracked",
        f'Last updated: <strong style="color:var(--text);">{today}</strong> · {n} vendors tracked',
        "last-updated", report)

    if new == html:
        return None, "no change"
    ok, why = safety_check(html, new)
    if not ok:
        return None, f"SAFETY FAIL: {why}"
    return new, " ".join(report)


# ───────────────────────── main ─────────────────────────
def main():
    log.info("Reading %s (post-scrape state)", INDEX_FILE)
    index_html, _ = gh_get(INDEX_FILE)

    vendors = parse_vendors(index_html)
    prices = parse_prices(index_html)
    log.info("Parsed %d vendors, %d compounds", len(vendors), len(prices))

    if len(vendors) < MIN_VENDORS or len(prices) < MIN_COMPOUNDS:
        log.error("Parse looks broken (vendors=%d, compounds=%d) — aborting without writes.",
                  len(vendors), len(prices))
        raise SystemExit(1)

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    pages = [n for n in gh_list(SITE_DIR) if n.startswith("cheapest-") and n.endswith(".html")]
    log.info("Found %d cheapest-* pages", len(pages))

    changed = skipped = failed = 0
    for name in sorted(pages):
        path = f"{SITE_DIR}/{name}"
        try:
            html, sha = gh_get(path)
            new, note = update_page(name, html, prices, vendors, today)
            if new is None:
                log.info("  skip %-46s %s", name, note)
                if note.startswith("SAFETY FAIL"):
                    failed += 1
                else:
                    skipped += 1
                continue
            if DRY_RUN:
                log.info("  DRY  %-46s %s", name, note)
            else:
                gh_put(path, new, sha, f"Auto-refresh prices: {name}")
                log.info("  ok   %-46s %s", name, note)
            changed += 1
        except Exception as e:
            log.error("  FAIL %-46s %s", name, e)
            failed += 1

    log.info("Done. updated=%d skipped=%d failed=%d%s",
             changed, skipped, failed, " (dry run)" if DRY_RUN else "")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
