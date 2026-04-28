"""
PepsTracker Price Scraper — Playwright Edition
Uses a real headless browser to execute JavaScript and scrape dynamic prices.
Runs hourly via GitHub Actions.
"""

import os, re, json, time, base64, logging, asyncio
from datetime import datetime, timezone
import requests
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = "Thepepstracker/pepstracker"
GITHUB_FILE  = "pepstracker_fixed/index.html"
GITHUB_API   = "https://api.github.com"

# ─── Vendor configs ──────────────────────────────────────────────────────────

VENDORS = {
    "ascension":  "https://ascensionpeptides.com/?s={query}",
    "lapeptides": "https://lapeptides.net/?s={query}",
    "glacier":    "https://glacieraminos.shop/?s={query}",
    "milehigh":   "https://milehighcompounds.is/?s={query}",
    "ezpeptides": "https://ezpeptides.com/?s={query}",
    "amp":        "https://ameanopeptides.com/?s={query}",
    "labsourced": "https://labsourced.com/?s={query}",
    "ion":        "https://ionpeptide.com/?s={query}",
    "retaone":    "https://retaonelabs.com/?s={query}",
    "nura":       "https://nurapeptide.com/?s={query}",
    "atomik":     "https://atomiklabz.com/?s={query}",
}

SEARCH_ALIASES = {
    "Semaglutide":                        ["semaglutide"],
    "Tirzepatide":                        ["tirzepatide"],
    "Retatrutide":                        ["retatrutide"],
    "Liraglutide":                        ["liraglutide"],
    "BPC-157":                            ["bpc-157"],
    "BPC-157 (Oral)":                     ["bpc-157 oral"],
    "TB-500":                             ["tb-500"],
    "TB-500 Fragment (17-23)":            ["tb-500 fragment"],
    "BPC-157 + TB-500 Blend":             ["bpc tb blend"],
    "CJC-1295 (with DAC)":               ["cjc-1295 dac"],
    "CJC-1295 (no DAC) / Mod GRF 1-29":  ["cjc-1295 no dac"],
    "Ipamorelin":                         ["ipamorelin"],
    "Hexarelin":                          ["hexarelin"],
    "GHRP-2":                             ["ghrp-2"],
    "GHRP-6":                             ["ghrp-6"],
    "Sermorelin":                         ["sermorelin"],
    "Tesamorelin":                        ["tesamorelin"],
    "GHRH (1-29)":                        ["ghrh"],
    "CJC-1295 + Ipamorelin Blend":        ["cjc ipamorelin"],
    "IGF-1 LR3":                          ["igf-1 lr3"],
    "IGF-1 DES":                          ["igf-1 des"],
    "HGH Fragment 176-191":               ["hgh fragment 176"],
    "AOD 9604":                           ["aod 9604"],
    "MGF (Mechano Growth Factor)":        ["mgf mechano"],
    "PEG-MGF":                            ["peg-mgf"],
    "Follistatin 344":                    ["follistatin"],
    "Adipotide (FTPP)":                   ["adipotide"],
    "5-Amino-1MQ":                        ["5-amino-1mq"],
    "Melanotan I (MT-1)":                 ["melanotan i"],
    "Melanotan II":                       ["melanotan ii"],
    "PT-141 (Bremelanotide)":             ["pt-141"],
    "GHK-Cu":                             ["ghk-cu"],
    "SNAP-8":                             ["snap-8"],
    "Leuphasyl":                          ["leuphasyl"],
    "Selank":                             ["selank"],
    "N-Acetyl Selank":                    ["n-acetyl selank"],
    "Semax":                              ["semax"],
    "N-Acetyl Semax":                     ["n-acetyl semax"],
    "Dihexa":                             ["dihexa"],
    "DSIP (Delta Sleep Inducing Peptide)":["dsip"],
    "P21":                                ["p21 peptide"],
    "Cerebrolysin":                       ["cerebrolysin"],
    "Pinealon":                           ["pinealon"],
    "Cortagen":                           ["cortagen"],
    "Epithalon":                          ["epithalon"],
    "SS-31 (Elamipretide)":               ["ss-31"],
    "MOTS-c":                             ["mots-c"],
    "Humanin":                            ["humanin"],
    "NAD+":                               ["nad+"],
    "Thymalin":                           ["thymalin"],
    "Thymosin Alpha-1":                   ["thymosin alpha"],
    "Thymosin Beta-4 (TB-4)":             ["thymosin beta-4"],
    "Thymogen":                           ["thymogen"],
    "Thymulin":                           ["thymulin"],
    "LL-37":                              ["ll-37"],
    "KPV":                                ["kpv peptide"],
    "Oxytocin":                           ["oxytocin"],
    "Kisspeptin-10":                      ["kisspeptin"],
    "Gonadorelin":                        ["gonadorelin"],
    "VIP (Vasoactive Intestinal Peptide)":["vip vasoactive"],
}

# ─── Price extraction ─────────────────────────────────────────────────────────

def parse_price(text: str) -> float | None:
    text = text.replace(",", "").strip()
    m = re.search(r"\$?([\d]+\.[\d]{1,2})", text)
    if m:
        v = float(m.group(1))
        return v if 1.0 < v < 10000 else None
    return None


async def scrape_vendor_price(page, vendor_id: str, search_url: str, peptide: str) -> float | None:
    """Navigate to vendor search results and extract the first product price."""
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)   # Let JS render

        # Try JSON-LD schema first (most reliable)
        schemas = await page.evaluate("""
            () => Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                .map(s => { try { return JSON.parse(s.textContent); } catch(e) { return null; } })
                .filter(Boolean)
        """)
        for schema in schemas:
            items = schema if isinstance(schema, list) else [schema]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("Product", "ItemPage"):
                    offers = item.get("offers", {})
                    if isinstance(offers, list): offers = offers[0]
                    price = offers.get("price") or offers.get("lowPrice")
                    if price:
                        p = parse_price(str(price))
                        if p:
                            log.info(f"  ✓ {vendor_id}/{peptide}: ${p:.2f} (schema)")
                            return p

        # CSS selectors for WooCommerce / Shopify / common e-commerce
        selectors = [
            ".woocommerce-Price-amount bdi",
            ".woocommerce-Price-amount",
            ".price ins .amount",
            ".price .amount",
            "[class*='price__current']",
            "[class*='product-price']",
            ".ProductItem__Price",
            "[data-product-price]",
            ".price",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.inner_text()
                    p = parse_price(text)
                    if p:
                        log.info(f"  ✓ {vendor_id}/{peptide}: ${p:.2f} (css: {sel})")
                        return p
            except Exception:
                continue

        log.info(f"  ✗ {vendor_id}/{peptide}: no price found")
        return None

    except PWTimeout:
        log.warning(f"  ✗ {vendor_id}/{peptide}: timeout")
        return None
    except Exception as e:
        log.warning(f"  ✗ {vendor_id}/{peptide}: {e}")
        return None


# ─── GitHub helpers ───────────────────────────────────────────────────────────

def github_get_file():
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def github_push_file(content: str, sha: str, message: str):
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
    log.info(f"✅ Pushed: {message}")


# ─── HTML price patcher ───────────────────────────────────────────────────────

def patch_prices_safe(html: str, updates: dict) -> str:
    patched = 0
    for peptide, vendor_prices in updates.items():
        block_pattern = rf'"({re.escape(peptide)})":\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)\}}'
        block_match = re.search(block_pattern, html, re.DOTALL)
        if not block_match:
            continue
        bs, be = block_match.start(), block_match.end()
        block = html[bs:be]
        new_block = block
        for vendor_id, new_price in vendor_prices.items():
            pattern = rf'({re.escape(vendor_id)}:\{{price:)[\d]+\.[\d]{{1,2}}(,)'
            updated, n = re.subn(pattern, rf'\g<1>{new_price:.2f}\2', new_block)
            if n:
                new_block = updated
                patched += 1
        html = html[:bs] + new_block + html[be:]
    log.info(f"Patched {patched} price fields")
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    log.info("=== PepsTracker Scraper (Playwright) Starting ===")

    html, sha = github_get_file()

    # Parse existing vendor/peptide combos
    existing_prices: dict[str, list[str]] = {}
    for m in re.finditer(r'"([^"]+)":\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', html, re.DOTALL):
        peptide, block = m.group(1), m.group(2)
        vendor_ids = re.findall(r'(\w+):\{price:', block)
        if vendor_ids:
            existing_prices[peptide] = vendor_ids

    if not existing_prices:
        log.error("Could not parse PRICES block — aborting")
        return

    # Rotate batch by hour
    priority = ["Semaglutide","Tirzepatide","Retatrutide","Liraglutide",
                "BPC-157","TB-500","BPC-157 + TB-500 Blend",
                "CJC-1295 (with DAC)","Ipamorelin","Epithalon"]
    all_peptides = priority + [p for p in existing_prices if p not in priority]
    hour = datetime.now(timezone.utc).hour
    batch_size = 12
    start = (hour * batch_size) % len(all_peptides)
    batch = all_peptides[start:start+batch_size]
    if len(batch) < batch_size:
        batch += all_peptides[:batch_size-len(batch)]

    log.info(f"Scraping {len(batch)} peptides this run")

    updates: dict[str, dict[str, float]] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        for peptide in batch:
            vendor_ids = existing_prices.get(peptide, [])
            aliases = SEARCH_ALIASES.get(peptide, [peptide.lower()])
            keyword = aliases[0]

            for vendor_id in vendor_ids:
                search_tpl = VENDORS.get(vendor_id)
                if not search_tpl:
                    continue
                url = search_tpl.format(query=requests.utils.quote(keyword))
                price = await scrape_vendor_price(page, vendor_id, url, peptide)
                if price:
                    updates.setdefault(peptide, {})[vendor_id] = price
                await asyncio.sleep(1.5)

        await browser.close()

    if not updates:
        log.info("No price updates — skipping commit")
        return

    new_html = patch_prices_safe(html, updates)
    if new_html == html:
        log.info("HTML unchanged — nothing to commit")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = sum(len(v) for v in updates.values())
    github_push_file(new_html, sha, f"🤖 Auto-update prices: {count} changes ({now})")
    log.info(f"=== Done. Updated {count} prices across {len(updates)} peptides ===")


if __name__ == "__main__":
    asyncio.run(main())
