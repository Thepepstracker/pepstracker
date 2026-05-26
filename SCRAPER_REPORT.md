# PepsTracker Scraper Diagnostics
**Run:** 2026-05-26 21:21 UTC
**Result:** 21 prices updated, 29 OOS

## ✅ Successful Fetches
Total: 122
- ion/MOTS-c: $42.00 (51.7s)
- ion/Selank: $34.65 (50.7s)
- ion/Tirzepatide: $49.00 (49.9s)
- ion/Tesamorelin: $69.95 (46.7s)
- ion/ARA-290: $59.00 (46.3s)
- ion/Tesamorelin/Ipamorelin Blend: $79.95 (45.8s)
- ion/PT-141 (Bremelanotide): $37.00 (45.7s)
- ion/CJC-1295 (with DAC): $59.00 (45.0s)
- retaone/Tesamorelin: $49.00 (43.9s)
- glacier/Tirzepatide: $39.99 (43.4s)

## ⚠️ Sanity Check Failures
Price changed too dramatically — investigate:
- milehigh/Epithalon: $27.00 → $119.99 (+344%)

## 🔍 Price Not Found
- **retaone** (5): Semaglutide, BPC-157, BPC-157 + TB-500 Blend, PT-141 (Bremelanotide), NAD+
- **nura** (23): Semaglutide, Tirzepatide, Retatrutide, BPC-157, TB-500, BPC-157 + TB-500 Blend, Ipamorelin, CJC-1295 (with DAC)
- **labsourced** (19): Tirzepatide, Retatrutide, BPC-157, TB-500, BPC-157 + TB-500 Blend, Ipamorelin, Sermorelin, Tesamorelin
- **atomik** (20): BPC-157, TB-500, BPC-157 + TB-500 Blend, Ipamorelin, CJC-1295 (with DAC), Sermorelin, Tesamorelin, Melanotan II
- **ion** (2): Semax, DSIP

## 📊 Summary
| Metric | Count |
|--------|-------|
| ✅ Prices fetched | 122 |
| 💰 Prices updated | 21 |
| 🚫 Cloudflare 403 | 0 |
| ⏱ Timeouts | 0 |
| ❌ 404 URLs | 0 |
| 🔒 Price capped | 0 |
| ⚠️ Sanity failed | 1 |
| 📦 OOS | 29 |