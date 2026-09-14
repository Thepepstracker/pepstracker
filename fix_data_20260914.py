#!/usr/bin/env python3
"""
fix_data_20260914.py - one-off correction of listing errors found by the
2026-09-14 full-catalogue audit.

Every change below was verified against the vendor's own live store API before
being written here; the evidence is quoted in each note. Nothing is inferred.
Each edit asserts its anchor exists, so a silent partial apply is impossible.

Run once, check the printed report, then delete the file.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(ROOT, "pepstracker_fixed", "index.html")

REPLACE = [
    # ---- ascension: the scraper added the solvent volume to the peptide mass.
    # Store lists "GHK-CU (100MG) 3mL" and "GHK-CU (100MG) 10mL" - both are
    # 100mg of GHK-Cu; the mL is how much water it ships in.
    ("ascension GHK-Cu 3mL: 103mg -> 100mg (3mL solvent was added to the mass)",
     '{price:59,mg:103,listing:"GHK-CU (100MG) 3mL"',
     '{price:59,mg:100,listing:"GHK-CU (100MG) 3mL"'),
    ("ascension GHK-Cu 10mL: 110mg -> 100mg (10mL solvent was added to the mass)",
     '{price:69,mg:110,listing:"GHK-CU (100MG) 10mL"',
     '{price:69,mg:100,listing:"GHK-CU (100MG) 10mL"'),

    # ---- fusion: these are capsule products. We stored the PER-CAPSULE
    # strength as the whole purchase, so $/mg came out 60-100x too high, and
    # the price was stale too. Live variants (store API, 2026-09-14):
    #   SLU-PP-332  100mcg/60 capsules  $99.99   -> 6mg
    #   SLU-PP-332  250mcg/100 capsules $159.99  -> 25mg
    #   Tesofensine 250mcg - 60 Count   $142.99  -> 15mg
    #   Tesofensine 500mcg - 100 Count  $175.99  -> 50mg
    ("fusion SLU-PP-332: 0.1mg/$80.99 -> 6mg/$99.99 (100mcg x 60 capsules)",
     '{price:80.99,mg:0.1,listing:"SLU-PP-332 0.1mg"',
     '{price:99.99,mg:6,listing:"SLU-PP-332 100mcg x 60 caps"'),
    ("fusion SLU-PP-332: 0.25mg/$140.99 -> 25mg/$159.99 (250mcg x 100 capsules)",
     '{price:140.99,mg:0.25,listing:"SLU-PP-332 0.25mg"',
     '{price:159.99,mg:25,listing:"SLU-PP-332 250mcg x 100 caps"'),
    ("fusion Tesofensine: 0.25mg/$106.99 -> 15mg/$142.99 (250mcg x 60 count)",
     '{price:106.99,mg:0.25,listing:"Tesofensine 0.25mg"',
     '{price:142.99,mg:15,listing:"Tesofensine 250mcg x 60 caps"'),
    ("fusion Tesofensine: 0.5mg/$139.99 -> 50mg/$175.99 (500mcg x 100 count)",
     '{price:139.99,mg:0.5,listing:"Tesofensine 0.5mg"',
     '{price:175.99,mg:50,listing:"Tesofensine 500mcg x 100 caps"'),

    # ---- Tesamorelin/Ipamorelin blends: we stored only the FIRST component as
    # the whole vial, so these vendors looked dearer than they are. Verified
    # against each store's own product name on 2026-09-14:
    #   nura    "Tesamorelin/Ipamorelin 13/3MG"   $109.00 -> 16mg total
    #   glacier "TESA/IPA Peptide Blend 13MG/3mg" $104.99 -> 16mg total
    # nura's stored link also pointed at a different product (tesamorelin-10mg);
    # the real slug is tesamorelin-ipamorelin-13-3-mg.
    ("nura Tesa/Ipa: 13mg -> 16mg total, and repoint the link at the actual "
     "blend product (was linking to plain Tesamorelin 10mg)",
     '{price:109.00,mg:13,listing:"Tesamorelin/Ipamorelin 13mg/3mg",'
     'url:"https://nurapeptide.com/product/tesamorelin-10mg/?ref=pepstracker"}',
     '{price:109.00,mg:16,listing:"Tesamorelin/Ipamorelin 13mg/3mg",'
     'url:"https://nurapeptide.com/product/tesamorelin-ipamorelin-13-3-mg/?ref=pepstracker"}'),
    ("glacier Tesa/Ipa: label said 10mg/3mg but the store sells 13MG/3mg; "
     "10mg -> 16mg total and $101.99 -> $104.99",
     '{price:101.99,mg:10,listing:"Tesa/Ipa Blend 10mg/3mg",',
     '{price:104.99,mg:16,listing:"Tesa/Ipa Blend 13mg/3mg",'),
]

# ---- whole listings to delete -------------------------------------------
DELETE = [
    # swisschems' store search for "NAD" returns "Go-NAD-orelin" on a substring
    # match, so a Gonadorelin vial was filed as an NAD+ price. Their real NAD+
    # products are separate items and are unaffected.
    ("NAD+: drop swisschems 'Gonadorelin 2mg' - wrong compound entirely "
     "(substring match on NAD inside GoNADorelin)",
     '{price:24.95,mg:2,listing:"Gonadorelin 2mg",'
     'url:"https://swisschems.is/product/gonadorelin-2mg/?ref=6822"}'),
    # Fusion's blend has three variants; we captured the Topical Gel one
    # ("Topical Gel/500mcg each", $171.99) and stored it as a 0.5mg vial. A
    # topical gel does not belong in a $/mg injectable comparison. The two real
    # peptide variants are added back in ADD below.
    ("BPC-157 + TB-500 Blend: drop fusion 0.5mg - that record is the "
     "Topical Gel variant, not a vial",
     '{price:171.99,mg:0.5,listing:"BPC-157 + TB-500 Blend 0.5mg",'
     'url:"https://fusionpeptide.com/product/bpc-157-tb-500-blend/?ref=pepstracker"}'),
]

# ---- listings to add -----------------------------------------------------
# Fusion's two genuine peptide variants of the blend, which we were missing
# entirely because the gel variant had taken the slot.
#   Peptide/6mg each  $80.99  -> 6+6   = 12mg
#   Peptide/10mg each $99.99  -> 10+10 = 20mg
ADD = [
    ("BPC-157 + TB-500 Blend", "fusion",
     '{price:80.99,mg:12,listing:"BPC-157/TB-500 Blend 6mg each",'
     'url:"https://fusionpeptide.com/product/bpc-157-tb-500-blend/?ref=pepstracker"}'),
    ("BPC-157 + TB-500 Blend", "fusion",
     '{price:99.99,mg:20,listing:"BPC-157/TB-500 Blend 10mg each",'
     'url:"https://fusionpeptide.com/product/bpc-157-tb-500-blend/?ref=pepstracker"}'),
]


def main():
    with open(INDEX, encoding="utf-8") as fh:
        src = fh.read()
    before = len(src)
    log = []

    for note, old, new in REPLACE:
        n = src.count(old)
        if n != 1:
            sys.exit("FATAL: anchor appears %d times (need exactly 1): %s" % (n, note))
        src = src.replace(old, new)
        log.append("REPLACED  " + note)

    for note, record in DELETE:
        n = src.count(record)
        if n != 1:
            sys.exit("FATAL: record appears %d times (need exactly 1): %s" % (n, note))
        # swallow one adjacent comma so the array stays valid either way
        if record + "," in src:
            src = src.replace(record + ",", "", 1)
        elif "," + record in src:
            src = src.replace("," + record, "", 1)
        else:
            src = src.replace(record, "", 1)     # lone element in its array
        log.append("DELETED   " + note)

    for compound, vendor, record in ADD:
        if record in src:
            log.append("SKIP add (already present): %s / %s" % (compound, vendor))
            continue
        ci = src.find('"%s": {' % compound)
        if ci < 0:
            ci = src.find('"%s":{' % compound)
        if ci < 0:
            sys.exit("FATAL: compound block not found: %s" % compound)
        vi = src.find("%s:[" % vendor, ci)
        if vi < 0 or vi - ci > 20000:
            sys.exit("FATAL: vendor array not found for %s / %s" % (compound, vendor))
        ins = vi + len("%s:[" % vendor)
        # only add a separator when the array already holds something,
        # otherwise we leave a stray trailing comma
        sep = "" if src[ins] == "]" else ","
        src = src[:ins] + record + sep + src[ins:]
        log.append("ADDED     %s / %s: %s" % (compound, vendor, record[:56]))

    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write(src)

    print("\n".join(log))
    print("\n%d edits; index.html %d -> %d bytes" % (len(log), before, len(src)))


if __name__ == "__main__":
    main()
