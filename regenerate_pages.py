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


# ───────────────────────── cheapest-* pass ─────────────────────────
def regen_cheapest(vendors, prices, today):
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

    log.info("cheapest-*: updated=%d skipped=%d failed=%d", changed, skipped, failed)
    return failed


# ═════════════════════ compare-* pages ═════════════════════
# These pages are 100% data-derived (no hand-written prose), so the whole
# content block is rebuilt. Each page's own shell — everything before
# <div class="page"> and from <footer> onward — is reused verbatim, so future
# design changes to the shell survive regeneration.

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def pair_rows(prices, vendors, a, b):
    """Shared compounds with each side's best $/mg, cheapest-first."""
    rows, a_sum, b_sum, aw, bw, tie = [], 0.0, 0.0, 0, 0, 0
    for compound, cmap in prices.items():
        ra = rank_vendors({a: cmap[a]}, vendors) if a in cmap else []
        rb = rank_vendors({b: cmap[b]}, vendors) if b in cmap else []
        if not ra or not rb:
            continue
        A, B = ra[0], rb[0]
        rows.append((compound, A, B))
        a_sum += A["permg"]
        b_sum += B["permg"]
        if A["permg"] < B["permg"]:
            aw += 1
        elif B["permg"] < A["permg"]:
            bw += 1
        else:
            tie += 1
    rows.sort(key=lambda r: min(r[1]["permg"], r[2]["permg"]))
    n = len(rows)
    return {"rows": rows, "n": n, "aw": aw, "bw": bw, "tie": tie,
            "a_avg": a_sum / n if n else 0, "b_avg": b_sum / n if n else 0}


def compare_table(rows, an, bn):
    out = ["<table>",
           f"    <tr><th>Peptide</th><th>{esc(an)}</th><th>{esc(bn)}</th><th>Cheaper</th></tr>"]
    for compound, A, B in rows[:18]:
        a_win = A["permg"] < B["permg"]
        is_tie = A["permg"] == B["permg"]
        gap = abs(A["permg"] - B["permg"])
        pct = round(gap / max(A["permg"], B["permg"]) * 100) if max(A["permg"], B["permg"]) else 0
        a_style = "color:var(--green);font-weight:800;" if a_win and not is_tie else ""
        b_style = "color:var(--green);font-weight:800;" if (not a_win and not is_tie) else ""
        if is_tie:
            verdict = '<span style="color:#5a6a82;">Tie</span>'
        else:
            verdict = (f'<strong>{esc(an if a_win else bn)}</strong>'
                       f'<br><span style="font-size:.72rem;color:var(--green);">{pct}% cheaper</span>')
        out.append(
            "<tr>"
            f"<td><strong>{esc(compound)}</strong></td>"
            f'<td style="{a_style}">{fmt_permg(A["permg"])}<br>'
            f'<span style="font-size:.72rem;color:#5a6a82;">{fmt_money(A["disc"])} / {fmt_mg(A["mg"])}</span></td>'
            f'<td style="{b_style}">{fmt_permg(B["permg"])}<br>'
            f'<span style="font-size:.72rem;color:#5a6a82;">{fmt_money(B["disc"])} / {fmt_mg(B["mg"])}</span></td>'
            f"<td>{verdict}</td>"
            "</tr>")
    out.append("</table>")
    return "\n".join(out)


def compare_faq(an, bn, st, a_cat, b_cat, a_code, b_code, a_disc, b_disc, cheaper_avg, gap_pct):
    w_name = an if st["aw"] > st["bw"] else (bn if st["bw"] > st["aw"] else None)
    l_name = bn if w_name == an else (an if w_name == bn else None)
    w_wins, l_wins = max(st["aw"], st["bw"]), min(st["aw"], st["bw"])
    decided = st["aw"] + st["bw"]
    dpct = round(w_wins / decided * 100) if decided else 0
    if w_name:
        a1 = (f"{w_name} is cheaper on {w_wins} of the {st['n']} peptides both vendors stock, "
              f"{l_name} on {l_wins}"
              + (f", and {st['tie']} are priced identically at the two vendors" if st["tie"] else "")
              + f". Across the compounds where they differ, that is {dpct}% in {w_name}'s favour. "
              f"On average cost-per-milligram, {cheaper_avg} comes out roughly {gap_pct}% lower. "
              "Neither wins everything, so check the specific compound you need.")
    else:
        a1 = ("They are remarkably even — each wins on the same number of shared compounds. "
              "The right pick depends entirely on which specific peptide you are buying.")
    return [
        (f"Which is cheaper overall, {an} or {bn}?", a1),
        (f"What discount codes do {an} and {bn} offer?",
         f"{an} uses code {a_code} for {round(a_disc*100)}% off, and {bn} uses {b_code} for "
         f"{round(b_disc*100)}% off. Every price in the comparison table already has these codes "
         "applied, which is why the ranking can differ from list prices."),
        (f"Do these two vendors carry the same peptides?",
         f"They overlap on {st['n']} compounds. {an} lists roughly {a_cat} tracked compounds and "
         f"{bn} lists about {b_cat}. If you need something outside the overlap, only one of them "
         "will have it."),
        ("Why compare cost per milligram instead of price?",
         "Vial sizes differ between vendors, so sticker price is misleading. A larger vial at a "
         "higher price is often cheaper per milligram. Every figure here is the discounted price "
         "divided by milligrams, which is the only like-for-like comparison."),
    ]


def build_compare(name, old_html, prices, vendors, catalog, a_id, b_id, today_month):
    va, vb = vendors[a_id], vendors[b_id]
    an, bn = va["name"], vb["name"]
    st = pair_rows(prices, vendors, a_id, b_id)
    if st["n"] < 2:
        return None, f"only {st['n']} shared compounds"

    url = f"https://pepstracker.com/{name}"
    w_name = an if st["aw"] > st["bw"] else (bn if st["bw"] > st["aw"] else None)
    l_name = bn if w_name == an else (an if w_name == bn else None)
    w_wins, l_wins = max(st["aw"], st["bw"]), min(st["aw"], st["bw"])
    decided = st["aw"] + st["bw"]
    dpct = round(w_wins / decided * 100) if decided else 0
    cheaper_avg = an if st["a_avg"] < st["b_avg"] else bn
    gap = abs(st["a_avg"] - st["b_avg"])
    gap_pct = round(gap / max(st["a_avg"], st["b_avg"]) * 100) if max(st["a_avg"], st["b_avg"]) else 0
    a_cat, b_cat = catalog.get(a_id, "—"), catalog.get(b_id, "—")

    if w_name:
        verdict = (f"<strong>{esc(w_name)}</strong> is cheaper on <strong>{w_wins}</strong> of the "
                   f"{st['n']} shared peptides, {esc(l_name)} on <strong>{l_wins}</strong>"
                   + (f", and <strong>{st['tie']}</strong> are priced identically" if st["tie"] else "")
                   + (f" — that is {dpct}% of the {decided} compounds where the two actually differ."
                      if decided else "."))
    else:
        verdict = (f"These two are <strong>dead even</strong> — each is cheaper on exactly "
                   f"{w_wins} of the {st['n']} shared peptides"
                   + (f", with {st['tie']} tied" if st["tie"] else "") + ".")

    title = (f"{an} vs {bn} (2026) — Price Comparison Across {st['n']} Peptides | PepsTracker")
    desc = (f"{an} vs {bn} compared on {st['n']} shared research peptides with discount codes "
            "applied. " + (f"{w_name} is cheaper on {w_wins}, {l_name} on {l_wins}"
                           + (f", and {st['tie']} are priced identically" if st["tie"] else "") + "."
                           if w_name else "An even split across the shared range.") + " Updated 2026.")
    faq = compare_faq(an, bn, st, a_cat, b_cat, va["code"], vb["code"],
                      va["discount"], vb["discount"], cheaper_avg, gap_pct)

    lds = [
        {"@context": "https://schema.org", "@type": "Article",
         "headline": f"{an} vs {bn} — 2026 Price Comparison", "description": desc,
         "datePublished": "2026-07-19",
         "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "url": url,
         "author": {"@type": "Organization", "name": "PepsTracker", "url": "https://pepstracker.com/"},
         "publisher": {"@type": "Organization", "name": "PepsTracker", "url": "https://pepstracker.com/"},
         "mainEntityOfPage": {"@type": "WebPage", "@id": url}},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "PepsTracker", "item": "https://pepstracker.com/"},
            {"@type": "ListItem", "position": 2, "name": "Vendor Comparisons",
             "item": "https://pepstracker.com/vendors.html"},
            {"@type": "ListItem", "position": 3, "name": f"{an} vs {bn}", "item": url}]},
    ]

    tie_note = (f" <strong>{st['tie']}</strong> of the {st['n']} shared compounds are priced "
                "identically at both vendors, so for those it comes down to shipping speed and "
                "stock rather than price.") if st["tie"] else ""

    card = ('<div style="background:var(--card);border:1px solid var(--border);'
            'border-radius:12px;padding:16px;">\n'
            '      <div style="font-weight:800;margin-bottom:6px;">{name}</div>\n'
            '      <div style="font-size:.82rem;color:#5a6a82;line-height:1.7;">Cheaper on '
            '<strong style="color:var(--green);">{wins}</strong> compounds<br>Catalog: {cat} tracked'
            '<br>Code: <code>{code}</code> ({pct}% off)</div>\n    </div>')

    content = (
        '<div class="page">\n'
        '  <p style="font-size:.82rem;color:#5a6a82;margin-bottom:20px;">'
        '<a href="/" style="color:var(--blue);text-decoration:none;">PepsTracker</a> › '
        '<a href="/vendors.html" style="color:var(--blue);text-decoration:none;">Vendors</a> › '
        f'{esc(an)} vs {esc(bn)}</p>\n'
        '  <div style="margin-bottom:8px;"><span style="background:rgba(59,158,255,.12);'
        'color:var(--blue);border:1px solid rgba(59,158,255,.25);padding:4px 12px;border-radius:20px;'
        'font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.5px;">'
        '⚖️ Vendor Comparison</span></div>\n'
        f'  <h1>{esc(an)} vs {esc(bn)} — Which Is Cheaper in 2026?</h1>\n'
        f'  <p style="color:#5a6a82;font-size:.82rem;margin-bottom:24px;">Updated {today_month} · '
        f'{st["n"]} shared compounds · discount codes applied</p>\n'
        '  <div style="background:var(--card);border:1px solid var(--border);border-radius:14px;'
        'padding:20px;margin-bottom:26px;">\n'
        '    <div style="font-size:.72rem;font-weight:800;text-transform:uppercase;'
        'letter-spacing:.5px;color:var(--green);margin-bottom:8px;">🏆 The verdict</div>\n'
        f'    <p style="margin:0 0 10px;">{verdict}</p>\n'
        '    <p style="margin:0;color:#5a6a82;font-size:.9rem;">Averaged across every shared '
        f'compound, <strong>{esc(cheaper_avg)}</strong> runs about <strong>{gap_pct}% lower</strong> '
        "on cost per milligram. Both figures already include each vendor's discount code.</p>\n"
        '  </div>\n'
        '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:28px;">\n    '
        + card.format(name=esc(an), wins=st["aw"], cat=a_cat, code=esc(va["code"]),
                      pct=round(va["discount"] * 100)) + "\n    "
        + card.format(name=esc(bn), wins=st["bw"], cat=b_cat, code=esc(vb["code"]),
                      pct=round(vb["discount"] * 100)) + "\n  </div>\n"
        "  <h2>Head-to-head: cost per milligram</h2>\n"
        "  <p>Every price below is the discounted price divided by milligrams, so vial sizes do not "
        "distort the comparison. Sorted by cheapest available option.</p>\n  "
        + compare_table(st["rows"], an, bn) + "\n"
        "  <h2>How to read this</h2>\n"
        f"  <p>Neither vendor wins across the board, which is the main takeaway. {esc(an)} is cheaper "
        f"on {st['aw']} of the {st['n']} shared compounds and {esc(bn)} on {st['bw']}.{tie_note} If you "
        "buy a single compound, the table above is the answer. If you are placing one larger order to "
        "save on shipping, the vendor that wins your two or three highest-volume compounds usually "
        "nets out ahead.</p>\n"
        f"  <p>Catalog breadth matters too: {esc(an)} lists around {a_cat} compounds we track versus "
        f"{b_cat} at {esc(bn)}. Outside the {st['n']} overlap, only one of them will stock what you "
        "need.</p>\n"
        "  <h2>Discount codes</h2>\n"
        f'  <p><strong>{esc(an)}</strong> — code <code>{esc(va["code"])}</code> for '
        f'{round(va["discount"]*100)}% off. <strong>{esc(bn)}</strong> — code '
        f'<code>{esc(vb["code"])}</code> for {round(vb["discount"]*100)}% off. Codes are applied '
        "before ranking on this page, which is why the order can differ from list prices. Always "
        "confirm the code at checkout.</p>\n"
        "  <h2>Frequently asked questions</h2>\n"
        + "".join(f"  <h3>{esc(q)}</h3>\n  <p>{esc(a)}</p>\n" for q, a in faq)
        + "  <h2>Compare live prices</h2>\n"
        '  <p><a href="/" style="color:var(--blue);">Open the live tracker</a> to compare these two '
        'against all 26 vendors in real time, or browse <a href="/vendors.html" '
        'style="color:var(--blue);">every vendor we track</a>.</p>\n'
        '  <p style="font-size:.8rem;color:#5a6a82;margin-top:26px;">PepsTracker is a price '
        "comparison service. All products referenced are for research use only. We do not sell or "
        "distribute any products. Affiliate links may generate a commission.</p>\n"
        "</div>\n")

    # splice: reuse this page's own shell
    p = old_html.find('<div class="page">')
    f = old_html.find("<footer")
    if p < 0 or f < 0 or f <= p:
        return None, "shell boundary not found"
    new = old_html[:p] + content + old_html[f:]

    report = []
    new = replace_once(new, r"<title>[^<]*</title>", f"<title>{esc(title)}</title>", "title", report)
    for label, pat in (("meta-desc", r'<meta name="description" content="[^"]*"\s*/?>'),
                       ("og-desc", r'<meta property="og:description" content="[^"]*"\s*/?>'),
                       ("tw-desc", r'<meta name="twitter:description" content="[^"]*"\s*/?>')):
        attr = ('name="description"' if label == "meta-desc" else
                'property="og:description"' if label == "og-desc" else 'name="twitter:description"')
        new = replace_once(new, pat, f'<meta {attr} content="{esc(desc)}"/>', label, report)

    blocks = list(re.finditer(r'<script type="application/ld\+json">[\s\S]*?</script>', new))
    if len(blocks) != 3:
        return None, f"expected 3 ld+json blocks, found {len(blocks)}"
    for m, ld in zip(reversed(blocks), reversed(lds)):
        tag = ('<script type="application/ld+json">'
               + json.dumps(ld, ensure_ascii=False, separators=(",", ":")) + "</script>")
        new = new[:m.start()] + tag + new[m.end():]
    report.append("ok:schema(3)")

    if new == old_html:
        return None, "no change"
    ok, why = safety_check(old_html, new)
    if not ok:
        return None, f"SAFETY FAIL: {why}"
    return new, " ".join(report)


def regen_compare(vendors, prices, today_month):
    by_name = {v["name"]: vid for vid, v in vendors.items()}
    catalog = {}
    for cmap in prices.values():
        for vid in cmap:
            if vid in vendors:
                catalog[vid] = catalog.get(vid, 0) + 1

    pages = [n for n in gh_list(SITE_DIR) if n.startswith("compare-") and n.endswith(".html")]
    log.info("Found %d compare-* pages", len(pages))
    changed = skipped = failed = 0
    for name in sorted(pages):
        path = f"{SITE_DIR}/{name}"
        try:
            html, sha = gh_get(path)
            m = re.search(r"<title>(.+?) vs (.+?) \(20\d\d\)", html)
            if not m:
                log.info("  skip %-56s unparseable title", name)
                skipped += 1
                continue
            a_id, b_id = by_name.get(m.group(1).strip()), by_name.get(m.group(2).strip())
            if not a_id or not b_id:
                log.info("  skip %-56s vendor not in VENDORS", name)
                skipped += 1
                continue
            new, note = build_compare(name, html, prices, vendors, catalog, a_id, b_id, today_month)
            if new is None:
                log.info("  skip %-56s %s", name, note)
                if note.startswith("SAFETY FAIL"):
                    failed += 1
                else:
                    skipped += 1
                continue
            if DRY_RUN:
                log.info("  DRY  %-56s %s", name, note)
            else:
                gh_put(path, new, sha, f"Auto-refresh comparison: {name}")
                log.info("  ok   %-56s %s", name, note)
            changed += 1
        except Exception as e:
            log.error("  FAIL %-56s %s", name, e)
            failed += 1
    log.info("compare-*: updated=%d skipped=%d failed=%d", changed, skipped, failed)
    return failed


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
    today_month = datetime.now(timezone.utc).strftime("%B %Y")

    failed = regen_cheapest(vendors, prices, today)
    failed += regen_compare(vendors, prices, today_month)

    log.info("Done%s. total failures=%d", " (dry run)" if DRY_RUN else "", failed)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
