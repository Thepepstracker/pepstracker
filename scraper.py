"""
PepsTracker Price Scraper — ScraperAPI Edition
Routes all requests through ScraperAPI to bypass Cloudflare/bot detection.
"""

import os, re, json, time, base64, logging
from datetime import datetime, timezone
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]
SCRAPERAPI_KEY = os.environ["SCRAPERAPI_KEY"]
GITHUB_REPO    = "Thepepstracker/pepstracker"
GITHUB_FILE    = "pepstracker_fixed/index.html"
GITHUB_API     = "https://api.github.com"

def scraper_get(url, render_js=False, timeout=30):
    """Route any request through ScraperAPI — bypasses Cloudflare automatically."""
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "render": "true" if render_js else "false",
        "keep_headers": "true",
    }
    return requests.get("https://api.scraperapi.com/", params=params, timeout=timeout)

VENDORS = {
    "ascension":  {"base": "https://ascensionpeptides.com",  "type": "woocommerce"},
    "lapeptides": {"base": "https://lapeptides.net",          "type": "woocommerce"},
    "glacier":    {"base": "https://glacieraminos.shop",      "type": "shopify"},
    "milehigh":   {"base": "https://milehighcompounds.is",    "type": "woocommerce"},
    "ezpeptides": {"base": "https://ezpeptides.com",          "type": "woocommerce"},
    "amp":        {"base": "https://ameanopeptides.com",      "type": "woocommerce"},
    "labsourced": {"base": "https://labsourced.com",          "type": "woocommerce"},
    "ion":        {"base": "https://ionpeptide.com",          "type": "woocommerce"},
    "retaone":    {"base": "https://retaonelabs.com",         "type": "shopify"},
    "nura":       {"base": "https://nurapeptide.com",         "type": "woocommerce"},
    "atomik":     {"base": "https://atomiklabz.com",          "type": "woocommerce"},
}

SEARCH_ALIASES = {
    "Semaglutide": "semaglutide", "Tirzepatide": "tirzepatide",
    "Retatrutide": "retatrutide", "Liraglutide": "liraglutide",
    "BPC-157": "bpc-157", "BPC-157 (Oral)": "bpc oral",
    "TB-500": "tb-500", "TB-500 Fragment (17-23)": "tb-500 fragment",
    "BPC-157 + TB-500 Blend": "bpc tb blend",
    "CJC-1295 (with DAC)": "cjc dac",
    "CJC-1295 (no DAC) / Mod GRF 1-29": "cjc mod grf",
    "Ipamorelin": "ipamorelin", "Hexarelin": "hexarelin",
    "GHRP-2": "ghrp-2", "GHRP-6": "ghrp-6", "Sermorelin": "sermorelin",
    "Tesamorelin": "tesamorelin", "GHRH (1-29)": "ghrh",
    "CJC-1295 + Ipamorelin Blend": "cjc ipamorelin blend",
    "IGF-1 LR3": "igf-1 lr3", "IGF-1 DES": "igf-1 des",
    "HGH Fragment 176-191": "hgh fragment 176", "AOD 9604": "aod 9604",
    "MGF (Mechano Growth Factor)": "mgf", "PEG-MGF": "peg-mgf",
    "Follistatin 344": "follistatin", "Adipotide (FTPP)": "adipotide",
    "5-Amino-1MQ": "5-amino-1mq", "Melanotan I (MT-1)": "melanotan i",
    "Melanotan II": "melanotan ii", "PT-141 (Bremelanotide)": "pt-141",
    "GHK-Cu": "ghk-cu", "SNAP-8": "snap-8", "Leuphasyl": "leuphasyl",
    "Selank": "selank", "N-Acetyl Selank": "n-acetyl selank",
    "Semax": "semax", "N-Acetyl Semax": "n-acetyl semax",
    "Dihexa": "dihexa", "DSIP (Delta Sleep Inducing Peptide)": "dsip",
    "P21": "p21", "Cerebrolysin": "cerebrolysin", "Pinealon": "pinealon",
    "Cortagen": "cortagen", "Epithalon": "epithalon",
    "SS-31 (Elamipretide)": "ss-31", "MOTS-c": "mots-c", "Humanin": "humanin",
    "NAD+": "nad", "Thymalin": "thymalin", "Thymosin Alpha-1": "thymosin alpha",
    "Thymosin Beta-4 (TB-4)": "thymosin beta-4", "Thymogen": "thymogen",
    "Thymulin": "thymulin", "LL-37": "ll-37", "KPV": "kpv",
    "Oxytocin": "oxytocin", "Kisspeptin-10": "kisspeptin",
    "Gonadorelin": "gonadorelin",
    "VIP (Vasoactive Intestinal Peptide)": "vip vasoactive",
}

def parse_price(val):
    try:
        v = float(str(val).replace(",","").replace("$","").strip())
        return v if 1.0 < v < 10000 else None
    except Exception:
        return None

def best_match(products, keyword):
    kw = keyword.lower()
    scored = []
    for p in products:
        title = (p.get("title") or p.get("name") or "").lower()
        score = sum(1 for w in kw.split() if w in title)
        if score > 0:
            scored.append((score, p))
    if not scored:
        return None
    best = sorted(scored, key=lambda x: x[0], reverse=True)[0][1]
    price = (best.get("price") or best.get("regular_price") or best.get("sale_price")
             or (best.get("variants") or [{}])[0].get("price"))
    return parse_price(price)

def scrape_shopify(base, keyword):
    url = f"{base}/products.json?q={requests.utils.quote(keyword)}&limit=10"
    try:
        resp = scraper_get(url)
        if resp.status_code == 200:
            return best_match(resp.json().get("products", []), keyword)
    except Exception:
        pass
    return None

def scrape_woocommerce(base, keyword):
    # Try WooCommerce REST API
    try:
        url = f"{base}/wp-json/wc/v3/products?search={requests.utils.quote(keyword)}&per_page=5"
        resp = scraper_get(url)
        if resp.status_code == 200:
            products = resp.json()
            if isinstance(products, list) and products:
                price = best_match(products, keyword)
                if price:
                    return price
    except Exception:
        pass

    # Fallback: search page with JS rendering
    try:
        url = f"{base}/?s={requests.utils.quote(keyword)}&post_type=product"
        resp = scraper_get(url, render_js=True)
        if resp.status_code != 200:
            return None
        html = resp.text

        # JSON-LD schema
        for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        if isinstance(offers, list): offers = offers[0]
                        p = parse_price(offers.get("price") or offers.get("lowPrice"))
                        if p: return p
            except Exception:
                pass

        # Price spans
        for raw in re.findall(r'class="[^"]*amount[^"]*"[^>]*>\s*\$?([\d,]+\.?\d*)', html):
            p = parse_price(raw)
            if p: return p

    except Exception:
        pass
    return None

def fetch_vendor_price(vendor_id, peptide):
    cfg = VENDORS.get(vendor_id)
    if not cfg: return None
    keyword = SEARCH_ALIASES.get(peptide, peptide.lower())
    try:
        price = scrape_shopify(cfg["base"], keyword) if cfg["type"] == "shopify" else scrape_woocommerce(cfg["base"], keyword)
        log.info(f"  {'OK' if price else '--'} {vendor_id}/{peptide}: {'${:.2f}'.format(price) if price else 'not found'}")
        return price
    except Exception as e:
        log.warning(f"  ERR {vendor_id}/{peptide}: {e}")
        return None

def github_get_file():
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]

def github_push_file(content, sha, message):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    requests.put(url,
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"},
        json={"message": message, "content": base64.b64encode(content.encode()).decode(), "sha": sha, "branch": "main"}
    ).raise_for_status()
    log.info(f"Pushed: {message}")

def patch_prices(html, updates):
    patched = 0
    for peptide, vendor_prices in updates.items():
        m = re.search(rf'"({re.escape(peptide)})":\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)\}}', html, re.DOTALL)
        if not m: continue
        bs, be = m.start(), m.end()
        block = html[bs:be]
        for vid, price in vendor_prices.items():
            new, n = re.subn(rf'({re.escape(vid)}:\{{price:)[\d]+\.[\d]{{1,2}}(,)', rf'\g<1>{price:.2f}\2', block)
            if n: block = new; patched += 1
        html = html[:bs] + block + html[be:]
    log.info(f"Patched {patched} prices")
    return html

def main():
    log.info("=== PepsTracker Scraper (ScraperAPI) Starting ===")
    html, sha = github_get_file()

    existing = {}
    for m in re.finditer(r'"([^"]+)":\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', html, re.DOTALL):
        vids = re.findall(r'(\w+):\{price:', m.group(2))
        if vids: existing[m.group(1)] = vids

    if not existing:
        log.error("Could not parse PRICES — aborting"); return

    priority = ["Semaglutide","Tirzepatide","Retatrutide","Liraglutide",
                "BPC-157","TB-500","BPC-157 + TB-500 Blend",
                "CJC-1295 (with DAC)","Ipamorelin","Epithalon",
                "Melanotan II","PT-141 (Bremelanotide)","GHK-Cu"]
    all_p = priority + [p for p in existing if p not in priority]
    hour = datetime.now(timezone.utc).hour
    size = 12
    start = (hour * size) % len(all_p)
    batch = (all_p * 2)[start:start + size]
    log.info(f"Scraping batch of {len(batch)} peptides")

    updates = {}
    for peptide in batch:
        for vendor_id in existing.get(peptide, []):
            if vendor_id not in VENDORS: continue
            price = fetch_vendor_price(vendor_id, peptide)
            if price: updates.setdefault(peptide, {})[vendor_id] = price
            time.sleep(2.0)  # ScraperAPI handles rate limiting but be polite

    if not updates:
        log.info("No price updates found"); return

    new_html = patch_prices(html, updates)
    if new_html == html:
        log.info("No HTML changes"); return

    count = sum(len(v) for v in updates.values())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    github_push_file(new_html, sha, f"🤖 Auto-update prices: {count} changes ({now})")
    log.info(f"=== Done: {count} prices updated ===")

if __name__ == "__main__":
    main()
