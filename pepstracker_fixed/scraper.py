"""
PepsTracker Price Scraper — Direct URL Edition (v6)
- Daily scraping (not hourly)
- Out of stock detection stored in prices data
- Full expanded product catalog
"""

import os, re, json, time, base64, logging
from datetime import datetime, timezone
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]
SCRAPERAPI_KEY = os.environ["SCRAPERAPI_KEY"]
GLACIER_EMAIL    = os.environ.get("GLACIER_EMAIL", "")
GLACIER_PASSWORD = os.environ.get("GLACIER_PASSWORD", "")
MILEHIGH_EMAIL    = os.environ.get("MILEHIGH_EMAIL", "")
MILEHIGH_PASSWORD = os.environ.get("MILEHIGH_PASSWORD", "")
ATOMIK_EMAIL     = os.environ.get("ATOMIK_EMAIL", "")
ATOMIK_PASSWORD  = os.environ.get("ATOMIK_PASSWORD", "")
GITHUB_REPO    = "Thepepstracker/pepstracker"
GITHUB_FILE    = "pepstracker_fixed/index.html"
GITHUB_API     = "https://api.github.com"

VENDOR_DOMAIN = {'amp': 'ameanopeptides.com', 'apollo': 'apollopeptidesciences.com', 'ascension': 'ascensionpeptides.com', 'atomik': 'atomiklabz.com', 'certapeptides': 'certapeptides.com', 'ezpeptides': 'ezpeptides.com', 'flawless': 'flawlesscompounds.com', 'fusion': 'fusionpeptide.com', 'glacier': 'glacieraminos.shop', 'glowaminos': 'glowaminos.com', 'glp1lab': 'glp1researchlab.com', 'hydro': 'hydroresearchpeptides.com', 'innoamino': 'innoamino.com', 'ion': 'ionpeptide.com', 'labsourced': 'labsourced.com', 'lapeptides': 'lapeptides.net', 'milehigh': 'milehighcompounds.is', 'nura': 'nurapeptide.com', 'pinnacle': 'pinnaclepeptidelabs.com', 'puratek': 'puratekpeptides.com', 'retaone': 'retaonelabs.com', 's1labs': 'www.s1labs.us', 'solas': 'solasscience.shop', 'swisschems': 'swisschems.is', 'zclabs': 'zclabs.com'}


# ── Full product URL catalog ───────────────────────────────
# NOTE (v7): product URLs are no longer hardcoded here. The scraper reads every
# product URL directly from the live PRICES block in index.html, so it always
# scrapes 100% of listed products and auto-covers vendors/products added later.

# Vendors that need real browser (Cloudflare protected)
CLOUDFLARE_VENDORS = {"glacier", "milehigh", "ezpeptides", "nura", "puratek", "pinnacle"}

# Vendors excluded from auto-scraping:
# - atomik: Cloudflare Turnstile (human verification) — unbypassable
# - labsourced: robots.txt blocks all scrapers
# - retaone: 502 server constantly unreliable
# Update these manually via price-update.html
SKIP_VENDORS = {"atomik", "labsourced", "retaone"}

PREMIUM_VENDORS = set()

def scraper_get(url, render_js=False, timeout=60, premium=False, wait_ms=0):
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "render": "true" if (render_js or premium) else "false",
        "keep_headers": "true",
    }
    if premium:
        params["premium"] = "true"
        params["country_code"] = "us"
    if render_js and wait_ms:
        params["wait"] = str(wait_ms)
    return requests.get("https://api.scraperapi.com/", params=params, timeout=timeout)

# Login state cache — stores cookies per vendor so we only log in once per session
_login_cookies = {}

def playwright_get(url, vendor_id="unknown"):
    """Use real headless Chrome — logs in to gated vendors first, caches cookies."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Atomik needs extra stealth to bypass Cloudflare "Just a moment" page
            stealth_args = [
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--flag-switches-begin", "--disable-site-isolation-trials",
                "--flag-switches-end",
            ]
            browser = p.chromium.launch(
                headless=True,
                args=stealth_args
            )
            # Use a realistic user agent and extra headers to look like a real browser
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                }
            )
            # Remove webdriver flag that Cloudflare detects
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

            # Restore cached cookies if we have them
            if vendor_id in _login_cookies:
                context.add_cookies(_login_cookies[vendor_id])
            else:
                # First time — need to log in or handle challenges
                page = context.new_page()
                try:
                    if vendor_id == "atomik":
                        log.info("  Logging in to Atomik Labz...")
                        page.goto("https://atomiklabz.com/my-account/", wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)  # Wait for CF challenge to clear
                        if "just a moment" in page.title().lower():
                            log.warning("  Atomik Cloudflare challenge not cleared — waiting longer...")
                            page.wait_for_timeout(5000)
                        if "just a moment" not in page.title().lower():
                            try:
                                page.fill("#username", ATOMIK_EMAIL)
                                page.fill("#password", ATOMIK_PASSWORD)
                                page.click("button[name='login']")
                                page.wait_for_load_state("domcontentloaded", timeout=15000)
                                _login_cookies["atomik"] = context.cookies()
                                log.info(f"  Atomik login done, title={page.title()}")
                            except Exception as e:
                                log.warning(f"  Atomik login error: {e}")
                        else:
                            log.warning("  Atomik Cloudflare still blocking after wait")
                    elif vendor_id == "glacier":
                        log.info("  Logging in to Glacier Aminos...")
                        page.goto("https://glacieraminos.shop/my-account/", wait_until="domcontentloaded", timeout=30000)
                        page.fill("#username", GLACIER_EMAIL)
                        page.fill("#password", GLACIER_PASSWORD)
                        page.click("button[name='login']")
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                        log.info(f"  Glacier login done, title={page.title()}")
                    elif vendor_id == "milehigh":
                        log.info("  Logging in to Mile High Compounds...")
                        page.goto("https://milehighcompounds.is/my-account/", wait_until="domcontentloaded", timeout=30000)
                        page.fill("#username", MILEHIGH_EMAIL)
                        page.fill("#password", MILEHIGH_PASSWORD)
                        page.click("button[name='login']")
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                        log.info(f"  MileHigh login done, title={page.title()}")
                    # Cache the cookies for subsequent requests
                    _login_cookies[vendor_id] = context.cookies()
                except Exception as e:
                    log.warning(f"  Login error for {vendor_id}: {e}")
                finally:
                    page.close()

            # Now fetch the actual product page
            page = context.new_page()
            page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf}", lambda r: r.abort())
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait longer for JS-heavy sites like Nura (Elementor) to render prices
            wait_time = 5000 if vendor_id in {"nura", "atomik"} else 8000
            try:
                page.wait_for_selector(".woocommerce-Price-amount, .price, [class*=price]", timeout=wait_time)
            except Exception:
                pass

            # For Nura specifically, wait extra time for Elementor to finish rendering
            if vendor_id == "nura":
                page.wait_for_timeout(2000)

            # Step 1: Select single unit if bundle selector exists
            # Handles sites like Labsourced with 1/3/5 bottle options
            try:
                # Look for bundle/quantity selector buttons (common in Shopify)
                bundle_btns = page.query_selector_all("[class*='bundle'] button, [class*='quantity-break'] button, [class*='multipacks'] button, [data-quantity='1']")
                for btn in bundle_btns:
                    txt = btn.inner_text().strip().lower()
                    if txt in ["1", "1 bottle", "single", "1x"]:
                        btn.click()
                        page.wait_for_timeout(1000)
                        log.info(f"  Selected single unit bundle option")
                        break
            except Exception:
                pass

            # Step 2: Select correct mg size if dropdown exists
            # Priority: 10mg > 5mg > 2mg > skip (never grab 20mg, 50mg etc)
            try:
                selects = page.query_selector_all("select")
                for sel in selects:
                    options = sel.query_selector_all("option")
                    option_texts = [o.inner_text().strip() for o in options]

                    # Only process size dropdowns
                    has_mg_options = any('mg' in t.lower() for t in option_texts)
                    if not has_mg_options:
                        continue

                    # Try preferred sizes in strict order: 10mg, 5mg, 2mg
                    target = None
                    for preferred_mg in ["10", "5", "2"]:
                        for opt_text in option_texts:
                            # Match "10mg", "10 mg", "10MG" etc — but not "100mg"
                            if opt_text.lower().strip().startswith(preferred_mg + "mg") or                                opt_text.lower().strip().startswith(preferred_mg + " mg") or                                f" {preferred_mg}mg" in opt_text.lower() or                                f" {preferred_mg} mg" in opt_text.lower():
                                target = opt_text
                                break
                        if target:
                            break

                    if target:
                        sel.select_option(label=target)
                        page.wait_for_timeout(2000)
                        log.info(f"  Selected size option: {target}")
                    else:
                        log.warning(f"  No 10mg/5mg/2mg option found in {option_texts[:5]} — skipping price to avoid wrong size")
                    break
            except Exception:
                pass

            # Try to read the visible sale price directly from the DOM first
            # This is more reliable than parsing HTML for sale prices
            visible_price = None
            try:
                # Try ins tag (WooCommerce sale price) first
                ins_el = page.query_selector("ins .woocommerce-Price-amount bdi")
                if ins_el:
                    txt = ins_el.inner_text().strip().replace("$","").replace(",","")
                    visible_price = float(txt)
                    log.info(f"  Got sale price from ins tag: ${visible_price}")

                if not visible_price:
                    # Try multiple price selectors — Nura uses Elementor which has different structure
                    price_selectors = [
                        ".woocommerce-Price-amount bdi",
                        ".price .amount",
                        "[class*='price'] .amount",
                        ".elementor-widget-woocommerce-product-price .amount",
                        ".summary .price bdi",
                        ".woocommerce-variation-price .woocommerce-Price-amount bdi",
                        "p.price bdi",
                        "span.price bdi",
                    ]
                    for selector in price_selectors:
                        els = page.query_selector_all(selector)
                        for el in els:
                            try:
                                txt = el.inner_text().strip().replace("$","").replace(",","")
                                p = float(txt)
                                if p > 1:
                                    visible_price = p
                                    log.info(f"  Got price from DOM: ${visible_price}")
                                    break
                            except Exception:
                                pass
                        if visible_price:
                            break
            except Exception as e:
                log.warning(f"  DOM price read error: {e}")

            # Glacier sometimes redirects to inbox/notifications after cookie restore
            # Detect wrong page and navigate directly to the product URL
            page_title = page.title()
            if any(x in page_title.lower() for x in ["new message", "inbox", "notification", "just a moment", "attention required"]):
                log.warning(f"  Wrong page loaded ({page_title}), navigating directly to product URL...")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_selector(".woocommerce-Price-amount, .price, [class*=price]", timeout=8000)
                except Exception:
                    pass
                page_title = page.title()
                log.info(f"  Reloaded: {page_title}")
                visible_price = None  # Reset price so we re-read after size selection below

            html = page.content()
            log.info(f"  Playwright loaded: {page_title}")

            # If we got a price directly from DOM, inject it so extract_main_product_price finds it
            if visible_price:
                html = f'<div class="woocommerce-Price-amount amount"><bdi>${visible_price:.2f}</bdi></div>' + html

            browser.close()
            return html
    except Exception as e:
        log.warning(f"  Playwright error: {e}")
        return None

def parse_price(val):
    try:
        v = float(str(val).replace(",", "").replace("$", "").strip())
        return v if 1.0 < v < 10000 else None
    except Exception:
        return None

def is_out_of_stock(html):
    # Step 1: Strip related/upsell/cross-sell sections to avoid false positives
    # These sections often contain OOS products that aren't the main product
    main_html = html
    for pattern in [
        r'<section[^>]*class="[^"]*related[^"]*".*',
        r'<div[^>]*class="[^"]*related[^"]*".*',
        r'<section[^>]*class="[^"]*upsell[^"]*".*',
        r'<section[^>]*class="[^"]*cross-sell[^"]*".*',
        r'id="related".*',
        r'class="related".*',
    ]:
        m = re.search(pattern, main_html, re.IGNORECASE | re.DOTALL)
        if m:
            main_html = main_html[:m.start()]

    html_lower = main_html.lower()

    # Step 2: Check STRONG definitive OOS signals first — these always mean OOS
    # regardless of any add-to-cart buttons in related products
    strong_oos = [
        '"availability":"http://schema.org/OutOfStock"',
        'availability":"OutOfStock"',
        '"stock_status":"outofstock"',
        'stock_status":"outofstock"',
        '"availability": "OutOfStock"',
        'sold_out":true',
        '"sold_out": true',
        # Ascension-specific: uses email notification form instead of standard OOS
        'email me when this item is back in stock',
        'notify me when available',
        'email me when available',
        'back in stock notification',
    ]
    if any(s.lower() in html_lower for s in strong_oos):
        return True

    # Step 3: If there's a main product add-to-cart button, it's in stock
    # But only count it if it's clearly the MAIN product button (not related)
    has_main_atc = any(x in html_lower for x in [
        'name="add-to-cart"', 'value="add-to-cart"',
        '"add_to_cart"', 'add-to-cart-button',
        'single_add_to_cart_button',
    ])
    if has_main_atc:
        return False

    # Step 4: Weaker OOS signals - only if no main add-to-cart found
    weak_oos = [
        '>out of stock<',
        '>currently unavailable<',
        '>sold out<',
        'class="stock out-of-stock"',
    ]
    return any(s.lower() in html_lower for s in weak_oos)

def extract_main_product_price(html):
    # Strip <del> tags (old/strikethrough prices) so we never grab them
    html = re.sub(r'<del[^>]*>.*?</del>', '', html, flags=re.DOTALL|re.IGNORECASE)

    # Check for <ins> sale price first (WooCommerce sale format)
    ins_match = re.search(r'<ins[^>]*>.*?(\d+\.\d{2}).*?</ins>', html, re.DOTALL|re.IGNORECASE)
    if ins_match:
        p = parse_price(ins_match.group(1))
        if p: return p

    # Strip shipping banners
    html = re.sub(r'[^<]{0,80}free\s*ship[^<]{0,150}\$\s*[\d,]+\.?\d*[^<]{0,80}', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\$\s*[\d,]+\.?\d*[^<]{0,80}free\s*ship[^<]{0,150}', '', html, flags=re.IGNORECASE)

    # Cut off related/upsell/bundle sections to avoid grabbing multi-pack prices
    for pattern in [
        r'<section[^>]*class="[^"]*related',
        r'<div[^>]*class="[^"]*related',
        r'<section[^>]*class="[^"]*upsell',
        r'id="related"',
        r'<[^>]*class="[^"]*bundle[^"]*"',
        r'<[^>]*class="[^"]*multipacks[^"]*"',
        r'<[^>]*class="[^"]*quantity.break[^"]*"',
        # Ascension kit pricing - strip everything after first price variation table
        r'<tr[^>]*>.*?Kit.*?</tr>',
        r'Kit\s*\(',
        r'Buy more',
        r'Bundle\s*&amp;\s*Save',
        r'bundle.*?save',
    ]:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            html = html[:m.start()]

    # JSON-LD — always grab lowPrice or minimum price (handles sale prices + bundle variants)
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Product":
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        # Always use minimum price — handles bundles (1 bottle = cheapest)
                        # and sale prices (sale price < original price)
                        prices = []
                        for o in offers:
                            p = parse_price(o.get("price") or o.get("lowPrice"))
                            if p: prices.append(p)
                        if prices: return min(prices)
                    else:
                        # Prefer lowPrice (sale price) over price (original)
                        # Never grab highPrice - that's the kit/bundle price
                        for key in ["lowPrice", "price"]:
                            val = offers.get(key)
                            if val:
                                p = parse_price(val)
                                if p: return p
        except Exception:
            pass

    # Shopify — check for variants JSON (labsourced uses this)
    # Labsourced stores prices in cents e.g. 4165 = $41.65
    shopify_match = re.search(r'"variants"\s*:\s*\[(.*?)\]', html, re.DOTALL)
    if shopify_match:
        try:
            raw_prices = re.findall(r'"price"\s*:\s*"?(\d+)"?', shopify_match.group(1))
            prices = []
            for rp in raw_prices:
                val = float(rp)
                # Shopify stores in cents if value > 1000
                if val > 1000:
                    val = val / 100
                p = parse_price(val)
                if p:
                    prices.append(p)
            if prices:
                return min(prices)  # Always grab cheapest = single bottle
        except Exception:
            pass

    # Shopify meta price tag (another common pattern)
    meta_match = re.search(r'"price":\s*"(\d+)"', html)
    if meta_match:
        try:
            val = float(meta_match.group(1))
            if val > 1000: val = val / 100
            p = parse_price(val)
            if p: return p
        except Exception:
            pass

    # WooCommerce price spans — after del removal, first price found is always current/sale price
    for pattern in [
        r'class="woocommerce-Price-amount[^"]*"[^>]*>.*?<bdi>.*?\$\s*([\d,]+\.?\d*)',
        r'<p[^>]*class="[^"]*price[^"]*"[^>]*>.*?\$\s*([\d,]+\.?\d*)',
    ]:
        for raw in re.findall(pattern, html, re.DOTALL):
            p = parse_price(raw)
            if p: return p

    # Shopify price in cents
    m = re.search(r'"price"\s*:\s*(\d+)', html)
    if m:
        val = float(m.group(1))
        if val > 1000: val = val / 100
        p = parse_price(val)
        if p: return p

    return None

def fetch_price_from_url(vendor_id, product, product_url):
    """
    Returns (price, oos) where:
      - (float, False) = got a price, in stock
      - (None, True)   = confirmed out of stock
      - (None, False)  = couldn't reach site (timeout/error) — do NOT update anything
    """
    import time as _time
    t_start = _time.time()
    log.info(f"  Fetching {vendor_id}/{product} → {product_url}")
    try:
        if vendor_id in CLOUDFLARE_VENDORS:
            log.info(f"  Using Playwright (real browser) for {vendor_id}")
            html = playwright_get(product_url, vendor_id=vendor_id)
            elapsed = _time.time() - t_start
            if not html:
                log.warning(f"  Playwright returned no HTML — skipping {vendor_id}/{product} [{elapsed:.1f}s]")
                return None, False
            if is_out_of_stock(html):
                log.info(f"  OUT OF STOCK: {vendor_id}/{product} [{elapsed:.1f}s]")
                return None, True
            price = extract_main_product_price(html)
            if price:
                log.info(f"  OK {vendor_id}/{product}: ${price:.2f} [{elapsed:.1f}s]")
                run_stats["successes"].append((vendor_id, product, price, elapsed))
            else:
                log.warning(f"  -- {vendor_id}/{product}: price not found [{elapsed:.1f}s] — check URL or page structure")
                run_stats["not_found"].append((vendor_id, product, elapsed))
            return price, False

        else:
            # Ion Peptides needs JS rendering - use it on first attempt
            ion_needs_js = vendor_id in {"ion"}
            max_attempts = 2  # All remaining vendors get 2 attempts
            # Try without JS first (faster), except for known JS-heavy sites
            for attempt in range(max_attempts):
                try:
                    use_js = ion_needs_js or (attempt == 1)
                    if attempt == 1 and not ion_needs_js:
                        log.info(f"  Retrying with JS...")
                    # Use premium ScraperAPI for Cloudflare-heavy vendors
                    use_premium = vendor_id in PREMIUM_VENDORS
                    if use_premium and attempt == 0:
                        log.info(f"  Using ScraperAPI premium for {vendor_id}...")
                    resp = scraper_get(product_url, render_js=use_js or use_premium, premium=use_premium)
                    if resp.status_code != 200:
                        reason = {
                            403: "🚫 403 Forbidden — likely Cloudflare block, add to CLOUDFLARE_VENDORS",
                            404: "❌ 404 Not Found — URL may be wrong or product removed",
                            429: "🔒 429 Rate Limited — too many requests",
                            500: "💥 500 Server Error — vendor site issue",
                            502: "💥 502 Bad Gateway — vendor site down",
                            503: "💥 503 Service Unavailable — vendor site overloaded",
                        }.get(resp.status_code, f"HTTP {resp.status_code}")
                        log.warning(f"  {reason} for {vendor_id}/{product} on attempt {attempt+1}")
                        if resp.status_code == 403:
                            log.warning(f"  💡 FIX: Add '{vendor_id}' to CLOUDFLARE_VENDORS to use Playwright")
                            run_stats["blocked_403"].append((vendor_id, product))
                            break  # CF won't change its mind
                        if resp.status_code == 404:
                            run_stats["url_404"].append((vendor_id, product))
                            break  # URL is wrong, retry won't help
                        if resp.status_code in {500, 502, 503}:
                            break  # Server error — skip fast, retry won't help
                        continue
                    html = resp.text
                    if is_out_of_stock(html):
                        log.info(f"  OUT OF STOCK: {vendor_id}/{product}")
                        return None, True
                    price = extract_main_product_price(html)
                    if price:
                        elapsed = _time.time() - t_start
                        log.info(f"  OK {vendor_id}/{product}: ${price:.2f} [{elapsed:.1f}s]")
                        run_stats["successes"].append((vendor_id, product, price, elapsed))
                        return price, False
                except requests.exceptions.Timeout:
                    elapsed = _time.time() - t_start
                    log.warning(f"  ⏱ TIMEOUT attempt {attempt+1} for {vendor_id}/{product} [{elapsed:.1f}s] — ScraperAPI may be blocked or site is slow")
                    if attempt == 1:  # Only log on final timeout
                        run_stats["timeouts"].append((vendor_id, product, elapsed))
                    time.sleep(2)
                    continue
                except Exception as e:
                    elapsed = _time.time() - t_start
                    log.warning(f"  ERR attempt {attempt+1} {vendor_id}/{product} [{elapsed:.1f}s]: {e}")
                    continue

            elapsed = _time.time() - t_start
            if elapsed > 60:
                log.warning(f"  🐢 SLOW: {vendor_id}/{product} took {elapsed:.1f}s — consider adding to Playwright vendors or skipping")
            elif elapsed > 30:
                log.warning(f"  ⚠️ SLOW: {vendor_id}/{product} took {elapsed:.1f}s — retries needed")
            log.info(f"  -- {vendor_id}/{product}: price not found after retries [{elapsed:.1f}s]")
            run_stats["not_found"].append((vendor_id, product, elapsed))
            return None, False

    except Exception as e:
        elapsed = _time.time() - t_start
        log.warning(f"  ERR {vendor_id}/{product} [{elapsed:.1f}s]: {e}")
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

import re, json

def find_prices_block(html):
    """Return (start_idx, end_idx) of the PRICES object literal {...}."""
    k = html.find('const PRICES')
    s = html.find('{', k)
    d = 0
    for i in range(s, len(html)):
        c = html[i]
        if c == '{': d += 1
        elif c == '}':
            d -= 1
            if d == 0:
                return s, i
    raise ValueError("PRICES block not found")

def _split_top_objects(arr_text):
    """Given text inside [ ... ] of a vendor array, split into element {..} strings (brace-balanced)."""
    els = []
    d = 0; start = None
    for i, c in enumerate(arr_text):
        if c == '{':
            if d == 0: start = i
            d += 1
        elif c == '}':
            d -= 1
            if d == 0:
                els.append(arr_text[start:i+1])
    return els

def parse_all_listings(html):
    """Parse the peptide-keyed section of PRICES into full listings.
    Returns dict: peptide -> vid -> list of {idx, price, mg, url, listing, oos}."""
    s, e = find_prices_block(html)
    block = html[s:e+1]
    # Walk depth-1 keys; peptide objects are those whose values contain vendor arrays with price:
    result = {}
    depth = 0; i = 1
    n = len(block)
    while i < n - 1:
        c = block[i]
        if c in '{[':
            depth += 1; i += 1; continue
        if c in '}]':
            depth -= 1; i += 1; continue
        if depth == 0 and c == '"':
            m = re.match(r'"([^"]+)"\s*:\s*', block[i:])
            if m:
                key = m.group(1)
                vpos = i + m.end()
                if block[vpos] == '{':
                    # capture this peptide object
                    d2 = 0
                    for x in range(vpos, n):
                        if block[x] == '{': d2 += 1
                        elif block[x] == '}':
                            d2 -= 1
                            if d2 == 0: objend = x; break
                    objtext = block[vpos:objend+1]
                    if 'price:' in objtext or '"price"' in objtext:
                        result[key] = _parse_peptide_obj(objtext)
                    i = objend + 1; continue
        i += 1
    return result

def _parse_peptide_obj(objtext):
    """objtext = { vid:[{...},{...}], vid2:null, ... } -> {vid: [listings]}"""
    out = {}
    # find vendor keys at depth 1 inside objtext
    inner = objtext
    depth = 0; i = 1; n = len(inner)
    while i < n - 1:
        c = inner[i]
        if c in '{[':
            depth += 1; i += 1; continue
        if c in '}]':
            depth -= 1; i += 1; continue
        if depth == 0:
            m = re.match(r'([A-Za-z0-9_]+)\s*:\s*', inner[i:])
            if m:
                vid = m.group(1); vpos = i + m.end()
                if inner[vpos] == '[':
                    d2 = 0
                    for x in range(vpos, n):
                        if inner[x] == '[': d2 += 1
                        elif inner[x] == ']':
                            d2 -= 1
                            if d2 == 0: arrend = x; break
                    arrtext = inner[vpos+1:arrend]
                    els = _split_top_objects(arrtext)
                    listings = []
                    for idx, el in enumerate(els):
                        pm = re.search(r'"?price"?\s*:\s*([\d.]+)', el)
                        mm = re.search(r'"?mg"?\s*:\s*([\d.]+)', el)
                        um = re.search(r'"?url"?\s*:\s*"([^"]*)"', el)
                        lm = re.search(r'"?listing"?\s*:\s*"([^"]*)"', el)
                        oo = 'oos:true' in el.replace('"','')
                        listings.append({
                            'idx': idx,
                            'price': float(pm.group(1)) if pm else None,
                            'mg': float(mm.group(1)) if mm else None,
                            'url': um.group(1) if um else None,
                            'listing': lm.group(1) if lm else None,
                            'oos': oo,
                        })
                    out[vid] = listings
                    i = arrend + 1; continue
                elif inner[vpos:vpos+4] == 'null':
                    out[vid] = None
                    i = vpos + 4; continue
        i += 1
    return out

def parse_with_offsets(html):
    """Like parse_all_listings but records absolute offsets for patching.
    Returns dict peptide->vid->list of {idx, price, mg, url, listing, oos,
      el_start, el_end (abs, el_end is index of closing '}'), price_span (abs a,b)}."""
    s, e = find_prices_block(html)
    block = html[s:e+1]
    base = s
    result = {}
    depth = 0; i = 1; n = len(block)
    while i < n - 1:
        c = block[i]
        if c in '{[':
            depth += 1; i += 1; continue
        if c in '}]':
            depth -= 1; i += 1; continue
        if depth == 0 and c == '"':
            m = re.match(r'"([^"]+)"\s*:\s*', block[i:])
            if m:
                key = m.group(1); vpos = i + m.end()
                if block[vpos] == '{':
                    d2 = 0
                    for x in range(vpos, n):
                        if block[x] == '{': d2 += 1
                        elif block[x] == '}':
                            d2 -= 1
                            if d2 == 0: objend = x; break
                    objtext = block[vpos:objend+1]
                    if 'price:' in objtext or '"price"' in objtext:
                        result[key] = _parse_obj_offsets(block, vpos, objend, base)
                    i = objend + 1; continue
        i += 1
    return result

def _parse_obj_offsets(block, ostart, oend, base):
    out = {}
    depth = 0; i = ostart + 1; n = oend
    while i < n:
        c = block[i]
        if c in '{[':
            depth += 1; i += 1; continue
        if c in '}]':
            depth -= 1; i += 1; continue
        if depth == 0:
            m = re.match(r'([A-Za-z0-9_]+)\s*:\s*', block[i:])
            if m:
                vid = m.group(1); vpos = i + m.end()
                if block[vpos] == '[':
                    d2 = 0
                    for x in range(vpos, n+1):
                        if block[x] == '[': d2 += 1
                        elif block[x] == ']':
                            d2 -= 1
                            if d2 == 0: arrend = x; break
                    # split elements with absolute offsets
                    listings = []
                    d3 = 0; estart = None; idx = 0
                    for x in range(vpos+1, arrend):
                        ch = block[x]
                        if ch == '{':
                            if d3 == 0: estart = x
                            d3 += 1
                        elif ch == '}':
                            d3 -= 1
                            if d3 == 0:
                                el = block[estart:x+1]
                                pm = re.search(r'"?price"?\s*:\s*([\d.]+)', el)
                                mm = re.search(r'"?mg"?\s*:\s*([\d.]+)', el)
                                um = re.search(r'"?url"?\s*:\s*"([^"]*)"', el)
                                lm = re.search(r'"?listing"?\s*:\s*"([^"]*)"', el)
                                oo = 'oos:true' in el.replace('"','')
                                listings.append({
                                    'idx': idx,
                                    'price': float(pm.group(1)) if pm else None,
                                    'mg': float(mm.group(1)) if mm else None,
                                    'url': um.group(1) if um else None,
                                    'listing': lm.group(1) if lm else None,
                                    'oos': oo,
                                    'el_start': base+estart, 'el_end': base+x,
                                    'price_span': (base+estart+pm.start(1), base+estart+pm.end(1)) if pm else None,
                                })
                                idx += 1
                    out[vid] = listings
                    i = arrend + 1; continue
                elif block[vpos:vpos+4] == 'null':
                    out[vid] = None; i = vpos + 4; continue
        i += 1
    return out

def patch_all(html, price_updates, oos_map):
    """price_updates: {(peptide,vid,idx): new_price_float}
       oos_map: {(peptide,vid,idx): bool}  (True=set oos, False=clear oos)
       Applies edits by absolute offset, right-to-left. Returns (new_html, n_price, n_oos)."""
    data = parse_with_offsets(html)
    edits = []  # (start, end, replacement)
    n_price = 0; n_oos = 0
    for pep, vm in data.items():
        for vid, ls in vm.items():
            if not ls: continue
            for el in ls:
                key = (pep, vid, el['idx'])
                if key in price_updates and el['price_span']:
                    a, b = el['price_span']
                    newp = f"{price_updates[key]:.2f}"
                    if html[a:b] != newp:
                        edits.append((a, b, newp)); n_price += 1
                if key in oos_map:
                    want = oos_map[key]
                    if want and not el['oos']:
                        # insert ,oos:true right before closing '}'
                        pos = el['el_end']
                        edits.append((pos, pos, ',oos:true')); n_oos += 1
                    elif (not want) and el['oos']:
                        # remove ,oos:true within element
                        eltext = html[el['el_start']:el['el_end']+1]
                        newel = eltext.replace(',oos:true','')
                        edits.append((el['el_start'], el['el_end']+1, newel)); n_oos += 1
    # apply right-to-left
    edits.sort(key=lambda x: x[0], reverse=True)
    out = html
    for a, b, rep in edits:
        out = out[:a] + rep + out[b:]
    return out, n_price, n_oos

# ── Run Statistics Tracker ──────────────────────────────────
run_stats = {
    "successes": [],      # (vendor, peptide, price, elapsed)
    "timeouts": [],       # (vendor, peptide, elapsed)
    "blocked_403": [],    # (vendor, peptide)
    "not_found": [],      # (vendor, peptide, elapsed)
    "oos": [],            # (vendor, peptide)
    "price_capped": [],   # (vendor, peptide, price, cap)
    "sanity_failed": [],  # (vendor, peptide, prev, new)
    "url_404": [],        # (vendor, peptide)
}


# ── v7: full-coverage, platform-aware scraping engine ───────────────────────
# Work-list is derived directly from the live PRICES block (every listing),
# so we scrape 100% of products and auto-cover any vendor/product added later.
# WooCommerce vendors use the Store API in bulk (one catalog fetch per vendor);
# everything else falls back to per-URL HTML parsing. A patched block is
# re-parsed and validated before commit (fail-safe: a bad run does nothing).

PRICE_CAPS = {
    "Semaglutide": 300, "Tirzepatide": 400, "Retatrutide": 500, "Cagrilintide": 400,
    "BPC-157": 400, "TB-500": 400, "BPC-157 + TB-500 Blend": 400,
    "Ipamorelin": 300, "CJC-1295 (with DAC)": 300, "CJC-1295 (No DAC)": 300,
    "CJC/Ipa Blend": 300, "Sermorelin": 300, "Tesamorelin": 400,
    "Melanotan II": 200, "PT-141 (Bremelanotide)": 200, "GHK-Cu": 400,
    "Epithalon": 400, "MOTS-c": 300, "NAD+": 400, "Semax": 200, "Selank": 200,
    "DSIP": 200, "KPV": 200, "ARA-290": 300, "AOD-9604": 200, "Klow Blend": 400,
    "Glow Blend": 400, "Glutathione": 400, "SS-31": 300, "IGF-1 LR3": 300,
    "Thymosin Alpha-1": 400, "Kisspeptin": 300, "Methylene Blue": 300,
    "SLU-PP-332": 500, "Hexarelin": 200, "GHRP-2": 200, "GHRP-6": 200,
}
DEFAULT_CAP = 800  # generous global ceiling; per-mg checks catch the rest

# Vendors with no per-product URLs or no scrapable pages -> leave to manual updates
NO_SCRAPE_VENDORS = {"certapeptides"}

def _slug_from_url(url):
    m = re.search(r'/product/([^/?#]+)', url)
    if m: return m.group(1).lower()
    m = re.search(r'/products/([^/?#]+)', url)   # shopify
    if m: return m.group(1).lower()
    m = re.search(r'/shop/([^/?#]+)', url)        # s1labs style
    if m: return m.group(1).lower()
    return None

def _http_json(url, vendor_id, timeout=40):
    """Fetch JSON, trying plain requests, then ScraperAPI (render off), then
    ScraperAPI premium for Cloudflare vendors. Returns parsed JSON or None."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PepsTrackerBot/1.0)"}
    # 1) direct
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200 and r.text.strip().startswith(("[", "{")):
            return r.json()
    except Exception:
        pass
    # 2) ScraperAPI (and premium for CF vendors)
    try:
        premium = vendor_id in CLOUDFLARE_VENDORS
        resp = scraper_get(url, render_js=False, premium=premium, timeout=timeout)
        if resp.status_code == 200 and resp.text.strip().startswith(("[", "{")):
            return resp.json()
    except Exception:
        pass
    return None

def woo_store_catalog(domain, vendor_id):
    """Return {slug: {'price': float, 'in_stock': bool}} for a WooCommerce store
    via the Store API. Paginated. None if the API is unavailable."""
    base = f"https://{domain}/wp-json/wc/store/v1/products"
    catalog = {}
    for page in range(1, 8):  # up to 700 products
        data = _http_json(f"{base}?per_page=100&page={page}", vendor_id)
        if not isinstance(data, list) or not data:
            break
        for p in data:
            slug = (p.get("slug") or "").lower()
            prices = p.get("prices") or {}
            raw = prices.get("price")
            minor = prices.get("currency_minor_unit", 2)
            if slug and raw is not None:
                try:
                    price = float(raw) / (10 ** int(minor))
                except Exception:
                    continue
                catalog[slug] = {"price": price, "in_stock": bool(p.get("is_in_stock", True))}
        if len(data) < 100:
            break
    return catalog or None

def _sane(peptide, listing, new_price):
    """Per-listing sanity: hard cap + per-mg ratio vs the listing's own price."""
    if new_price is None or new_price <= 0:
        return False
    cap = PRICE_CAPS.get(peptide, DEFAULT_CAP)
    if new_price > cap:
        log.warning(f"  CAP FAIL {peptide}/{listing.get('listing')}: ${new_price:.2f} > ${cap}")
        run_stats["price_capped"].append((listing.get('_vid'), peptide, new_price, cap))
        return False
    prev = listing.get("price")
    if prev and prev > 0:
        ratio = new_price / prev
        if ratio > 5.0 or ratio < 0.20:
            log.warning(f"  SANITY FAIL {peptide}/{listing.get('listing')}: ${prev:.2f} -> ${new_price:.2f} ({ratio:.2f}x)")
            run_stats["sanity_failed"].append((listing.get('_vid'), peptide, prev, new_price))
            return False
    return True

def main():
    log.info("=== PepsTracker Scraper v7 (full-coverage, platform-aware) ===")
    html, sha = github_get_file()
    listings = parse_all_listings(html)
    if not listings:
        log.error("Could not parse PRICES block — aborting")
        return

    # invert to per-vendor work-list
    per_vendor = {}
    total = 0
    for pep, vmap in listings.items():
        for vid, arr in vmap.items():
            if not arr:
                continue
            for el in arr:
                if not el.get("url"):
                    continue
                el["_vid"] = vid
                per_vendor.setdefault(vid, []).append((pep, el))
                total += 1
    log.info(f"Parsed {len(listings)} peptides, {total} listings across {len(per_vendor)} vendors")

    price_updates = {}   # (peptide, vid, idx) -> new_price
    oos_map = {}         # (peptide, vid, idx) -> bool

    for vid in sorted(per_vendor):
        work = per_vendor[vid]
        if vid in SKIP_VENDORS or vid in NO_SCRAPE_VENDORS:
            log.info(f"⏭ {vid}: manual vendor ({len(work)} listings) — skipping")
            continue

        domain = VENDOR_DOMAIN.get(vid)
        sample_url = work[0][1]["url"]
        is_woo = "/product/" in sample_url and vid != "labsourced"

        catalog = None
        if is_woo and domain:
            log.info(f"🛒 {vid}: fetching WooCommerce Store API catalog ({domain})")
            catalog = woo_store_catalog(domain, vid)
            if catalog:
                log.info(f"   {vid}: {len(catalog)} products from Store API")
            else:
                log.info(f"   {vid}: Store API unavailable — falling back to per-URL HTML")

        for pep, el in work:
            idx = el["idx"]
            new_price = None
            oos = None
            if catalog is not None:
                slug = _slug_from_url(el["url"])
                hit = catalog.get(slug) if slug else None
                if hit:
                    new_price = hit["price"]
                    oos = not hit["in_stock"]
                    run_stats["successes"].append((vid, pep, new_price, 0.0))
                else:
                    run_stats["not_found"].append((vid, pep, 0.0))
                    continue
            else:
                # per-URL HTML fallback (reuses proven fetch path)
                price, is_oos = fetch_price_from_url(vid, pep, el["url"])
                if is_oos:
                    oos = True
                elif price is not None:
                    new_price = price
                else:
                    continue
                time.sleep(0.8)

            if oos:
                oos_map[(pep, vid, idx)] = True
                run_stats["oos"].append((vid, pep))
                continue
            else:
                # clear a stale oos flag if the product is back
                if el.get("oos"):
                    oos_map[(pep, vid, idx)] = False

            if new_price is not None and _sane(pep, el, new_price):
                if abs(new_price - (el["price"] or 0)) > 0.01:
                    price_updates[(pep, vid, idx)] = new_price
                    log.info(f"  CHANGE {pep}/{vid}[{idx}]: ${el['price']} → ${new_price:.2f}")

    if not price_updates and not any(oos_map.values()):
        log.info("No changes — skipping commit")
        _write_report(0, 0)
        return

    new_html, n_price, n_oos = patch_all(html, price_updates, oos_map)

    # ── FAIL-SAFE VERIFICATION: patched block must re-parse to the same shape ──
    try:
        after = parse_all_listings(new_html)
    except Exception as e:
        log.error(f"ABORT: patched PRICES block failed to parse ({e}) — not committing")
        return
    before_n = sum(len(a) for vm in listings.values() for a in vm.values() if a)
    after_n = sum(len(a) for vm in after.values() for a in vm.values() if a)
    if after_n != before_n or len(after) != len(listings):
        log.error(f"ABORT: listing count changed ({before_n}→{after_n}) — not committing")
        return

    now = datetime.now(timezone.utc)
    scrape_date_str = now.strftime("%B %-d, %Y")
    new_html = re.sub(r'const SCRAPE_DATE = "[^"]*";',
                      f'const SCRAPE_DATE = "{scrape_date_str}";', new_html)
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")
    github_push_file(new_html, sha, f"🤖 Daily price update: {n_price} prices, {n_oos} OOS ({now_str})")
    log.info(f"=== Done: {n_price} prices updated, {n_oos} OOS flags ===")
    _write_report(n_price, n_oos)

def _write_report(n_price, n_oos):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# PepsTracker Scraper Diagnostics",
        f"**Run:** {now_str}",
        f"**Result:** {n_price} prices updated, {n_oos} OOS flags",
        "",
        f"## ✅ Fetched: {len(run_stats['successes'])}",
        f"## 🔎 Not found (slug/url mismatch): {len(run_stats['not_found'])}",
        f"## 🚫 OOS: {len(run_stats['oos'])}",
        f"## 🧢 Price-capped: {len(run_stats['price_capped'])}",
        f"## ⚖️ Sanity-failed: {len(run_stats['sanity_failed'])}",
    ]
    if run_stats["not_found"]:
        by = {}
        for vid, pep, _ in run_stats["not_found"]:
            by.setdefault(vid, 0)
            by[vid] += 1
        lines.append("")
        lines.append("### Not-found by vendor")
        for vid, c in sorted(by.items(), key=lambda x: -x[1]):
            lines.append(f"- {vid}: {c}")
    report = "\n".join(lines)
    try:
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/SCRAPER_REPORT.md"
        resp = requests.get(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
        report_sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {"message": f"📊 Scraper report {now_str}",
                   "content": base64.b64encode(report.encode()).decode(), "branch": "main"}
        if report_sha:
            payload["sha"] = report_sha
        requests.put(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}",
                     "Content-Type": "application/json"}, json=payload)
        log.info("Pushed diagnostics report to SCRAPER_REPORT.md")
    except Exception as e:
        log.warning(f"Could not push report: {e}")


# ── Vendor Discovery System ─────────────────────────────────
# To add a new vendor, add it to this list and run the scraper once.
# It will auto-discover all product URLs and add them to PRODUCT_URLS.
# Leave empty for normal daily runs.

NEW_VENDORS_TO_DISCOVER = [
    # Example:
    # {
    #   "id": "newvendor",
    #   "name": "New Vendor Name",
    #   "base_url": "https://newvendor.com",
    #   "code": "GLOWLAB",
    #   "discount": 0.10,
    #   "platform": "auto",      # "woocommerce", "shopify", or "auto"
    #   "needs_login": False,
    #   "login_url": "",
    #   "email_secret": "",      # GitHub secret name e.g. "NEWVENDOR_EMAIL"
    #   "password_secret": "",   # GitHub secret name e.g. "NEWVENDOR_PASSWORD"
    # }
]

PEPTIDE_SEARCH_TERMS = {
    "Semaglutide":                  ["semaglutide", "glp-1s", "sem"],
    "Tirzepatide":                  ["tirzepatide", "glp-2t", "tirz"],
    "Retatrutide":                  ["retatrutide", "glp-3", "reta"],
    "BPC-157":                      ["bpc-157", "bpc157"],
    "TB-500":                       ["tb-500", "tb500", "thymosin beta"],
    "BPC-157 + TB-500 Blend":       ["bpc tb", "wolverine", "bpc-157 tb-500"],
    "Ipamorelin":                   ["ipamorelin"],
    "CJC-1295 (with DAC)":          ["cjc-1295 dac", "cjc 1295 dac"],
    "Sermorelin":                   ["sermorelin"],
    "Tesamorelin":                  ["tesamorelin"],
    "Melanotan II":                 ["melanotan ii", "melanotan-ii", "mt-2"],
    "PT-141 (Bremelanotide)":       ["pt-141", "pt141", "bremelanotide"],
    "GHK-Cu":                       ["ghk-cu", "ghk cu"],
    "Epithalon":                    ["epithalon", "epitalon"],
    "MOTS-c":                       ["mots-c", "motsc"],
    "NAD+":                         ["nad+", "nad 500"],
    "Semax":                        ["semax"],
    "Selank":                       ["selank"],
    "DSIP":                         ["dsip", "delta sleep"],
    "KPV":                          ["kpv"],
    "ARA-290":                      ["ara-290", "ara290"],
    "AOD-9604":                     ["aod-9604", "aod 9604"],
    "Klow Blend":                   ["klow"],
    "Tesamorelin/Ipamorelin Blend": ["tesamorelin ipamorelin", "tesa ipa"],
}


def detect_platform(html, base_url):
    html_lower = html.lower()
    if "cdn.shopify.com" in html_lower or "/collections/" in html_lower:
        return "shopify"
    if "woocommerce" in html_lower or "wc-ajax" in html_lower:
        return "woocommerce"
    return "unknown"


def build_search_urls(base_url, platform, search_term):
    base = base_url.rstrip("/")
    term = search_term.replace(" ", "+")
    urls = []
    if platform in ("woocommerce", "unknown", "auto"):
        urls.append(f"{base}/?s={term}&post_type=product")
    if platform in ("shopify", "unknown", "auto"):
        urls.append(f"{base}/search?q={term}&type=product")
    return urls


def extract_product_links(html, base_url, search_term):
    base = base_url.rstrip("/")
    found = []
    for pattern in [
        r'href=["\']((?:' + re.escape(base) + r')?/product(?:s)?/[^"\'\s>?#]+)',
    ]:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            url = m.group(1)
            if not url.startswith("http"):
                url = base + url
            if url not in found:
                found.append(url)
    # Score by relevance to search term
    term_words = search_term.lower().replace("-", " ").split()
    scored = []
    for url in found:
        url_lower = url.lower().replace("-", " ")
        score = sum(1 for w in term_words if w in url_lower)
        if score > 0:
            scored.append((score, url))
    scored.sort(reverse=True)
    return [url for _, url in scored]


def extract_mg_from_page(html, url):
    url_mg = re.search(r'-(\d+)mg', url, re.IGNORECASE)
    if url_mg:
        val = int(url_mg.group(1))
        if 1 <= val <= 1000:
            return val
    for pattern in [
        r'<h1[^>]*>[^<]*(\d+)\s*mg[^<]*</h1>',
        r'"name"\s*:\s*"[^"]*(\d+)mg[^"]*"',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 1000:
                return val
    return None


def discover_vendor_urls(vendor_info):
    """Auto-discover product URLs for a new vendor."""
    base_url = vendor_info["base_url"]
    vendor_id = vendor_info["id"]
    platform = vendor_info.get("platform", "auto")
    needs_login = vendor_info.get("needs_login", False)
    discovered = {}

    log.info(f"=== Discovering {vendor_info['name']} ({base_url}) ===")

    # Detect platform
    if platform == "auto":
        try:
            use_playwright = needs_login or vendor_id in CLOUDFLARE_VENDORS
            html = playwright_get(base_url, vendor_id=vendor_id) if use_playwright else scraper_get(base_url).text
            platform = detect_platform(html, base_url)
            log.info(f"  Platform: {platform}")
        except Exception:
            platform = "unknown"

    use_playwright = needs_login or vendor_id in CLOUDFLARE_VENDORS

    for peptide, search_terms in PEPTIDE_SEARCH_TERMS.items():
        found_url = found_mg = found_price = None

        for term in search_terms:
            for search_url in build_search_urls(base_url, platform, term):
                try:
                    if use_playwright:
                        html = playwright_get(search_url, vendor_id=vendor_id)
                    else:
                        resp = scraper_get(search_url, render_js=False)
                        html = resp.text if resp.status_code == 200 else None
                    if not html:
                        continue

                    links = extract_product_links(html, base_url, term)
                    if not links:
                        continue

                    product_url = links[0]
                    log.info(f"  Checking {peptide}: {product_url}")

                    if use_playwright:
                        product_html = playwright_get(product_url, vendor_id=vendor_id)
                    else:
                        r2 = scraper_get(product_url, render_js=False)
                        product_html = r2.text if r2.status_code == 200 else None
                    if not product_html:
                        continue

                    price = extract_main_product_price(product_html)
                    mg = extract_mg_from_page(product_html, product_url)
                    oos = is_out_of_stock(product_html)

                    found_url = product_url
                    found_mg = mg or 5
                    found_price = price
                    status = "OOS" if oos else f"${price:.2f}" if price else "no price"
                    log.info(f"  FOUND {peptide}: {status} / {found_mg}mg")
                    break
                except Exception as e:
                    log.warning(f"  Error: {e}")
                time.sleep(0.5)
            if found_url:
                break
            time.sleep(0.5)

        if found_url:
            discovered[peptide] = {"url": found_url, "mg": found_mg or 5, "price": found_price}
        else:
            log.info(f"  NOT FOUND: {peptide}")
        time.sleep(1.0)

    log.info(f"=== Done: {len(discovered)}/{len(PEPTIDE_SEARCH_TERMS)} found ===")
    return discovered


def run_discovery():
    """Run vendor discovery for any new vendors in NEW_VENDORS_TO_DISCOVER."""
    if not NEW_VENDORS_TO_DISCOVER:
        return

    log.info(f"Running discovery for {len(NEW_VENDORS_TO_DISCOVER)} new vendor(s)...")
    for vendor_info in NEW_VENDORS_TO_DISCOVER:
        vid = vendor_info["id"]

        # Load login credentials from env if needed
        if vendor_info.get("needs_login"):
            email_key = vendor_info.get("email_secret", "")
            pass_key = vendor_info.get("password_secret", "")
            if email_key:
                os.environ[f"{vid.upper()}_EMAIL"] = os.environ.get(email_key, "")
            if pass_key:
                os.environ[f"{vid.upper()}_PASSWORD"] = os.environ.get(pass_key, "")

        results = discover_vendor_urls(vendor_info)

        # Print summary for manual review
        log.info(f"\n=== DISCOVERY RESULTS FOR {vendor_info['name']} ===")
        log.info(f"Add to VENDORS list:")
        log.info(f"  {{ id:\"{vid}\", name:\"{vendor_info['name']}\", url:\"{vendor_info['base_url']}\", code:\"{vendor_info['code']}\", discount:{vendor_info['discount']} }},")
        log.info(f"\nAdd to PRODUCT_URLS:")
        log.info(f"  \"{vid}\": {{")
        for peptide, info in results.items():
            log.info(f"    \"{peptide}\": {{\"url\":\"{info['url']}\",\"mg\":{info['mg']}}},")
        log.info(f"  }},")
        log.info(f"\nAdd to PRICES block:")
        for peptide, info in results.items():
            if info.get("price"):
                log.info(f"  {vid}:{{price:{info['price']:.2f},mg:{info['mg']},listing:\"{peptide} {info['mg']}mg\"}},")


if __name__ == "__main__":
    run_discovery()
    main()
