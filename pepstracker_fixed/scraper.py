"""
PepsTracker Daily Price Scraper
================================
Sweeps all vendor websites for peptide prices and writes prices.json.
Run daily via cron: 0 6 * * * /usr/bin/python3 /path/to/scraper.py

Requirements: pip install requests beautifulsoup4 playwright
"""

import json, re, time, logging
from datetime import datetime
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────

OUTPUT_FILE = Path(__file__).parent / "prices.json"

VENDORS = [
    {
        "id": "ascension",
        "name": "Ascension Peptides",
        "base_url": "https://ascensionpeptides.com",
        "affiliate_url": "https://ascensionpeptides.com/ref/Glowlab/",
        "code": "Glowlab",
        "discount": 0.50,
        "search_url": "https://ascensionpeptides.com/?s={peptide}",
    },
    {
        "id": "atomik",
        "name": "AtomiK Labz",
        "base_url": "https://atomiklabz.com",
        "affiliate_url": "https://affiliatepirate.com/r/IE180L",
        "code": "Glowlab15",
        "discount": 0.15,
        "search_url": "https://atomiklabz.com/?s={peptide}",
    },
    {
        "id": "lapeptides",
        "name": "LA Peptides",
        "base_url": "https://lapeptides.net",
        "affiliate_url": "https://lapeptides.net/?ref=Glowlab",
        "code": "Glowlab",
        "discount": 0.10,
        "search_url": "https://lapeptides.net/?s={peptide}",
    },
    {
        "id": "glacier",
        "name": "Glacier Aminos",
        "base_url": "https://glacieraminos.shop",
        "affiliate_url": "https://glacieraminos.shop/?ref=sidbilvi",
        "code": "Glowlab",
        "discount": 0.10,
        "search_url": "https://glacieraminos.shop/?s={peptide}",
    },
    {
        "id": "milehigh",
        "name": "Mile High Compound",
        "base_url": "https://milehighcompounds.is",
        "affiliate_url": "https://milehighcompounds.is/ref=glowlab10",
        "code": "Glowlab",
        "discount": 0.10,
        "search_url": "https://milehighcompounds.is/?s={peptide}",
    },
    {
        "id": "ezpeptides",
        "name": "EZ Peptides",
        "base_url": "https://ezpeptides.com",
        "affiliate_url": "https://ezpeptides.com/?red=glowlab",
        "code": "GlowLab",
        "discount": 0.10,
        "search_url": "https://ezpeptides.com/?s={peptide}",
    },
    {
        "id": "amp",
        "name": "AMP Ameano Peptides",
        "base_url": "https://ameanopeptides.com",
        "affiliate_url": "https://ameanopeptides.com/?ref=lcbpndeo",
        "code": "Glowlab",
        "discount": 0.10,
        "search_url": "https://ameanopeptides.com/?s={peptide}",
    },
    {
        "id": "labsourced",
        "name": "Labsourced",
        "base_url": "https://labsourced.com",
        "affiliate_url": "https://labsourced.com/?ref=Glowlab",
        "code": "Glowlab",
        "discount": 0.15,
        "search_url": "https://labsourced.com/?s={peptide}",
    },
    {
        "id": "ion",
        "name": "Ion Peptides",
        "base_url": "https://ionpeptide.com",
        "affiliate_url": "https://ionpeptide.com/?ref=Glowlab",
        "code": "Glowlab",
        "discount": 0.15,
        "search_url": "https://ionpeptide.com/?s={peptide}",
    },
    {
        "id": "retaone",
        "name": "Reta One Labs",
        "base_url": "https://retaonelabs.com",
        "affiliate_url": "https://retaonelabs.com/ref/0rgv6",
        "code": "Glowlab",
        "discount": 0.05,
        "search_url": "https://retaonelabs.com/?s={peptide}",
    },
    {
        "id": "nura",
        "name": "NuraPeptide",
        "base_url": "https://nurapeptide.com",
        "affiliate_url": "https://nurapeptide.com/?ref=glowlab",
        "code": "Glowlab15",
        "discount": 0.15,
        "search_url": "https://nurapeptide.com/?s={peptide}",
    },
]

PEPTIDES = [
    "BPC-157", "TB-500", "Semaglutide", "Tirzepatide",
    "CJC-1295 (with DAC)", "CJC-1295 (no DAC)", "Ipamorelin", "Hexarelin",
    "GHRP-2", "GHRP-6", "IGF-1 LR3", "Melanotan II",
    "PT-141 (Bremelanotide)", "Selank", "Semax", "Epithalon",
    "SS-31", "GHK-Cu", "KPV", "LL-37", "NAD+", "Tesamorelin",
    "Sermorelin", "Oxytocin", "Thymosin Alpha-1", "AOD 9604",
    "5-Amino-1MQ", "MOTS-c", "Humanin", "Cerebrolysin",
]

# ── SCRAPER ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pepstracker")


def parse_price(text: str) -> float | None:
    """Extract the first USD price from a string."""
    match = re.search(r"\$\s*([\d,]+(?:\.\d{1,2})?)", text.replace(",", ""))
    if match:
        return float(match.group(1))
    return None


def scrape_vendor(session, vendor: dict, peptide: str) -> float | None:
    """
    Try to find the price for `peptide` on `vendor`.
    Strategy: search the vendor's site and parse the first product price found.
    Falls back to None if the page can't be parsed or product isn't found.
    """
    try:
        from bs4 import BeautifulSoup

        url = vendor["search_url"].format(peptide=peptide.replace(" ", "+"))
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # --- Strategy 1: WooCommerce / Shopify standard price selectors ---
        price_selectors = [
            ".price ins .amount",          # WooCommerce sale price
            ".price .amount",              # WooCommerce regular price
            ".product__price",             # Shopify theme
            "[class*='price']",            # Generic
            ".amount",
        ]
        for selector in price_selectors:
            els = soup.select(selector)
            for el in els:
                price = parse_price(el.get_text())
                if price and 5 < price < 1000:   # sanity check
                    return price

        # --- Strategy 2: Look for peptide name near a price in the page text ---
        text = soup.get_text(" ", strip=True)
        # Find occurrences of the peptide name (case-insensitive)
        name_clean = peptide.split("(")[0].strip().lower()
        idx = text.lower().find(name_clean)
        if idx != -1:
            snippet = text[idx:idx+200]
            price = parse_price(snippet)
            if price and 5 < price < 1000:
                return price

    except Exception as exc:
        log.warning("  ⚠️  %s / %s → %s", vendor["name"], peptide, exc)

    return None


def run_scraper():
    try:
        import requests
    except ImportError:
        log.error("Missing 'requests'. Run: pip install requests beautifulsoup4")
        return

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    })

    results = {}

    for peptide in PEPTIDES:
        log.info("🔬 Scanning: %s", peptide)
        results[peptide] = {}

        for vendor in VENDORS:
            price = scrape_vendor(session, vendor, peptide)
            results[peptide][vendor["id"]] = price
            status = f"${price:.2f}" if price else "not found"
            log.info("  %-26s → %s", vendor["name"], status)
            time.sleep(0.8)   # polite delay between requests

    # Write output
    output = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "prices": results,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    log.info("✅ Written to %s", OUTPUT_FILE)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_scraper()
