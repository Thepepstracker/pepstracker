#!/usr/bin/env python3
"""
nav_active.py — give every page a "you are here" cue in the header nav.

278 pages had no active nav item, so a customer landing from search got no
orientation. Two-part fix, because none of these templates style .active:
mark the right section link with class="active", and inject one conservative
CSS rule (blue + bold, no layout shift) where missing.

Scope is deliberately narrow:
  - vendor-*.html          -> highlight the Vendors link
  - a page whose own URL   -> highlight the self link (about.html, blog.html...)
    appears in its header
  - guide/blog articles    -> highlight the Blog link when one exists
  - cheapest-*/compare-*   -> SKIPPED: their header is logo + hamburger only,
    peptides/*, index.html    or the active state already exists and is correct

Idempotent: any page whose header already contains class="active" is skipped.

Usage: python3 nav_active.py [--apply]   (DRY_RUN=0 for CI)
"""
import glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "pepstracker_fixed")
CSS = "header nav a.active,header .mobile-nav a.active{color:#3b9eff;font-weight:700;}"
GUIDE = re.compile(r'^(best-|blog-|.*-guide-2026|peptides-for-|semaglutide-vs-|retatrutide-vs-|cagrisema-|survodutide-|nad-longevity|us-based-vs-|how-to-|are-peptides-|glp-1-side|peptide-half-life|cost-per-mg|what-are-peptides)')

def target_for(base, header):
    if base.startswith('vendor-') and base != 'vendor-comparisons.html':
        if 'vendors.html' in header: return 'vendors.html'
    if base == 'vendor-comparisons.html' and 'vendors.html' in header: return 'vendors.html'
    if re.search(r'href="/?' + re.escape(base) + '"', header): return base
    if GUIDE.match(base) and 'blog.html' in header: return 'blog.html'
    return None

def main(apply_changes):
    changed = skipped = 0
    for path in sorted(glob.glob(os.path.join(SITE, '*.html'))):
        base = os.path.basename(path)
        if base == 'index.html' or base.startswith(('cheapest-', 'compare-')):
            continue
        src = open(path, encoding='utf-8', errors='replace').read()
        if re.search(r'robots"[^>]*noindex', src, re.I): continue
        end = src.find('</header>')
        if end < 0: continue
        header = src[:end]
        if 'class="active"' in header: continue
        tgt = target_for(base, header)
        if not tgt: skipped += 1; continue
        rx = re.compile(r'(<a )(href="/?' + re.escape(tgt) + '")')
        new_header, n = rx.subn(r'\1class="active" \2', header, count=1)
        if not n: skipped += 1; continue
        out = new_header + src[end:]
        if 'a.active' not in out:
            out = out.replace('</style>', CSS + '\n</style>', 1)
        assert out.count('class="active"') >= 1 and len(out) > len(src)
        changed += 1
        if apply_changes: open(path, 'w', encoding='utf-8').write(out)
        else: print('  %-44s -> %s' % (base, tgt))
    print('%s: %d changed, %d skipped(no target)' % ('APPLIED' if apply_changes else 'DRY RUN', changed, skipped))

if __name__ == '__main__':
    main('--apply' in sys.argv or os.environ.get('DRY_RUN') == '0')
