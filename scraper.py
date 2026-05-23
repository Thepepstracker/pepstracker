"""
PepsTracker Price Scraper — Direct URL Edition (v5)
Fixes: ignores related product prices, detects out of stock.
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

PRODUCT_URLS = {
  "ascension": {
    "Semaglutide":            {"url": "https://ascensionpeptides.com/product/s-5/",               "mg": 5},
    "Tirzepatide":            {"url": "https://ascensionpeptides.com/product/t-10/",              "mg": 10},
    "Retatrutide":            {"url": "https://ascensionpeptides.com/product/t-10/",              "mg": 10},
    "BPC-157":                {"url": "https://ascensionpeptides.com/product/bpc-157-5mg/",       "mg": 5},
    "TB-500":                 {"url": "https://ascensionpeptides.com/product/tb-500-5mg/",        "mg": 5},
    "BPC-157 + TB-500 Blend": {"url": "https://ascensionpeptides.com/product/wolverine-stack/",   "mg": 20},
    "Ipamorelin":             {"url": "https://ascensionpeptides.com/product/ipamorelin-5mg/",    "mg": 5},
    "Epithalon":              {"url": "https://ascensionpeptides.com/product/epithalon-10mg/",    "mg": 10},
    "Melanotan II":           {"url": "https://ascensionpeptides.com/product/melanotan-ii-10mg/", "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://ascensionpeptides.com/product/pt-141-10mg/",      "mg": 10},
    "GHK-Cu":                 {"url": "https://ascensionpeptides.com/product/ghk-cu-100mg/",     "mg": 100},
  },
  "lapeptides": {
    "Semaglutide":            {"url": "https://lapeptides.net/product/g-1-s/",            "mg": 5},
    "Tirzepatide":            {"url": "https://lapeptides.net/product/g-2/",              "mg": 15},
    "Retatrutide":            {"url": "https://lapeptides.net/product/g-3/",              "mg": 10},
    "BPC-157":                {"url": "https://lapeptides.net/product/bpc-157/",          "mg": 10},
    "TB-500":                 {"url": "https://lapeptides.net/product/tb500/",            "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://lapeptides.net/product/bpc-tb500-blend/", "mg": 10},
    "Ipamorelin":             {"url": "https://lapeptides.net/product/ipamorelin/",       "mg": 10},
    "Epithalon":              {"url": "https://lapeptides.net/product/epithalon/",        "mg": 50},
    "Melanotan II":           {"url": "https://lapeptides.net/product/melanotan-2/",      "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://lapeptides.net/product/pt-141/",          "mg": 10},
    "GHK-Cu":                 {"url": "https://lapeptides.net/product/ghk-cu/",          "mg": 100},
  },
  "glacier": {
    "Semaglutide":            {"url": "https://glacieraminos.shop/product/gla1-s/",                "mg": 15},
    "Tirzepatide":            {"url": "https://glacieraminos.shop/product/gla2-trz/",              "mg": 10},
    "Retatrutide":            {"url": "https://glacieraminos.shop/product/gla3-rt/",               "mg": 10},
    "BPC-157":                {"url": "https://glacieraminos.shop/product/bpc-157/",               "mg": 10},
    "TB-500":                 {"url": "https://glacieraminos.shop/product/tb500/",                 "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://glacieraminos.shop/product/bpc-tb-500-wolverine/", "mg": 10},
    "Ipamorelin":             {"url": "https://glacieraminos.shop/product/ipamorelin-10mg/",       "mg": 10},
    "CJC-1295 (with DAC)":    {"url": "https://glacieraminos.shop/product/cjc-1295-w-dac-5mg/",   "mg": 5},
    "Epithalon":              {"url": "https://glacieraminos.shop/product/epi10/",                 "mg": 10},
    "Melanotan II":           {"url": "https://glacieraminos.shop/product/mt-2/",                  "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://glacieraminos.shop/product/pt-141/",               "mg": 10},
    "GHK-Cu":                 {"url": "https://glacieraminos.shop/product/ghk-cu/",               "mg": 50},
  },
  "milehigh": {
    "Semaglutide":            {"url": "https://milehighcompounds.is/product/mhc-1-sm/",                "mg": 10},
    "Tirzepatide":            {"url": "https://milehighcompounds.is/product/mhc-2-trz/",               "mg": 10},
    "Retatrutide":            {"url": "https://milehighcompounds.is/product/mhc-3-rt/",                "mg": 10},
    "BPC-157":                {"url": "https://milehighcompounds.is/product/bpc-157/",                 "mg": 10},
    "TB-500":                 {"url": "https://milehighcompounds.is/product/tb-500/",                  "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://milehighcompounds.is/product/bpc-157-tb-500-blend/",   "mg": 20},
    "Ipamorelin":             {"url": "https://milehighcompounds.is/product/ipamorelin/",              "mg": 10},
    "CJC-1295 (with DAC)":    {"url": "https://milehighcompounds.is/product/cjc-1295-w-dac/",         "mg": 5},
    "Epithalon":              {"url": "https://milehighcompounds.is/product/epithalon/",               "mg": 50},
    "Melanotan II":           {"url": "https://milehighcompounds.is/product/mt-2/",                    "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://milehighcompounds.is/product/pt-141/",                 "mg": 10},
    "GHK-Cu":                 {"url": "https://milehighcompounds.is/product/ghk-cu/",                 "mg": 50},
  },
  "ezpeptides": {
    "Semaglutide":            {"url": "https://ezpeptides.com/product/ezp-1p-10mg/",                  "mg": 10},
    "Tirzepatide":            {"url": "https://ezpeptides.com/product/ezp-2p-10mg/",                  "mg": 10},
    "Retatrutide":            {"url": "https://ezpeptides.com/product/ezp-3p-10mg-glp-3rt/",          "mg": 10},
    "BPC-157":                {"url": "https://ezpeptides.com/product/bpc-157-10mg/",                 "mg": 10},
    "TB-500":                 {"url": "https://ezpeptides.com/product/tb4-10mg/",                     "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://ezpeptides.com/product/bpc-157-tb4-blend-10mg-10mg/", "mg": 10},
    "Ipamorelin":             {"url": "https://ezpeptides.com/product/ipamorelin-10mg/",              "mg": 10},
    "Epithalon":              {"url": "https://ezpeptides.com/product/epitalon-10mg/",                "mg": 10},
    "Melanotan II":           {"url": "https://ezpeptides.com/product/melanotan-ii-10mg/",            "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://ezpeptides.com/product/pt-141-10mg/",                 "mg": 10},
    "GHK-Cu":                 {"url": "https://ezpeptides.com/product/ghk-cu-50mg/",                 "mg": 50},
  },
  "amp": {
    "Semaglutide":            {"url": "https://ameanopeptides.com/product/amp-1p-5mg/",                   "mg": 5},
    "Tirzepatide":            {"url": "https://ameanopeptides.com/product/amp-2p-10mg/",                  "mg": 10},
    "Retatrutide":            {"url": "https://ameanopeptides.com/product/amp-3p-10mg/",                  "mg": 10},
    "BPC-157":                {"url": "https://ameanopeptides.com/product/bpc-157-10mg/",                 "mg": 10},
    "TB-500":                 {"url": "https://ameanopeptides.com/product/tb4-10mg-research-peptide/",    "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://ameanopeptides.com/product/bpc-157-tb4-blend-10mg-10mg/", "mg": 10},
    "Ipamorelin":             {"url": "https://ameanopeptides.com/product/ipamorelin-10mg/",              "mg": 10},
    "Epithalon":              {"url": "https://ameanopeptides.com/product/epitalon-10mg/",                "mg": 10},
    "Melanotan II":           {"url": "https://ameanopeptides.com/product/melanotan-ii-10mg/",            "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://ameanopeptides.com/product/pt-141-10mg-research-peptide/","mg": 10},
    "GHK-Cu":                 {"url": "https://ameanopeptides.com/product/ghk-cu-100mg/",                "mg": 100},
  },
  "labsourced": {
    "Tirzepatide":            {"url": "https://www.labsourced.com/products/tirzepatide-30mg",   "mg": 30},
    "Retatrutide":            {"url": "https://www.labsourced.com/products/peptide-r-5mg",      "mg": 5},
    "BPC-157":                {"url": "https://www.labsourced.com/products/bpc-157-10mg",       "mg": 10},
    "TB-500":                 {"url": "https://www.labsourced.com/products/tb-500-10mg",        "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://www.labsourced.com/products/wolverine-10-10mg", "mg": 10},
    "Ipamorelin":             {"url": "https://www.labsourced.com/products/ipamorelin-10mg",    "mg": 10},
    "Epithalon":              {"url": "https://www.labsourced.com/products/epithalon-10mg",     "mg": 10},
    "Melanotan II":           {"url": "https://www.labsourced.com/products/mt2-10mg",           "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://www.labsourced.com/products/pt-141-10mg",       "mg": 10},
    "GHK-Cu":                 {"url": "https://www.labsourced.com/products/ghk-cu-50mg",       "mg": 50},
  },
  "ion": {
    "Semaglutide":            {"url": "https://ionpeptide.com/product/glp-1s/",                "mg": 5},
    "Tirzepatide":            {"url": "https://ionpeptide.com/product/glp-2t/",                "mg": 10},
    "Retatrutide":            {"url": "https://ionpeptide.com/product/glp-3r/",                "mg": 5},
    "BPC-157":                {"url": "https://ionpeptide.com/product/bpc-157-2/",             "mg": 5},
    "TB-500":                 {"url": "https://ionpeptide.com/product/tb-500/",                "mg": 5},
    "BPC-157 + TB-500 Blend": {"url": "https://ionpeptide.com/product/bpc157tb500/",          "mg": 10},
    "Ipamorelin":             {"url": "https://ionpeptide.com/product/ipamorelin/",            "mg": 5},
    "CJC-1295 (with DAC)":    {"url": "https://ionpeptide.com/product/cjc-1295-with-dac-5mg/","mg": 5},
    "Epithalon":              {"url": "https://ionpeptide.com/product/epithalon/",             "mg": 10},
    "Melanotan II":           {"url": "https://ionpeptide.com/product/melanotan-ii/",          "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://ionpeptide.com/product/pt-141/",               "mg": 10},
    "GHK-Cu":                 {"url": "https://ionpeptide.com/product/ghk-cu-2/",             "mg": 50},
  },
  "retaone": {
    "Semaglutide":            {"url": "https://retaonelabs.com/product/ro-1s-10mg/",                       "mg": 10},
    "Tirzepatide":            {"url": "https://retaonelabs.com/product/ro-2t-10mg/",                       "mg": 10},
    "Retatrutide":            {"url": "https://retaonelabs.com/product/ro-3r-10mg/",                       "mg": 10},
    "BPC-157":                {"url": "https://retaonelabs.com/product/bpc-157-10mg/",                     "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://retaonelabs.com/product/bpc-157-tb-500-blend-10mg-10mg/",  "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://retaonelabs.com/product/pt-141-10mg/",                     "mg": 10},
    "GHK-Cu":                 {"url": "https://retaonelabs.com/product/ghk-cu-50mg/",                     "mg": 50},
  },
  "nura": {
    "Semaglutide":            {"url": "https://nurapeptide.com/product/glp-1sg-10mg/",               "mg": 10},
    "Tirzepatide":            {"url": "https://nurapeptide.com/product/glp-2t-10mg/",                "mg": 10},
    "Retatrutide":            {"url": "https://nurapeptide.com/product/glp-3rt-12mg/",               "mg": 12},
    "BPC-157":                {"url": "https://nurapeptide.com/product/bpc-157-10mg/",               "mg": 10},
    "TB-500":                 {"url": "https://nurapeptide.com/product/tb-500-10mg/",                "mg": 10},
    "BPC-157 + TB-500 Blend": {"url": "https://nurapeptide.com/product/bpc-157-tb-500-5-5mg/",      "mg": 5},
    "Ipamorelin":             {"url": "https://nurapeptide.com/product/ipamorelin-10mg/",            "mg": 10},
    "CJC-1295 (with DAC)":    {"url": "https://nurapeptide.com/product/cjc-1295-with-dac-5mg/",     "mg": 5},
    "Epithalon":              {"url": "https://nurapeptide.com/product/epitalon-10mg/",              "mg": 10},
    "Melanotan II":           {"url": "https://nurapeptide.com/product/melanotan-ii-10mg/",          "mg": 10},
    "PT-141 (Bremelanotide)": {"url": "https://nurapeptide.com/product/pt-141-peptide-10mg/",       "mg": 10},
    "GHK-Cu":                 {"url": "https://nurapeptide.com/product/ghk-cu-100mg/",              "mg": 100},
  },
  "atomik": {},
}

def scraper_get(url, render_js=False, timeout=45):
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "render": "true" if render_js else "false",
        "keep_headers": "true",
    }
    return requests.get("https://api.scraperapi.com/", params=params, timeout=timeout)

def parse_price(val):
    try:
        v = float(str(val).replace(",", "").replace("$", "").strip())
        return v if 1.0 < v < 10000 else None
    except Exception:
        return None

def is_out_of_stock(html):
    """Check if page indicates product is out of stock."""
    oos_signals = [
        'class="out-of-stock"',
        'stock_status":"outofstock"',
        '"availability":"http://schema.org/OutOfStock"',
        'availability":"OutOfStock"',
        '>Out of stock<',
        '>Currently unavailable<',
        '>Sold out<',
        'sold_out":true',
        '"sold_out": true',
    ]
    html_lower = html.lower()
    for signal in oos_signals:
        if signal.lower() in html_lower:
            return True
    return False

def extract_main_product_price(html):
    """
    Extract ONLY the main product price — ignoring related products,
    upsells, cross-sells, and bundle sections.
    """

    # Step 1: Strip banners, notices, shipping promo text, related sections
    trimmed_html = html

    # Remove free shipping banners (e.g. "Free shipping on orders over $200")
    trimmed_html = re.sub(
        r'[^<]{0,80}free\s*ship[^<]{0,150}\$\s*[\d,]+\.?\d*[^<]{0,80}',
        '', trimmed_html, flags=re.IGNORECASE
    )
    trimmed_html = re.sub(
        r'\$\s*[\d,]+\.?\d*[^<]{0,80}free\s*ship[^<]{0,150}',
        '', trimmed_html, flags=re.IGNORECASE
    )
    # Remove promo/notice bar elements
    trimmed_html = re.sub(
        r'<[^>]+class="[^"]*(?:store-notice|announcement|promo-bar|free-ship)[^"]*"[^>]*>.*?</[a-z]+>',
        '', trimmed_html, flags=re.DOTALL | re.IGNORECASE
    )

    # Cut off at related/upsell sections
    cutoff_patterns = [
        r'<section[^>]*class="[^"]*related[^"]*"',
        r'<div[^>]*class="[^"]*related[^"]*"',
        r'<section[^>]*class="[^"]*upsell[^"]*"',
        r'<div[^>]*class="[^"]*upsell[^"]*"',
        r'<div[^>]*class="[^"]*cross-sell[^"]*"',
        r'id="related[^"]*"',
        r'class="[^"]*product-recommendations[^"]*"',
    ]
    for pattern in cutoff_patterns:
        m = re.search(pattern, trimmed_html, re.IGNORECASE)
        if m:
            trimmed_html = trimmed_html[:m.start()]

    # Step 2: Try JSON-LD on trimmed HTML first
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', trimmed_html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Product":
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        prices = [parse_price(o.get("price") or o.get("lowPrice")) for o in offers]
                        prices = [p for p in prices if p]
                        if prices:
                            return min(prices)  # return lowest (base) price
                    else:
                        p = parse_price(offers.get("price") or offers.get("lowPrice"))
                        if p:
                            return p
        except Exception:
            pass

    # Step 3: WooCommerce price — look for the FIRST price only
    # Target the summary/main product div specifically
    summary_match = re.search(
        r'<div[^>]*class="[^"]*(?:summary|product-summary|entry-summary)[^"]*"[^>]*>(.*?)</div>\s*</div>',
        trimmed_html, re.DOTALL | re.IGNORECASE
    )
    search_area = summary_match.group(1) if summary_match else trimmed_html

    # Find first price in the summary area
    price_patterns = [
        r'class="woocommerce-Price-amount[^"]*"[^>]*>.*?<bdi>.*?\$\s*([\d,]+\.?\d*)',
        r'<ins>.*?<bdi>.*?\$\s*([\d,]+\.?\d*)',  # sale price
        r'"price"\s*:\s*"([\d.]+)"',
        r'<p[^>]*class="[^"]*price[^"]*"[^>]*>.*?\$\s*([\d,]+\.?\d*)',
    ]
    for pattern in price_patterns:
        matches = re.findall(pattern, search_area, re.DOTALL)
        for raw in matches:
            p = parse_price(raw)
            if p:
                return p

    # Step 4: Shopify — product JSON in page
    for pattern in [
        r'"price"\s*:\s*(\d+)',           # price in cents
        r'"price":\s*"([\d.]+)"',         # price as string
        r'window\.ShopifyAnalytics.*?"price":"([\d.]+)"',
    ]:
        m = re.search(pattern, trimmed_html)
        if m:
            val = float(m.group(1))
            # Shopify stores price in cents
            if val > 1000:
                val = val / 100
            p = parse_price(val)
            if p:
                return p

    return None

def fetch_price_from_url(vendor_id, peptide, product_url):
    """Fetch price directly from a known product URL."""
    log.info(f"  Fetching {vendor_id}/{peptide} → {product_url}")
    try:
        # Try without JS first (faster)
        resp = scraper_get(product_url, render_js=False)
        if resp.status_code != 200:
            log.warning(f"  HTTP {resp.status_code}")
            return None, False

        html = resp.text

        # Check out of stock
        if is_out_of_stock(html):
            log.info(f"  OUT OF STOCK: {vendor_id}/{peptide}")
            return None, True  # (price, is_out_of_stock)

        price = extract_main_product_price(html)

        # Retry with JS if no price found
        if not price:
            log.info(f"  Retrying with JS render...")
            resp2 = scraper_get(product_url, render_js=True)
            if resp2.status_code == 200:
                html2 = resp2.text
                if is_out_of_stock(html2):
                    log.info(f"  OUT OF STOCK (JS): {vendor_id}/{peptide}")
                    return None, True
                price = extract_main_product_price(html2)

        log.info(f"  {'OK' if price else '--'} {vendor_id}/{peptide}: {'${:.2f}'.format(price) if price else 'not found'}")
        return price, False

    except Exception as e:
        log.warning(f"  ERR {vendor_id}/{peptide}: {e}")
        return None, False

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
        json={"message": message,
              "content": base64.b64encode(content.encode()).decode(),
              "sha": sha, "branch": "main"}
    ).raise_for_status()
    log.info(f"Pushed: {message}")

def parse_prices_block(html):
    result = {}
    pep_re = re.compile(r'"([^"]+)":\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
    vendor_re = re.compile(
        r'(\w+):\s*(?:null|\{[^}]*price\s*:\s*([\d.]+)[^}]*mg\s*:\s*([\d.]+)[^}]*\})',
        re.DOTALL
    )
    for m in pep_re.finditer(html):
        peptide = m.group(1)
        block = m.group(2)
        if 'price:' not in block:
            continue
        vendors = {}
        for vm in vendor_re.finditer(block):
            vid = vm.group(1)
            if vm.group(2) is None:
                continue
            vendors[vid] = {"price": float(vm.group(2)), "mg": float(vm.group(3))}
        if vendors:
            result[peptide] = vendors
    return result

def patch_prices(html, updates):
    patched = 0
    for peptide, vendor_prices in updates.items():
        pep_re = re.compile(
            rf'("{re.escape(peptide)}":\s*\{{)(.*?)(\n  \}},?\n)',
            re.DOTALL
        )
        m = pep_re.search(html)
        if not m:
            log.warning(f"  Block not found for: {peptide}")
            continue
        block = m.group(2)
        new_block = block
        for vid, price in vendor_prices.items():
            new_block, n = re.subn(
                rf'({re.escape(vid)}:\{{price:)([\d.]+)(,mg:)',
                rf'\g<1>{price:.2f}\3',
                new_block
            )
            if n:
                patched += 1
            else:
                log.warning(f"  Could not patch {vid}/{peptide}")
        html = html[:m.start(2)] + new_block + html[m.end(2):]
    log.info(f"Patched {patched} prices")
    return html, patched

def main():
    log.info("=== PepsTracker Scraper v5 (out-of-stock aware) Starting ===")
    html, sha = github_get_file()

    existing = parse_prices_block(html)
    if not existing:
        log.error("Could not parse PRICES block — aborting")
        return
    log.info(f"Parsed {len(existing)} peptides from PRICES block")

    priority = [
        "Semaglutide", "Tirzepatide", "Retatrutide",
        "BPC-157", "TB-500", "Ipamorelin",
        "Epithalon", "Melanotan II", "PT-141 (Bremelanotide)",
        "GHK-Cu", "CJC-1295 (with DAC)", "BPC-157 + TB-500 Blend",
    ]
    all_p = priority + [p for p in existing if p not in priority]
    hour = datetime.now(timezone.utc).hour
    batch_size = 6
    start = (hour * batch_size) % max(len(all_p) - len(priority), 1)
    extra = [p for p in all_p if p not in priority][start:start + batch_size]
    batch = list(dict.fromkeys(priority + extra))
    log.info(f"Scraping {len(batch)} peptides this run")

    updates = {}
    out_of_stock = []

    for peptide in batch:
        vendor_map = existing.get(peptide, {})
        for vid, info in vendor_map.items():
            url_info = PRODUCT_URLS.get(vid, {}).get(peptide)
            if not url_info:
                continue

            price, oos = fetch_price_from_url(vid, peptide, url_info["url"])

            if oos:
                out_of_stock.append(f"{vid}/{peptide}")
                # Don't update price — leave existing price unchanged
            elif price:
                if abs(price - info["price"]) > 0.01:
                    updates.setdefault(peptide, {})[vid] = price
                    log.info(f"  CHANGE {peptide}/{vid}: ${info['price']:.2f} → ${price:.2f}")
                else:
                    log.info(f"  SAME   {peptide}/{vid}: ${price:.2f}")
            time.sleep(1.5)

    if out_of_stock:
        log.info(f"Out of stock items ({len(out_of_stock)}): {', '.join(out_of_stock)}")

    if not updates:
        log.info("No price changes — skipping commit")
        return

    new_html, count = patch_prices(html, updates)
    if count == 0:
        log.info("Patch produced no changes — skipping commit")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    github_push_file(new_html, sha, f"🤖 Auto-update prices: {count} changes ({now})")
    log.info(f"=== Done: {count} prices updated ===")

if __name__ == "__main__":
    main()
