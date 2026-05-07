"""
PepsTracker Price Scraper — ScraperAPI Edition v3
Correctly parses mg:5 format from index.html and matches exact mg size.
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

def scraper_get(url, render_js=False, timeout=45):
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
    "Dihexa": "dihexa", "Epithalon": "epithalon",
    "SS-31 (Elamipretide)": "ss-31", "MOTS-c": "mots-c", "Humanin": "humanin",
    "NAD+": "nad", "Thymalin": "thymalin", "Thymosin Alpha-1": "thymosin alpha",
    "Thymosin Beta-4 (TB-4)": "thymosin beta-4", "Thymulin": "thymulin",
    "LL-37": "ll-37", "KPV": "kpv", "Oxytocin": "oxytocin",
    "Kisspeptin-10": "kisspeptin", "Gonadorelin": "gonadorelin",
    "VIP (Vasoactive Intestinal Peptide)": "vip vasoactive",
    "Cortagen": "cortagen", "DSIP (Delta Sleep Inducing Peptide)": "dsip",
    "P21": "p21", "Thymogen": "thymogen",
}

def parse_price(val):
    try:
        v = float(str(val).replace(",", "").replace("$", "").strip())
        return v if 1.0 < v < 10000 else None
    except Exception:
        return None

def mg_matches(text, target_mg):
    """Check if a product title/option contains the target mg amount."""
    if target_mg is None:
        return False
    text = str(text).lower().replace(" ", "")
    # Build patterns: 5mg, 5.0mg, 500mg etc
    target = float(target_mg)
    patterns = [
        f"{int(target)}mg",
        f"{target}mg",
        f"{int(target)}mcg",
        f"{target}mcg",
    ]
    return any(p in text for p in patterns)

def price_from_product(product, target_mg=None):
    """Extract price from a product, preferring the variant that matches target_mg."""
    # Shopify variants
    variants = product.get("variants") or []
    if variants:
        if target_mg is not None:
            for v in variants:
                opts = " ".join([
                    str(v.get("option1") or ""),
                    str(v.get("option2") or ""),
                    str(v.get("option3") or ""),
                    str(v.get("title") or ""),
                ])
                if mg_matches(opts, target_mg):
                    p = parse_price(v.get("price"))
                    if p:
                        log.info(f"    Variant match '{v.get('title')}' → ${p}")
                        return p
        # No match or no target — return cheapest variant
        prices = [parse_price(v.get("price")) for v in variants]
        prices = [p for p in prices if p]
        return min(prices) if prices else None

    # WooCommerce simple
    for field in ("sale_price", "price", "regular_price"):
        p = parse_price(product.get(field))
        if p:
            return p
    return None

def best_product_match(products, keyword, target_mg=None):
    """Score products by keyword relevance, return price from best match."""
    kw_words = keyword.lower().split()
    scored = []
    for p in products:
        title = (p.get("title") or p.get("name") or "").lower()
        score = sum(1 for w in kw_words if w in title)
        if score > 0:
            scored.append((score, p))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score = scored[0][0]
    candidates = [p for s, p in scored if s == top_score]

    # Among equally-scored candidates, prefer one whose title contains target_mg
    if target_mg is not None and len(candidates) > 1:
        for c in candidates:
            title = (c.get("title") or c.get("name") or "").lower()
            if mg_matches(title, target_mg):
                return price_from_product(c, target_mg)

    return price_from_product(candidates[0], target_mg)

def scrape_shopify(base, keyword, target_mg=None):
    url = f"{base}/products.json?q={requests.utils.quote(keyword)}&limit=10"
    try:
        resp = scraper_get(url)
        if resp.status_code == 200:
            products = resp.json().get("products", [])
            if products:
                return best_product_match(products, keyword, target_mg)
    except Exception as e:
        log.warning(f"    Shopify error: {e}")
    return None

def scrape_woocommerce(base, keyword, target_mg=None):
    # WooCommerce REST API
    try:
        url = f"{base}/wp-json/wc/v3/products?search={requests.utils.quote(keyword)}&per_page=5&status=publish"
        resp = scraper_get(url)
        if resp.status_code == 200:
            products = resp.json()
            if isinstance(products, list) and products:
                price = best_product_match(products, keyword, target_mg)
                if price:
                    return price
    except Exception:
        pass

    # Rendered search page fallback
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
                        if isinstance(offers, list):
                            if target_mg:
                                for offer in offers:
                                    if mg_matches(offer.get("name", ""), target_mg):
                                        p = parse_price(offer.get("price") or offer.get("lowPrice"))
                                        if p:
                                            return p
                            prices = [parse_price(o.get("price") or o.get("lowPrice")) for o in offers]
                            prices = [p for p in prices if p]
                            if prices:
                                return min(prices)
                        else:
                            p = parse_price(offers.get("price") or offers.get("lowPrice"))
                            if p:
                                return p
            except Exception:
                pass

        # Price span fallback
        for raw in re.findall(r'class="[^"]*(?:price|amount)[^"]*"[^>]*>\s*\$?([\d,]+\.?\d*)', html):
            p = parse_price(raw)
            if p:
                return p
    except Exception as e:
        log.warning(f"    WooCommerce fallback error: {e}")
    return None

def fetch_vendor_price(vendor_id, peptide, target_mg=None):
    cfg = VENDORS.get(vendor_id)
    if not cfg:
        return None
    keyword = SEARCH_ALIASES.get(peptide, peptide.lower())
    mg_str = f"{int(target_mg)}mg" if target_mg else "any"
    log.info(f"  Fetching {vendor_id}/{peptide} (want: {mg_str})")
    try:
        if cfg["type"] == "shopify":
            price = scrape_shopify(cfg["base"], keyword, target_mg)
        else:
            price = scrape_woocommerce(cfg["base"], keyword, target_mg)
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
        json={"message": message,
              "content": base64.b64encode(content.encode()).decode(),
              "sha": sha, "branch": "main"}
    ).raise_for_status()
    log.info(f"Pushed: {message}")

def parse_prices_block(html):
    """
    Parse PRICES const from index.html.
    Format: "Peptide": { vendor: {price:65.00, mg:5, listing:"..."}, ... }
    Returns: { peptide: { vendor_id: {"price": float, "mg": float} } }
    """
    result = {}
    # Find each peptide block
    pep_re = re.compile(r'"([^"]+)":\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
    # Match vendor entries: vendorid:{price:65.00,mg:5,listing:"..."}  OR  vendorid:null
    vendor_re = re.compile(
        r'(\w+):\s*(?:null|\{[^}]*price\s*:\s*([\d.]+)[^}]*mg\s*:\s*([\d.]+)[^}]*\})',
        re.DOTALL
    )
    for m in pep_re.finditer(html):
        peptide = m.group(1)
        block = m.group(2)
        vendors = {}
        for vm in vendor_re.finditer(block):
            vid = vm.group(1)
            if vm.group(2) is None:
                continue  # null entry, skip
            price = float(vm.group(2))
            mg = float(vm.group(3))
            vendors[vid] = {"price": price, "mg": mg}
        if vendors:
            result[peptide] = vendors
    return result

def patch_prices(html, updates):
    """
    updates: { peptide: { vendor_id: new_price_float } }
    Patches price values in the JS PRICES const.
    """
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
    log.info("=== PepsTracker Scraper v3 (mg-aware) Starting ===")
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
        "GHK-Cu", "CJC-1295 (with DAC)", "Liraglutide",
    ]
    all_p = priority + [p for p in existing if p not in priority]
    hour = datetime.now(timezone.utc).hour
    batch_size = 12
    start = (hour * batch_size) % max(len(all_p), 1)
    batch = (all_p * 2)[start:start + batch_size]
    for p in priority:
        if p not in batch and p in existing:
            batch.append(p)
    batch = list(dict.fromkeys(batch))
    log.info(f"Scraping {len(batch)} peptides this run")

    updates = {}
    for peptide in batch:
        vendor_map = existing.get(peptide, {})
        for vid, info in vendor_map.items():
            if vid not in VENDORS:
                continue
            target_mg = info.get("mg")  # e.g. 5 (a number)
            price = fetch_vendor_price(vid, peptide, target_mg)
            if price:
                if abs(price - info["price"]) > 0.01:
                    updates.setdefault(peptide, {})[vid] = price
                    log.info(f"  CHANGE {peptide}/{vid}: ${info['price']:.2f} → ${price:.2f}")
                else:
                    log.info(f"  SAME   {peptide}/{vid}: ${price:.2f}")
            time.sleep(2.0)

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
