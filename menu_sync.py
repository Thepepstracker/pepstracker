"""menu_sync.py - enforce one canonical menu on every page.

Two menu systems exist: id=mobileNav (homepage/vendors, items carry
onclick=toggleMenu()) and id=mn (article/compare pages, plain anchors).
Both get the same 14 items. Runs in the daily workflow before nav_active.py
so active states are re-applied after.
"""
import glob, os, re

SITE = "pepstracker_fixed"
ITEMS = [
    ("/", "\U0001F3E0 Price Tracker"),
    ("/price-index", "\U0001F4C8 Price Index"),
    ("/deals", "\U0001F3F7\uFE0F Deals"),
    ("/vendors", "\U0001F3EA Vendors"),
    ("/dictionary", "\U0001F4D6 Dictionary"),
    ("/blog", "\U0001F4DD Blog"),
    ("/quiz", "\U0001F9EC Quiz"),
    ("/tracker", "\U0001F4C5 My Tracker"),
    ("/calculators", "\U0001F9EE Calculators"),
    ("/vendor-apply", "\U0001F4CB Vendor Apply"),
    ("/advertise", "\U0001F4E3 Advertise"),
    ("/live", "\U0001F399\uFE0F Book the Live"),
    ("/disclaimer", "\u26A0\uFE0F Disclaimer"),
    ("/account", "\U0001F464 My Account"),
]

def inner(onclick):
    oc = ' onclick="toggleMenu()"' if onclick else ""
    return "".join('<a href="%s"%s>%s</a>' % (h, oc, label) for h, label in ITEMS)

RE_MOBILE = re.compile(r'(<(?:div|nav)[^>]*id="mobileNav"[^>]*>)([\s\S]*?)(</(?:div|nav)>)')
RE_MN     = re.compile(r'(<(?:div|nav)[^>]*id="mn"[^>]*>)([\s\S]*?)(</(?:div|nav)>)')

changed = 0
for path in sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True)):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    out = src
    if 'id="mobileNav"' in out:
        out = RE_MOBILE.sub(lambda m: m.group(1) + inner(True) + m.group(3), out, count=1)
    if 'id="mn"' in out:
        out = RE_MN.sub(lambda m: m.group(1) + inner(False) + m.group(3), out, count=1)
    if out != src:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out)
        changed += 1
print("menu_sync: %d pages updated" % changed)
