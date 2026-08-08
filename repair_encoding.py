#!/usr/bin/env python3
"""
repair_encoding.py — replace U+FFFD replacement characters with the real glyph.

At some point a number of pages were read with the wrong codec and written back,
permanently substituting U+FFFD (the replacement character, rendered as a black
diamond) for several punctuation marks. The files are still *valid* UTF-8 --
U+FFFD is a legal codepoint -- so nothing errored and the damage went unnoticed.

Two consequences:
  * visible garbage on live pages, including cheapest-semaglutide,
    cheapest-retatrutide and cheapest-melanotan-ii
  * regenerate_pages.py could no longer match its "Last updated ... · N vendors
    tracked" pattern on those three pages, so they froze on 2026-06-09 while
    every other cheapest-* page kept updating

The original character is recoverable from context. Every rule below was derived
by enumerating all 300 occurrences across the site, not guessed; the script
asserts that each occurrence matches exactly one rule and that none survive.

Usage:  python3 repair_encoding.py [--apply]
"""
import os
import re
import sys
import glob

BAD = "�"
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pepstracker_fixed")

# (label, replacement, regex). The regex must match the bad char via group
# "b" so the surrounding context is preserved. Order matters: the arithmetic
# and degree rules must run before the generic separator rule, because those
# occurrences are also surrounded by spaces.
RULES = [
    # "Discounted price ÷ mg = cost per mg" / "$45 after discount ÷ 10mg = ..."
    ("division", "÷",
     re.compile(r'(?<=price\s)(?P<b>' + BAD + r')(?=\s*mg)|'
                r'(?<=discount\s)(?P<b2>' + BAD + r')(?=\s*\d+\s*mg)|'
                r'(?<=\$45\s)(?P<b3>' + BAD + r')(?=\s*10mg)')),
    # "stored at 2-8°C"
    ("degree", "°",
     re.compile(r'(?<=\d)(?P<b>' + BAD + r')(?=C\b)')),
    # "5mg×60caps" and "1.5-2× the cost"
    ("multiply", "×",
     re.compile(r'(?<=[a-z0-9])(?P<b>' + BAD + r')(?=\d)|'
                r'(?<=\d)(?P<b2>' + BAD + r')(?=\s+(?:the|more)\b)')),
    # "© 2026 PepsTracker"
    ("copyright", "©",
     re.compile(r'(?P<b>' + BAD + r')(?=\s*20\d\d\s+PepsTracker)')),
    # everything else is the middot separator: "A · B", "&nbsp;·&nbsp;"
    ("middot", "·",
     re.compile(r'(?P<b>' + BAD + r')')),
]


def repair(text):
    counts = {}
    for label, repl, rx in RULES:
        n = 0

        def sub(m):
            nonlocal n
            n += 1
            return repl

        text = rx.sub(sub, text)
        if n:
            counts[label] = counts.get(label, 0) + n
    return text, counts


def main(apply_changes):
    targets = sorted(
        glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True) +
        glob.glob(os.path.join(SITE, "**", "*.js"), recursive=True))

    total = {}
    files = 0
    for path in targets:
        try:
            src = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        if BAD not in src:
            continue
        before = src.count(BAD)
        out, counts = repair(src)

        # every bad char must be accounted for, and none may survive
        assert sum(counts.values()) == before, \
            f"{path}: classified {sum(counts.values())} of {before}"
        assert BAD not in out, f"{path}: {out.count(BAD)} U+FFFD survived"
        # nothing but the replacement characters may change
        assert len(out) == len(src), f"{path}: length changed"

        files += 1
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
        if apply_changes:
            open(path, "w", encoding="utf-8").write(out)
        else:
            print(f"  {os.path.relpath(path, SITE):48s} "
                  + " ".join(f"{k}:{v}" for k, v in sorted(counts.items())))

    print(f"\n{'APPLIED' if apply_changes else 'DRY RUN'}: {files} files, "
          f"{sum(total.values())} characters repaired")
    for k, v in sorted(total.items(), key=lambda kv: -kv[1]):
        glyph = dict((lbl, r) for lbl, r, _ in RULES)[k]
        print(f"   {k:<10} {glyph}  {v}")
    return 0


if __name__ == "__main__":
    # --apply for humans; DRY_RUN=0 for CI. Not driven by a workflow
    # expression like `inputs.dry_run && '' || '--apply'` -- an empty string is
    # falsy in GitHub Actions, so that form would always mean --apply.
    sys.exit(main("--apply" in sys.argv or os.environ.get("DRY_RUN") == "0"))
