"""
PepsTracker Price Scraper
Scrapes peptide prices from vendor sites and updates index.html in GitHub.
Runs hourly via GitHub Actions.
"""

import os, re, json, time, base64, logging
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = "Thepepstracker/pepstracker"
GITHUB_FILE  = "pepstracker_fixed/index.html"
GITHUB_API   = "https://api.github.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ─── Vendor scraper configs ─────────────────────────────────────────────────

VENDORS = {
    "ascension": {
        "base":   "https://ascensionpeptides.com",
        "search": "https://ascensionpeptides.com/?s={query}",
        "type":   "woocommerce",
    },
    "lapeptides": {
        "base":   "https://lapeptides.net",
        "search": "https://lapeptides.net/?s={query}",
        "type":   "woocommerce",
    },
    "glacier": {
        "base":   "https://glacieraminos.shop",
        "search": "https://glacieraminos.shop/?s={query}",
        "type":   "woocommerce",
    },
    "milehigh": {
        "base":   "https://milehighcompounds.is",
        "search": "https://milehighcompounds.is/?s={query}",
        "type":   "woocommerce",
    },
    "ezpeptides": {
        "base":   "https://ezpeptides.com",
        "search": "https://ezpeptides.com/?s={query}",
        "type":   "woocommerce",
    },
    "amp": {
        "base":   "https://ameanopeptides.com",
        "search": "https://ameanopeptides.com/?s={query}",
        "type":   "woocommerce",
    },
    "labsourced": {
        "base":   "https://labsourced.com",
        "search": "https://labsourced.com/?s={query}",
        "type":   "woocommerce",
    },
    "ion": {
        "base":   "https://ionpeptide.com",
        "search": "https://ionpeptide.com/?s={query}",
        "type":   "woocommerce",
    },
    "retaone": {
        "base":   "https://retaonelabs.com",
        "search": "https://retaonelabs.com/?s={query}",
        "type":   "woocommerce",
    },
    "nura": {
        "base":   "https://nurapeptide.com",
        "search": "https://nurapeptide.com/?s={query}",
        "type":   "woocommerce",
    },
    "atomik": {
        "base":   "https://affiliatepirate.com",
        "search": None,   # Affiliate platform — scrape their catalog page directly
        "catalog":"https://atomiklabz.com/?s={query}",
        "type":   "woocommerce",
    },
}

# Maps peptide name → search keywords per vendor (when name alone isn't enough)
SEARCH_ALIASES = {
    "Semaglutide":                   ["semaglutide", "sema"],
    "Tirzepatide":                   ["tirzepatide", "tirz"],
    "Retatrutide":                   ["retatrutide", "reta"],
    "Liraglutide":                   ["liraglutide"],
    "BPC-157":                       ["bpc-157", "bpc157"],
    "BPC-157 (Oral)":                ["bpc-157 oral", "oral bpc"],
    "TB-500":                        ["tb-500", "tb500", "thymosin beta"],
    "TB-500 Fragment (17-23)":       ["tb-500 fragment", "tb-4 frag"],
    "BPC-157 + TB-500 Blend":        ["bpc tb blend", "bpc+tb"],
    "CJC-1295 (with DAC)":           ["cjc-1295 dac", "cjc dac"],
    "CJC-1295 (no DAC) / Mod GRF 1-29": ["cjc-1295 no dac", "mod grf"],
    "Ipamorelin":                    ["ipamorelin"],
    "Hexarelin":                     ["hexarelin"],
    "GHRP-2":                        ["ghrp-2", "ghrp2"],
    "GHRP-6":                        ["ghrp-6", "ghrp6"],
    "Sermorelin":                    ["sermorelin"],
    "Tesamorelin":                   ["tesamorelin"],
    "GHRH (1-29)":                   ["ghrh"],
    "CJC-1295 + Ipamorelin Blend":   ["cjc ipamorelin blend"],
    "IGF-1 LR3":                     ["igf-1 lr3", "igf lr3"],
    "IGF-1 DES":                     ["igf-1 des", "igf des"],
    "HGH Fragment 176-191":          ["hgh fragment", "frag 176"],
    "AOD 9604":                      ["aod 9604", "aod9604"],
    "MGF (Mechano Growth Factor)":   ["mgf"],
    "PEG-MGF":                       ["peg-mgf", "pegylated mgf"],
    "Follistatin 344":               ["follistatin"],
    "Adipotide (FTPP)":              ["adipotide", "ftpp"],
    "5-Amino-1MQ":                   ["5-amino-1mq", "5a1mq"],
    "Melanotan I (MT-1)":            ["melanotan i", "mt-1"],
    "Melanotan II":                  ["melanotan ii", "mt-2"],
    "PT-141 (Bremelanotide)":        ["pt-141", "bremelanotide"],
    "GHK-Cu":                        ["ghk-cu", "ghk cu"],
    "SNAP-8":                        ["snap-8"],
    "Leuphasyl":                     ["leuphasyl"],
    "Selank":                        ["selank"],
    "N-Acetyl Selank":               ["n-acetyl selank", "na selank"],
    "Semax":                         ["semax"],
    "N-Acetyl Semax":                ["n-acetyl semax", "na semax"],
    "Dihexa":                        ["dihexa"],
    "DSIP (Delta Sleep Inducing Peptide)": ["dsip", "delta sleep"],
    "P21":                           ["p21"],
    "Cerebrolysin":                  ["cerebrolysin"],
    "Pinealon":                      ["pinealon"],
    "Cortagen":                      ["cortagen"],
    "Epithalon":                     ["epithalon", "epithalamin"],
    "SS-31 (Elamipretide)":          ["ss-31", "elamipretide"],
    "MOTS-c":                        ["mots-c", "motsc"],
    "Humanin":                       ["humanin"],
    "NAD+":                          ["nad+", "nad"],
    "Thymalin":                      ["thymalin"],
    "Thymosin Alpha-1":              ["thymosin alpha", "ta1"],
    "Thymosin Beta-4 (TB-4)":        ["thymosin beta-4", "tb-4"],
    "Thymogen":                      ["thymogen"],
    "Thymulin":                      ["thymulin"],
    "LL-37":                         ["ll-37"],
    "KPV":                           ["kpv"],
    "Oxytocin":                      ["oxytocin"],
    "Kisspeptin-10":                 ["kisspeptin"],
    "Gonadorelin":                   ["gonadorelin"],
    "VIP (Vasoactive Intestinal Peptide)": ["vip", "vasoactive"],
}


# ─── Price extractors ────────────────────────────────────────────────────────

def extract_price_woocommerce(html: str) -> float | None:
    """Pull the first product price from a WooCommerce search results or product page."""
    soup = BeautifulSoup(html, "html.parser")

    # Try schema.org JSON-LD first (most reliable)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Product", "ItemPage"):
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0]
                    price = offers.get("price") or offers.get("lowPrice")
                    if price:
                        return float(price)
        except Exception:
            pass

    # WooCommerce price selectors (fallback)
    selectors = [
        "span.woocommerce-Price-amount bdi",
        "span.woocommerce-Price-amount",
        ".price ins span.amount",
        ".price span.amount",
        "[class*='price'] bdi",
        ".product-price",
        ".price",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            raw = el.get_text(strip=True)
            price = parse_price(raw)
            if price:
                return price
    return None


def parse_price(text: str) -> float | None:
    """Extract a dollar amount from raw text."""
    text = text.replace(",", "")
    m = re.search(r"\$?([\d]+\.[\d]{1,2})", text)
    if m:
        return float(m.group(1))
    m = re.search(r"\$?([\d]+)", text)
    if m:
        return float(m.group(1))
    return None


def fetch_vendor_price(vendor_id: str, peptide: str) -> float | None:
    """Try to scrape a price for a given peptide from one vendor."""
    cfg = VENDORS.get(vendor_id)
    if not cfg:
        return None

    aliases = SEARCH_ALIASES.get(peptide, [peptide.lower()])
    search_tpl = cfg.get("search") or cfg.get("catalog")
    if not search_tpl:
        return None

    for keyword in aliases[:2]:   # Try first two aliases only
        url = search_tpl.format(query=requests.utils.quote(keyword))
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            price = extract_price_woocommerce(resp.text)
            if price:
                log.info(f"  ✓ {vendor_id} / {peptide}: ${price:.2f}")
                return price
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"  ✗ {vendor_id} / {peptide}: {e}")
    return None


# ─── GitHub helpers ──────────────────────────────────────────────────────────

def github_get_file():
    """Fetch current index.html content + SHA from GitHub."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
    resp.raise_for_status()
    data = resp.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def github_push_file(content: str, sha: str, message: str):
    """Push updated index.html back to GitHub."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "sha": sha,
        "branch": "main",
    }
    resp = requests.put(
        url,
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"},
        json=payload,
    )
    resp.raise_for_status()
    log.info(f"✅ Pushed to GitHub: {message}")


# ─── HTML price patcher ──────────────────────────────────────────────────────

def patch_prices(html: str, updates: dict[str, dict[str, float]]) -> str:
    """
    Replace price values inside the PRICES const in index.html.

    updates = { "peptide_name": { "vendor_id": new_price, ... }, ... }
    """
    patched = 0
    for peptide, vendor_prices in updates.items():
        for vendor_id, new_price in vendor_prices.items():
            # Pattern: vendorId:{price:XX.XX,mg:...
            pattern = rf'({re.escape(vendor_id)}:{{price:)[\d]+\.[\d]{{1,2}}(,mg:\d)'
            replacement = rf'\g<1>{new_price:.2f}\2'
            new_html, n = re.subn(
                pattern,
                replacement,
                html,
                # Scope match to the peptide's block
                # We'll do a two-pass approach for safety
            )
            if n > 0:
                html = new_html
                patched += 1

    log.info(f"Patched {patched} prices in HTML")
    return html


def patch_prices_safe(html: str, updates: dict[str, dict[str, float]]) -> str:
    """
    Scope-aware price patcher. Finds each peptide block then patches within it.
    """
    patched = 0
    for peptide, vendor_prices in updates.items():
        # Find the peptide block: "PeptideName": { ... }
        block_pattern = rf'"({re.escape(peptide)})":\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)\}}'
        block_match = re.search(block_pattern, html, re.DOTALL)
        if not block_match:
            log.warning(f"Could not find block for: {peptide}")
            continue

        block_start = block_match.start()
        block_end   = block_match.end()
        block       = html[block_start:block_end]
        new_block   = block

        for vendor_id, new_price in vendor_prices.items():
            # Within the block, update the price field for this vendor
            pattern = rf'({re.escape(vendor_id)}:\{{price:)[\d]+\.[\d]{{1,2}}(,)'
            replacement = rf'\g<1>{new_price:.2f}\2'
            updated, n = re.subn(pattern, replacement, new_block)
            if n:
                new_block = updated
                patched += 1
                log.debug(f"  {peptide} / {vendor_id}: → ${new_price:.2f}")

        html = html[:block_start] + new_block + html[block_end:]

    log.info(f"Patched {patched} price fields in HTML")
    return html


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    log.info("=== PepsTracker Scraper Starting ===")

    # 1. Fetch current index.html from GitHub
    log.info("Fetching index.html from GitHub…")
    html, sha = github_get_file()

    # 2. Parse existing PRICES block to know which vendor/peptide combos exist
    #    (Only update combos where we currently have a non-null value — don't add new ones)
    existing_pattern = re.compile(
        r'"([^"]+)":\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',  # peptide block
        re.DOTALL,
    )

    # Build list of (peptide, vendor_id) pairs that have real prices
    existing_prices: dict[str, list[str]] = {}
    for m in existing_pattern.finditer(html):
        peptide = m.group(1)
        block   = m.group(2)
        vendor_ids = re.findall(r'(\w+):\{price:', block)
        if vendor_ids:
            existing_prices[peptide] = vendor_ids

    if not existing_prices:
        log.error("Could not parse existing PRICES — aborting to avoid overwrite")
        return

    log.info(f"Found {len(existing_prices)} peptides to update")

    # 3. Scrape prices
    updates: dict[str, dict[str, float]] = {}
    # Limit: only scrape the top ~10 most important peptides per run to stay fast
    # Prioritize GLP-1s and most popular
    priority = [
        "Semaglutide", "Tirzepatide", "Retatrutide", "Liraglutide",
        "BPC-157", "TB-500", "BPC-157 + TB-500 Blend",
        "CJC-1295 (with DAC)", "Ipamorelin", "Epithalon",
    ]
    # Rotate through all peptides across runs using hour-of-day as offset
    hour = datetime.now(timezone.utc).hour
    all_peptides = priority + [p for p in existing_prices if p not in priority]
    # In each run, scrape a rotating batch of 15 peptides
    batch_size = 15
    start = (hour * batch_size) % len(all_peptides)
    batch = all_peptides[start:start + batch_size]
    if len(batch) < batch_size:
        batch += all_peptides[:batch_size - len(batch)]

    log.info(f"Scraping batch of {len(batch)} peptides this run")

    for peptide in batch:
        vendor_ids = existing_prices.get(peptide, [])
        for vendor_id in vendor_ids:
            if vendor_id not in VENDORS:
                continue
            price = fetch_vendor_price(vendor_id, peptide)
            if price:
                updates.setdefault(peptide, {})[vendor_id] = price
            time.sleep(1.0)   # polite crawl delay

    if not updates:
        log.info("No price updates found — skipping commit")
        return

    # 4. Patch HTML
    new_html = patch_prices_safe(html, updates)

    if new_html == html:
        log.info("HTML unchanged — nothing to commit")
        return

    # 5. Push to GitHub → Netlify auto-deploys
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    updated_count = sum(len(v) for v in updates.values())
    commit_msg = f"🤖 Auto-update prices: {updated_count} changes ({now})"
    github_push_file(new_html, sha, commit_msg)

    log.info(f"=== Done. Updated {updated_count} prices across {len(updates)} peptides ===")


if __name__ == "__main__":
    main()
