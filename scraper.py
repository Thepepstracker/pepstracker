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

# ── Full product URL catalog ───────────────────────────────
PRODUCT_URLS = {
  "ascension": {
    "Semaglutide":                    {"url":"https://ascensionpeptides.com/product/s-5/","mg":5},
    "Tirzepatide":                    {"url":"https://ascensionpeptides.com/product/t-10/","mg":10},
    "Retatrutide":                    {"url":"https://ascensionpeptides.com/product/t-10/","mg":10},
    "BPC-157":                        {"url":"https://ascensionpeptides.com/product/bpc-157-5mg/","mg":5},
    "TB-500":                         {"url":"https://ascensionpeptides.com/product/tb-500-5mg/","mg":5},
    "BPC-157 + TB-500 Blend":         {"url":"https://ascensionpeptides.com/product/wolverine-stack/","mg":20},
    "Ipamorelin":                     {"url":"https://ascensionpeptides.com/product/ipamorelin-5mg/","mg":5},
    "Epithalon":                      {"url":"https://ascensionpeptides.com/product/epithalon-10mg/","mg":10},
    "Melanotan II":                   {"url":"https://ascensionpeptides.com/product/melanotan-ii-10mg/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://ascensionpeptides.com/product/pt-141-10mg/","mg":10},
    "GHK-Cu":                         {"url":"https://ascensionpeptides.com/product/ghk-cu-100mg/","mg":100},
    "Klow Blend":                     {"url":"https://ascensionpeptides.com/product/klow-ghk-cu-bpc-157-thymosin-beta4-kpv/","mg":80},
    "ARA-290":                        {"url":"https://ascensionpeptides.com/product/ara-290-10mg/","mg":10},
    "MOTS-c":                         {"url":"https://ascensionpeptides.com/product/mots-c-10mg/","mg":10},
    "NAD+":                           {"url":"https://ascensionpeptides.com/product/nad-500mg/","mg":500},
    "KPV":                            {"url":"https://ascensionpeptides.com/product/kpv-10mg/","mg":10},
    "Semax":                          {"url":"https://ascensionpeptides.com/product/semax-10mg/","mg":10},
    "AOD-9604":                       {"url":"https://ascensionpeptides.com/product/aod-9604-5mg/","mg":5},
    "Tesamorelin":                    {"url":"https://ascensionpeptides.com/product/tesamorelin-5mg/","mg":5},
    "Selank":                         {"url":"https://ascensionpeptides.com/product/selank-10mg/","mg":10},
    "Sermorelin":                     {"url":"https://ascensionpeptides.com/product/sermorelin-10mg/","mg":10},
    "DSIP":                           {"url":"https://ascensionpeptides.com/product/dsip-10mg/","mg":10},
    "Adamax":                         {"url":"https://ascensionpeptides.com/product/adamax-10mg/","mg":10},
  },
  "atomik": {
    "Semaglutide":                    {"url":"https://atomiklabz.com/product/peptide-1-s-10mg/","mg":10},
    "Tirzepatide":                    {"url":"https://atomiklabz.com/product/peptide-2-t-10mg/","mg":10},
    "Retatrutide":                    {"url":"https://atomiklabz.com/product/peptide-3-r-10mg/","mg":10},
    "BPC-157":                        {"url":"https://atomiklabz.com/product/bpc-157-5mg/","mg":5},
    "TB-500":                         {"url":"https://atomiklabz.com/product/tb-500-10mg/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://atomiklabz.com/product/bpc-157-tb-500-blend-10mg-10mg/","mg":10},
    "Ipamorelin":                     {"url":"https://atomiklabz.com/product/ipamorelin-10mg/","mg":10},
    "CJC-1295 (with DAC)":            {"url":"https://atomiklabz.com/product/new-release-cjc-1295-with-dac-5mg/","mg":5},
    "Epithalon":                      {"url":"https://atomiklabz.com/product/epithalon-10mg/","mg":10},
    "Melanotan II":                   {"url":"https://atomiklabz.com/product/melanotan-ii-10mg/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://atomiklabz.com/product/pt-141/","mg":10},
    "GHK-Cu":                         {"url":"https://atomiklabz.com/product/ghk-cu-100mg/","mg":100},
    "Bacteriostatic Water":           {"url":"https://atomiklabz.com/product/10ml-bacteriostatic-water/","mg":10},
    "ARA-290":                        {"url":"https://atomiklabz.com/product/ara-290-16mg/","mg":16},
    "Tesamorelin/Ipamorelin Blend":   {"url":"https://atomiklabz.com/product/tesamorelin-ipamorelin/","mg":12},
    "MOTS-c":                         {"url":"https://atomiklabz.com/product/mots-c-10mg/","mg":10},
    "NAD+":                           {"url":"https://atomiklabz.com/product/nad-700mg-new-adjusted-ph-lyophilized/","mg":700},
    "KPV":                            {"url":"https://atomiklabz.com/product/kpv-10mg/","mg":10},
    "Semax":                          {"url":"https://atomiklabz.com/product/semax-10mg/","mg":10},
    "AOD-9604":                       {"url":"https://atomiklabz.com/product/aod-9604-5mg/","mg":5},
    "Tesamorelin":                    {"url":"https://atomiklabz.com/product/tesamorelin-10mg/","mg":5},
    "Selank":                         {"url":"https://atomiklabz.com/product/selank-12mg/","mg":12},
    "Sermorelin":                     {"url":"https://atomiklabz.com/product/sermorelin-10mg/","mg":10},
    "DSIP":                           {"url":"https://atomiklabz.com/product/dsip-5mg/","mg":5},
    "Klow Blend":                     {"url":"https://atomiklabz.com/product/klow-cu/","mg":91},
  },
  "lapeptides": {
    "Semaglutide":                    {"url":"https://lapeptides.net/product/g-1-s/","mg":5},
    "Tirzepatide":                    {"url":"https://lapeptides.net/product/g-2/","mg":15},
    "Retatrutide":                    {"url":"https://lapeptides.net/product/g-3/","mg":10},
    "BPC-157":                        {"url":"https://lapeptides.net/product/bpc-157/","mg":10},
    "TB-500":                         {"url":"https://lapeptides.net/product/tb500/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://lapeptides.net/product/bpc-tb500-blend/","mg":10},
    "Ipamorelin":                     {"url":"https://lapeptides.net/product/ipamorelin/","mg":10},
    "Epithalon":                      {"url":"https://lapeptides.net/product/epithalon/","mg":50},
    "Melanotan II":                   {"url":"https://lapeptides.net/product/melanotan-2/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://lapeptides.net/product/pt-141/","mg":10},
    "GHK-Cu":                         {"url":"https://lapeptides.net/product/ghk-cu/","mg":100},
    "Klow Blend":                     {"url":"https://lapeptides.net/product/klow/","mg":80},
    "ARA-290":                        {"url":"https://lapeptides.net/product/ara-290/","mg":16},
    "MOTS-c":                         {"url":"https://lapeptides.net/product/mots-c/","mg":10},
    "NAD+":                           {"url":"https://lapeptides.net/product/nad/","mg":500},
    "KPV":                            {"url":"https://lapeptides.net/product/kpv/","mg":10},
    "Semax":                          {"url":"https://lapeptides.net/product/semax/","mg":10},
    "AOD-9604":                       {"url":"https://lapeptides.net/product/aod-9604/","mg":10},
    "Tesamorelin":                    {"url":"https://lapeptides.net/product/tesamorelin/","mg":10},
    "Selank":                         {"url":"https://lapeptides.net/product/selank/","mg":10},
    "Sermorelin":                     {"url":"https://lapeptides.net/product/sermorelin/","mg":10},
    "DSIP":                           {"url":"https://lapeptides.net/product/dsip/","mg":5},
    "Adamax":                         {"url":"https://lapeptides.net/product/adamax/","mg":10},
    "SS-31":                          {"url":"https://lapeptides.net/product/ss-31/","mg":10},
  },
  "glacier": {
    "Semaglutide":                    {"url":"https://glacieraminos.shop/product/gla1-s/","mg":15},
    "Tirzepatide":                    {"url":"https://glacieraminos.shop/product/gla2-trz/","mg":10},
    "Retatrutide":                    {"url":"https://glacieraminos.shop/product/gla3-rt/","mg":10},
    "BPC-157":                        {"url":"https://glacieraminos.shop/product/bpc-157/","mg":10},
    "TB-500":                         {"url":"https://glacieraminos.shop/product/tb500/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://glacieraminos.shop/product/bpc-tb-500-wolverine/","mg":10},
    "Ipamorelin":                     {"url":"https://glacieraminos.shop/product/ipamorelin-10mg/","mg":10},
    "CJC-1295 (with DAC)":            {"url":"https://glacieraminos.shop/product/cjc-1295-w-dac-5mg/","mg":5},
    "Epithalon":                      {"url":"https://glacieraminos.shop/product/epi10/","mg":10},
    "Melanotan II":                   {"url":"https://glacieraminos.shop/product/mt-2/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://glacieraminos.shop/product/pt-141/","mg":10},
    "GHK-Cu":                         {"url":"https://glacieraminos.shop/product/ghk-cu/","mg":50},
    "Bacteriostatic Water":           {"url":"https://glacieraminos.shop/product/reconstitution-solution-10ml/","mg":10},
    "Bacteriostatic Water 30mL":      {"url":"https://glacieraminos.shop/product/water30/","mg":30},
    "Buffered NAD+":                  {"url":"https://glacieraminos.shop/product/nad-500mg-buffered/","mg":500},
    "Klow Blend":                     {"url":"https://glacieraminos.shop/product/klow-80/","mg":80},
    "ARA-290":                        {"url":"https://glacieraminos.shop/product/ara-29010/","mg":10},
    "Tesamorelin/Ipamorelin Blend":   {"url":"https://glacieraminos.shop/product/tesa-ipa-peptide-blend-10mg-3mg/","mg":10},
    "MOTS-c":                         {"url":"https://glacieraminos.shop/product/mots-c/","mg":10},
    "KPV":                            {"url":"https://glacieraminos.shop/product/kpv/","mg":10},
    "Semax":                          {"url":"https://glacieraminos.shop/product/s3max-10/","mg":10},
    "Tesamorelin":                    {"url":"https://glacieraminos.shop/product/tesamorelin/","mg":10},
    "Selank":                         {"url":"https://glacieraminos.shop/product/selank-10/","mg":10},
    "Sermorelin":                     {"url":"https://glacieraminos.shop/product/sermorelin/","mg":10},
    "DSIP":                           {"url":"https://glacieraminos.shop/product/dsip/","mg":5},
    "Adamax":                         {"url":"https://glacieraminos.shop/product/adamax-10mg/","mg":10},
    "Lipo-C":                         {"url":"https://glacieraminos.shop/product/lipo-c/","mg":10},
    "Glutathione":                    {"url":"https://glacieraminos.shop/product/glutathione-1500mg/","mg":1500},
  },
  "milehigh": {
    "Semaglutide":                    {"url":"https://milehighcompounds.is/product/mhc-1-sm/","mg":10},
    "Tirzepatide":                    {"url":"https://milehighcompounds.is/product/mhc-2-trz/","mg":10},
    "Retatrutide":                    {"url":"https://milehighcompounds.is/product/mhc-3-rt/","mg":10},
    "BPC-157":                        {"url":"https://milehighcompounds.is/product/bpc-157/","mg":10},
    "TB-500":                         {"url":"https://milehighcompounds.is/product/tb-500/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://milehighcompounds.is/product/bpc-157-tb-500-blend/","mg":20},
    "Ipamorelin":                     {"url":"https://milehighcompounds.is/product/ipamorelin/","mg":10},
    "CJC-1295 (with DAC)":            {"url":"https://milehighcompounds.is/product/cjc-1295-w-dac/","mg":5},
    "Epithalon":                      {"url":"https://milehighcompounds.is/product/epithalon/","mg":50},
    "Melanotan II":                   {"url":"https://milehighcompounds.is/product/mt-2/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://milehighcompounds.is/product/pt-141/","mg":10},
    "GHK-Cu":                         {"url":"https://milehighcompounds.is/product/ghk-cu/","mg":50},
    "Klow Blend":                     {"url":"https://milehighcompounds.is/product/klow-80-blend/","mg":80},
    "ARA-290":                        {"url":"https://milehighcompounds.is/product/ara-290/","mg":10},
    "Tesamorelin/Ipamorelin Blend":   {"url":"https://milehighcompounds.is/product/tesa-ipa-blend/","mg":10},
    "MOTS-c":                         {"url":"https://milehighcompounds.is/product/mots-c/","mg":10},
    "NAD+":                           {"url":"https://milehighcompounds.is/product/nad500mg/","mg":500},
    "KPV":                            {"url":"https://milehighcompounds.is/product/kpv/","mg":10},
    "Semax":                          {"url":"https://milehighcompounds.is/product/semax/","mg":10},
    "AOD-9604":                       {"url":"https://milehighcompounds.is/product/aod-9604/","mg":5},
    "Tesamorelin":                    {"url":"https://milehighcompounds.is/product/tesamorlin/","mg":10},
    "Selank":                         {"url":"https://milehighcompounds.is/product/selank/","mg":10},
    "Sermorelin":                     {"url":"https://milehighcompounds.is/product/sermorelin/","mg":10},
    "DSIP":                           {"url":"https://milehighcompounds.is/product/dsip/","mg":10},
    "Adamax":                         {"url":"https://milehighcompounds.is/product/adamax/","mg":10},
    "Lipo-C":                         {"url":"https://milehighcompounds.is/product/lipo-c/","mg":10},
    "SS-31":                          {"url":"https://milehighcompounds.is/product/mtp-31/","mg":10},
    "Glutathione":                    {"url":"https://milehighcompounds.is/product/glutathione/","mg":1500},
  },
  "ezpeptides": {
    "Semaglutide":                    {"url":"https://ezpeptides.com/product/ezp-1p-10mg/","mg":10},
    "Tirzepatide":                    {"url":"https://ezpeptides.com/product/ezp-2p-10mg/","mg":10},
    "Retatrutide":                    {"url":"https://ezpeptides.com/product/ezp-3p-10mg-glp-3rt/","mg":10},
    "BPC-157":                        {"url":"https://ezpeptides.com/product/bpc-157-10mg/","mg":10},
    "TB-500":                         {"url":"https://ezpeptides.com/product/tb4-10mg/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://ezpeptides.com/product/bpc-157-tb4-blend-10mg-10mg/","mg":10},
    "Ipamorelin":                     {"url":"https://ezpeptides.com/product/ipamorelin-10mg/","mg":10},
    "Epithalon":                      {"url":"https://ezpeptides.com/product/epitalon-10mg/","mg":10},
    "Melanotan II":                   {"url":"https://ezpeptides.com/product/melanotan-ii-10mg/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://ezpeptides.com/product/pt-141-10mg/","mg":10},
    "GHK-Cu":                         {"url":"https://ezpeptides.com/product/ghk-cu-50mg/","mg":50},
    "Research Diluent Solution":      {"url":"https://ezpeptides.com/product/research-diluent-solution-10ml/","mg":10},
    "Buffered NAD+":                  {"url":"https://ezpeptides.com/product/buffered-nad-500mg/","mg":500},
    "Buffered NAD+ 250mg":            {"url":"https://ezpeptides.com/product/buffered-nad-250mg/","mg":250},
    "Lipo-C":                         {"url":"https://ezpeptides.com/product/lipo-c-with-b12-10ml-research-grade-solution/","mg":10},
    "LIPO-C with B12":                {"url":"https://ezpeptides.com/product/lipo-c-with-b12-10ml-research-grade-solution/","mg":10},
    "GHK-Cu Lyophilized":             {"url":"https://ezpeptides.com/product/ghk-cu-50mg/","mg":50},
    "Klow Blend":                     {"url":"https://ezpeptides.com/product/klow-blend-80mg/","mg":80},
    "ARA-290":                        {"url":"https://ezpeptides.com/product/ara-290-10mg/","mg":10},
    "Beauty Blend (GHK-Cu/KPV)":      {"url":"https://ezpeptides.com/product/beauty-blend-ghk-cu-kpv-blend-50mg-20mg/","mg":50},
    "MOTS-c":                         {"url":"https://ezpeptides.com/product/mots-c-10mg/","mg":10},
    "KPV":                            {"url":"https://ezpeptides.com/product/kpv-10mg/","mg":10},
    "Semax":                          {"url":"https://ezpeptides.com/product/semax-10mg/","mg":10},
    "AOD-9604":                       {"url":"https://ezpeptides.com/product/aod-9604-5mg/","mg":5},
    "Tesamorelin":                    {"url":"https://ezpeptides.com/product/tesamorelin-10mg/","mg":10},
    "Selank":                         {"url":"https://ezpeptides.com/product/selank-10mg/","mg":10},
    "Sermorelin":                     {"url":"https://ezpeptides.com/product/sermorelin-5mg/","mg":5},
    "DSIP":                           {"url":"https://ezpeptides.com/product/dsip-10mg/","mg":10},
    "Adamax":                         {"url":"https://ezpeptides.com/product/adamax-10mg/","mg":10},
  },
  "amp": {
    "Semaglutide":                    {"url":"https://ameanopeptides.com/product/amp-1p-5mg/","mg":5},
    "Tirzepatide":                    {"url":"https://ameanopeptides.com/product/amp-2p-10mg/","mg":10},
    "Retatrutide":                    {"url":"https://ameanopeptides.com/product/amp-3p-10mg/","mg":10},
    "BPC-157":                        {"url":"https://ameanopeptides.com/product/bpc-157-10mg/","mg":10},
    "TB-500":                         {"url":"https://ameanopeptides.com/product/tb4-10mg-research-peptide/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://ameanopeptides.com/product/bpc-157-tb4-blend-10mg-10mg/","mg":10},
    "Ipamorelin":                     {"url":"https://ameanopeptides.com/product/ipamorelin-10mg/","mg":10},
    "Epithalon":                      {"url":"https://ameanopeptides.com/product/epitalon-10mg/","mg":10},
    "Melanotan II":                   {"url":"https://ameanopeptides.com/product/melanotan-ii-10mg/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://ameanopeptides.com/product/pt-141-10mg-research-peptide/","mg":10},
    "GHK-Cu":                         {"url":"https://ameanopeptides.com/product/ghk-cu-100mg/","mg":100},
    "Buffered NAD+ 250mg":            {"url":"https://ameanopeptides.com/product/nad-250mg-buffered/","mg":250},
    "LIPO-C with B12":                {"url":"https://ameanopeptides.com/product/lipo-c-with-b12-10ml/","mg":10},
    "Klow Blend":                     {"url":"https://ameanopeptides.com/product/klow-blend-80mg-research-peptide/","mg":80},
    "Reta/Cagri Blend":               {"url":"https://ameanopeptides.com/product/reta-cagri-blend/","mg":12},
    "Tesamorelin/Ipamorelin Blend":   {"url":"https://ameanopeptides.com/product/tesamorelin-ipamorelin-blend-10mg-3mg/","mg":10},
    "MOTS-c":                         {"url":"https://ameanopeptides.com/product/mots-c-10mg/","mg":10},
    "KPV":                            {"url":"https://ameanopeptides.com/product/kpv-10mg/","mg":10},
    "AOD-9604":                       {"url":"https://ameanopeptides.com/product/aod-9604-5mg/","mg":5},
    "Tesamorelin":                    {"url":"https://ameanopeptides.com/product/tesamorelin-10mg-research-peptide/","mg":10},
    "Selank":                         {"url":"https://ameanopeptides.com/product/n-acetyl-selank-amidate-10mg-research-peptide/","mg":10},
    "Sermorelin":                     {"url":"https://ameanopeptides.com/product/sermorelin-5mg/","mg":5},
    "DSIP":                           {"url":"https://ameanopeptides.com/product/dsip-10mg/","mg":10},
    "Adamax":                         {"url":"https://ameanopeptides.com/product/adamax-10mg/","mg":10},
  },
  "labsourced": {
    "Tirzepatide":                    {"url":"https://www.labsourced.com/products/tirzepatide-30mg","mg":30},
    "Retatrutide":                    {"url":"https://www.labsourced.com/products/peptide-r-5mg","mg":5},
    "BPC-157":                        {"url":"https://www.labsourced.com/products/bpc-157-10mg","mg":10},
    "TB-500":                         {"url":"https://www.labsourced.com/products/tb-500-10mg","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://www.labsourced.com/products/wolverine-10-10mg","mg":10},
    "Ipamorelin":                     {"url":"https://www.labsourced.com/products/ipamorelin-10mg","mg":10},
    "Epithalon":                      {"url":"https://www.labsourced.com/products/epithalon-10mg","mg":10},
    "Melanotan II":                   {"url":"https://www.labsourced.com/products/mt2-10mg","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://www.labsourced.com/products/pt-141-10mg","mg":10},
    "GHK-Cu":                         {"url":"https://www.labsourced.com/products/ghk-cu-50mg","mg":50},
    "Klow Blend":                     {"url":"https://www.labsourced.com/products/klow-80mg","mg":80},
    "MOTS-c":                         {"url":"https://www.labsourced.com/products/mots-c-10mg","mg":10},
    "NAD+":                           {"url":"https://www.labsourced.com/products/nad-500mg","mg":500},
    "KPV":                            {"url":"https://www.labsourced.com/products/kpv-10mg","mg":10},
    "Semax":                          {"url":"https://www.labsourced.com/products/semax-10mg","mg":10},
    "AOD-9604":                       {"url":"https://www.labsourced.com/products/aod-9604-5mg","mg":5},
    "Tesamorelin":                    {"url":"https://www.labsourced.com/products/tesamorelin-10mg","mg":10},
    "Sermorelin":                     {"url":"https://www.labsourced.com/products/sermorelin-10mg","mg":10},
    "DSIP":                           {"url":"https://www.labsourced.com/products/dsip-5mg","mg":5},
  },
  "ion": {
    "Semaglutide":                    {"url":"https://ionpeptide.com/product/glp-1s/","mg":5},
    "Tirzepatide":                    {"url":"https://ionpeptide.com/product/glp-2t/","mg":10},
    "Retatrutide":                    {"url":"https://ionpeptide.com/product/glp-3r/","mg":5},
    "BPC-157":                        {"url":"https://ionpeptide.com/product/bpc-157-2/","mg":5},
    "TB-500":                         {"url":"https://ionpeptide.com/product/tb-500/","mg":5},
    "BPC-157 + TB-500 Blend":         {"url":"https://ionpeptide.com/product/bpc157tb500/","mg":10},
    "Ipamorelin":                     {"url":"https://ionpeptide.com/product/ipamorelin/","mg":5},
    "CJC-1295 (with DAC)":            {"url":"https://ionpeptide.com/product/cjc-1295-with-dac-5mg/","mg":5},
    "Epithalon":                      {"url":"https://ionpeptide.com/product/epithalon/","mg":10},
    "Melanotan II":                   {"url":"https://ionpeptide.com/product/melanotan-ii/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://ionpeptide.com/product/pt-141/","mg":10},
    "GHK-Cu":                         {"url":"https://ionpeptide.com/product/ghk-cu-2/","mg":50},
    "LIPO-C with B12":                {"url":"https://ionpeptide.com/product/lipo-c-b12-methylated-10mg/","mg":10},
    "Klow Blend":                     {"url":"https://ionpeptide.com/product/klow/","mg":80},
    "ARA-290":                        {"url":"https://ionpeptide.com/product/ara-290/","mg":10},
    "Tesamorelin/Ipamorelin Blend":   {"url":"https://ionpeptide.com/product/tesamorelin-ipamorelin-10mg/","mg":10},
    "MOTS-c":                         {"url":"https://ionpeptide.com/product/mots-c/","mg":10},
    "NAD+":                           {"url":"https://ionpeptide.com/product/nad/","mg":500},
    "KPV":                            {"url":"https://ionpeptide.com/product/kpv-10/","mg":10},
    "Semax":                          {"url":"https://ionpeptide.com/product/semax/","mg":10},
    "AOD-9604":                       {"url":"https://ionpeptide.com/product/aod-9604-2/","mg":5},
    "Tesamorelin":                    {"url":"https://ionpeptide.com/product/tesamorelin/","mg":5},
    "Selank":                         {"url":"https://ionpeptide.com/product/selank-2/","mg":5},
    "Sermorelin":                     {"url":"https://ionpeptide.com/product/sermorelin/","mg":5},
    "DSIP":                           {"url":"https://ionpeptide.com/product/dsip/","mg":5},
    "Adamax":                         {"url":"https://ionpeptide.com/product/adamax-10mg/","mg":10},
    "Lipo-C":                         {"url":"https://ionpeptide.com/product/lipo-c-b12-methylated-10mg/","mg":10},
    "SS-31":                          {"url":"https://ionpeptide.com/product/ss-31/","mg":10},
    "Glutathione":                    {"url":"https://ionpeptide.com/product/glutathione/","mg":600},
  },
  "retaone": {
    "Semaglutide":                    {"url":"https://retaonelabs.com/product/ro-1s-10mg/","mg":10},
    "Tirzepatide":                    {"url":"https://retaonelabs.com/product/ro-2t-10mg/","mg":10},
    "Retatrutide":                    {"url":"https://retaonelabs.com/product/ro-3r-10mg/","mg":10},
    "BPC-157":                        {"url":"https://retaonelabs.com/product/bpc-157-10mg/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://retaonelabs.com/product/bpc-157-tb-500-blend-10mg-10mg/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://retaonelabs.com/product/pt-141-10mg/","mg":10},
    "GHK-Cu":                         {"url":"https://retaonelabs.com/product/ghk-cu-50mg/","mg":50},
    "Research Diluent Solution":      {"url":"https://retaonelabs.com/product/research-diluent-solution-10ml/","mg":10},
    "MOTS-c":                         {"url":"https://retaonelabs.com/product/mots-c/","mg":10},
    "NAD+":                           {"url":"https://retaonelabs.com/product/nad-500mg/","mg":500},
    "Tesamorelin":                    {"url":"https://retaonelabs.com/product/tesamorelin-10mg/","mg":10},
  },
  "nura": {
    "Semaglutide":                    {"url":"https://nurapeptide.com/product/glp-1sg-10mg/","mg":10},
    "Tirzepatide":                    {"url":"https://nurapeptide.com/product/glp-2t-10mg/","mg":10},
    "Retatrutide":                    {"url":"https://nurapeptide.com/product/glp-3rt-12mg/","mg":12},
    "BPC-157":                        {"url":"https://nurapeptide.com/product/bpc-157-10mg/","mg":10},
    "TB-500":                         {"url":"https://nurapeptide.com/product/tb-500-10mg/","mg":10},
    "BPC-157 + TB-500 Blend":         {"url":"https://nurapeptide.com/product/bpc-157-tb-500-5-5mg/","mg":5},
    "Ipamorelin":                     {"url":"https://nurapeptide.com/product/ipamorelin-10mg/","mg":10},
    "CJC-1295 (with DAC)":            {"url":"https://nurapeptide.com/product/cjc-1295-with-dac-5mg/","mg":5},
    "Epithalon":                      {"url":"https://nurapeptide.com/product/epitalon-10mg/","mg":10},
    "Melanotan II":                   {"url":"https://nurapeptide.com/product/melanotan-ii-10mg/","mg":10},
    "PT-141 (Bremelanotide)":         {"url":"https://nurapeptide.com/product/pt-141-peptide-10mg/","mg":10},
    "GHK-Cu":                         {"url":"https://nurapeptide.com/product/ghk-cu-100mg/","mg":100},
    "Bacteriostatic Water":           {"url":"https://nurapeptide.com/product/bacteriostatic-water-10ml/","mg":10},
    "Bacteriostatic Water 30mL":      {"url":"https://nurapeptide.com/product/bacteriostatic-water/","mg":30},
    "Klow Blend":                     {"url":"https://nurapeptide.com/product/klow-bpc-157-ghk-cu-tb-500-kpv-blend/","mg":10},
    "Tesamorelin/Ipamorelin Blend":   {"url":"https://nurapeptide.com/product/tesamorelin-ipamorelin-13-3-mg/","mg":13},
    "MOTS-c":                         {"url":"https://nurapeptide.com/product/mots-c-10mg/","mg":10},
    "NAD+":                           {"url":"https://nurapeptide.com/product/nad-500mg/","mg":500},
    "KPV":                            {"url":"https://nurapeptide.com/product/kpv-10mg/","mg":10},
    "Semax":                          {"url":"https://nurapeptide.com/product/semax-peptide-10mg/","mg":10},
    "AOD-9604":                       {"url":"https://nurapeptide.com/product/aod-9604-5mg/","mg":5},
    "Tesamorelin":                    {"url":"https://nurapeptide.com/product/tesamorelin-10mg/","mg":10},
    "Selank":                         {"url":"https://nurapeptide.com/product/selank-peptide-10mg/","mg":10},
    "Sermorelin":                     {"url":"https://nurapeptide.com/product/sermorelin-5mg/","mg":5},
    "DSIP":                           {"url":"https://nurapeptide.com/product/dsip-5mg/","mg":5},
    "Adamax":                         {"url":"https://nurapeptide.com/product/adamax-10mg/","mg":10},
    "SS-31":                          {"url":"https://nurapeptide.com/product/ss-31-50mg/","mg":50},
    "Glutathione":                    {"url":"https://nurapeptide.com/product/glutathione-peptide-1500mg/","mg":1500},
  },
}

# Vendors that need real browser (Cloudflare protected)
CLOUDFLARE_VENDORS = {"glacier", "milehigh", "ezpeptides", "nura"}

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

def parse_prices_block(html):
    result = {}
    pep_re = re.compile(r'"([^"]+)":\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
    vendor_re = re.compile(
        r'(\w+):\s*(?:null|\{[^}]*price\s*:\s*([\d.]+)[^}]*mg\s*:\s*([\d.]+)[^}]*\})',
        re.DOTALL
    )
    for m in pep_re.finditer(html):
        peptide = m.group(1)
        block = m.group(2)
        if 'price:' not in block:
            continue
        vendors = {}
        for vm in vendor_re.finditer(block):
            vid = vm.group(1)
            if vm.group(2) is None:
                continue
            vendors[vid] = {"price": float(vm.group(2)), "mg": float(vm.group(3))}
        if vendors:
            result[peptide] = vendors
    return result

def patch_prices(html, updates, out_of_stock_items):
    """
    Bulletproof line-by-line price patcher.
    Finds vendor lines like:
        ascension:{price:65.00,mg:5,listing:"Semaglutide 5mg"},
    and replaces just the price value. Never touches mg or listing.
    Also handles oos flag adding/removing.
    """
    patched = 0
    lines = html.split('\n')

    # Build a fast lookup: {peptide: {vid: new_price}}
    # and a set of oos items: {(peptide, vid)}
    oos_set = set(out_of_stock_items)

    # We track which peptide block we're currently inside
    current_peptide = None
    peptide_detect = re.compile(r'^\s*"([^"]+)":\s*\{')
    # Matches a vendor price line: vid:{price:XX.XX,mg:YY,...}
    vendor_line = re.compile(
        r'^(\s*)(\w+):\{price:([\d.]+)(,mg:[\d.]+,listing:"[^"]*")((?:,oos:true)?)\}(,?)\s*$'
    )
    # Also matches array format: vid:[{price:XX.XX,mg:YY,...},...]
    vendor_line_array = re.compile(
        r'^(\s*)(\w+):\[\{price:([\d.]+)(,mg:[\d.]+,listing:"[^"]*")((?:,oos:true)?)\}(.*?)\](,?)\s*$'
    )

    new_lines = []
    for line in lines:
        # Detect peptide block start
        pm = peptide_detect.match(line)
        if pm:
            current_peptide = pm.group(1)

        if current_peptide is None:
            new_lines.append(line)
            continue

        vm = vendor_line.match(line)
        vm_arr = vendor_line_array.match(line) if not vm else None
        matched = vm or vm_arr
        is_array = vm_arr is not None and vm is None

        if matched:
            indent    = matched.group(1)
            vid       = matched.group(2)
            price_val = matched.group(3)
            mg_list   = matched.group(4)   # e.g. ,mg:10,listing:"BPC-157 10mg"
            oos_part  = matched.group(5)
            rest      = matched.group(6) if is_array else ""   # remaining array items
            trailing  = matched.group(7) if is_array else matched.group(6)
            is_oos    = (current_peptide, vid) in oos_set

            # Check if we have a price update for this vendor
            new_price = updates.get(current_peptide, {}).get(vid)

            if new_price is not None:
                price_str = f"{new_price:.2f}"
                oos_flag = ",oos:true" if is_oos else ""
                if is_array:
                    new_line = f'{indent}{vid}:[{{price:{price_str}{mg_list}{oos_flag}}}{rest}]{trailing}'
                else:
                    new_line = f'{indent}{vid}:{{price:{price_str}{mg_list}{oos_flag}}}{trailing}'
                new_lines.append(new_line)
                patched += 1
                log.info(f"  PATCHED {current_peptide}/{vid}: ${price_val} → ${price_str}{chr(32)}[array={is_array}]{chr(32)}[OOS={is_oos}]")
            elif is_oos:
                oos_flag = ",oos:true"
                if is_array:
                    new_line = f'{indent}{vid}:[{{price:{price_val}{mg_list}{oos_flag}}}{rest}]{trailing}'
                else:
                    new_line = f'{indent}{vid}:{{price:{price_val}{mg_list}{oos_flag}}}{trailing}'
                if new_line.rstrip() != line.rstrip():
                    log.info(f"  Marked OOS: {current_peptide}/{vid}")
                new_lines.append(new_line)
            else:
                # Remove oos flag if no longer OOS
                clean = line.replace(',oos:true', '')
                new_lines.append(clean)
        else:
            new_lines.append(line)

    log.info(f"Patched {patched} prices")
    return '\n'.join(new_lines), patched

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


def main():
    log.info("=== PepsTracker Scraper v6 (daily + OOS) Starting ===")

    # Only scrape the 13 peptides shown in the dropdown — not the full 60-peptide catalog
    # Glacier and MileHigh block ScraperAPI (always timeout) — skip them to save time + credits
    ACTIVE_PEPTIDES = [
        # GLP-1
        "Semaglutide", "Tirzepatide", "Retatrutide",
        # BPC / TB
        "BPC-157", "TB-500", "BPC-157 + TB-500 Blend",
        # Growth Hormone
        "Ipamorelin", "CJC-1295 (with DAC)", "Sermorelin", "Tesamorelin",
        # Skin / Tanning
        "Melanotan II", "PT-141 (Bremelanotide)", "GHK-Cu",
        # Longevity
        "Epithalon", "MOTS-c", "NAD+",
        # Cognitive
        "Semax", "Selank", "DSIP", "Adamax",
        # Immune
        "KPV", "ARA-290",
        # Fat Loss
        "AOD-9604",
        # Blends
        "Klow Blend",
        "Tesamorelin/Ipamorelin Blend",
        # Immune / Metabolic
        "Lipo-C",
        # Mitochondrial
        "SS-31",
        # Antioxidant
        "Glutathione",
    ]
    # SKIP_VENDORS defined at module level — atomik, labsourced, retaone

    html, sha = github_get_file()

    existing = parse_prices_block(html)
    if not existing:
        log.error("Could not parse PRICES block — aborting")
        return
    log.info(f"Parsed {len(existing)} peptides from PRICES block")
    log.info(f"Scraping {len(ACTIVE_PEPTIDES)} active peptides")
    log.info(f"⏭ Skipping manual vendors (update via price-update.html): {', '.join(sorted(SKIP_VENDORS))}")

    updates = {}
    oos_items = []

    for peptide in ACTIVE_PEPTIDES:
        vendor_map = existing.get(peptide)
        if not vendor_map:
            log.warning(f"  {peptide} not found in PRICES block — skipping")
            continue
        for vid, info in vendor_map.items():
            if vid in SKIP_VENDORS:
                log.info(f"  Skipping {vid}/{peptide} (Cloudflare blocked)")
                continue
            url_info = PRODUCT_URLS.get(vid, {}).get(peptide)
            if not url_info:
                continue
            price, oos = fetch_price_from_url(vid, peptide, url_info["url"])
            if oos:
                oos_items.append((peptide, vid))
                run_stats["oos"].append((vid, peptide))
            elif price and abs(price - info["price"]) > 0.01:
                # Sanity check 1: hard price caps per peptide type
                # Prevents bundle/page errors from corrupting prices
                PRICE_CAPS = {
                    "Semaglutide": 150, "Tirzepatide": 200, "Retatrutide": 250,
                    "BPC-157": 100, "TB-500": 120, "BPC-157 + TB-500 Blend": 180,
                    "Ipamorelin": 100, "CJC-1295 (with DAC)": 100, "Sermorelin": 120,
                    "Tesamorelin": 150, "Melanotan II": 80, "PT-141 (Bremelanotide)": 100,
                    "GHK-Cu": 250, "Epithalon": 200, "MOTS-c": 150, "NAD+": 150,
                    "Semax": 100, "Selank": 100, "DSIP": 80, "Adamax": 100, "KPV": 100,
                    "ARA-290": 120, "AOD-9604": 80, "Klow Blend": 200,
                    "Tesamorelin/Ipamorelin Blend": 200,
                }
                cap = PRICE_CAPS.get(peptide, 300)
                if price > cap:
                    log.warning(f"  PRICE CAP FAIL {peptide}/{vid}: ${price:.2f} exceeds max ${cap:.2f} — skipping")
                    run_stats["price_capped"].append((vid, peptide, price, cap))
                    continue

                # Sanity check 2: reject prices > 4x or < 0.25x previous
                prev = info["price"]
                ratio = price / prev if prev > 0 else 999
                # Allow larger swings for peptides sold in different mg sizes
                # e.g. Epithalon: 10mg ($27) vs 50mg ($119) = 4.4x but both valid
                max_ratio = 6.0 if peptide in {
                    "Epithalon", "GHK-Cu", "NAD+", "Klow Blend",
                    "Tesamorelin/Ipamorelin Blend", "BPC-157 + TB-500 Blend"
                } else 4.0
                if ratio > max_ratio or ratio < 0.20:
                    log.warning(f"  SANITY FAIL {peptide}/{vid}: ${prev:.2f} → ${price:.2f} (ratio {ratio:.2f}x, max {max_ratio}x) — skipping")
                    run_stats["sanity_failed"].append((vid, peptide, prev, price))
                else:
                    updates.setdefault(peptide, {})[vid] = price
                    log.info(f"  CHANGE {peptide}/{vid}: ${prev:.2f} → ${price:.2f}")
            time.sleep(1.0)

    if not updates and not oos_items:
        log.info("No changes — skipping commit")
        return

    new_html, count = patch_prices(html, updates, oos_items)
    now = datetime.now(timezone.utc)
    # Update SCRAPE_DATE in the HTML so the site shows the real last-updated date
    scrape_date_str = now.strftime("%B %-d, %Y")  # e.g. "May 26, 2026"
    new_html = re.sub(
        r'const SCRAPE_DATE = "[^"]*";',
        f'const SCRAPE_DATE = "{scrape_date_str}";',
        new_html
    )
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")
    github_push_file(new_html, sha, f"🤖 Daily price update: {count} changes, {len(oos_items)} OOS ({now_str})")
    log.info(f"=== Done: {count} prices updated, {len(oos_items)} marked OOS ===")

    # ── Generate diagnostics report ──────────────────────────
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report_lines = [
        f"# PepsTracker Scraper Diagnostics",
        f"**Run:** {now_str}",
        f"**Result:** {count} prices updated, {len(oos_items)} OOS",
        "",
        "## ✅ Successful Fetches",
        f"Total: {len(run_stats['successes'])}",
    ]
    for vid, pep, price, elapsed in sorted(run_stats["successes"], key=lambda x: x[3], reverse=True)[:10]:
        report_lines.append(f"- {vid}/{pep}: ${price:.2f} ({elapsed:.1f}s)")

    if run_stats["blocked_403"]:
        report_lines += ["", "## 🚫 Cloudflare Blocked (403)"]
        report_lines.append("**FIX: Add these to CLOUDFLARE_VENDORS in scraper.py**")
        vendors_403 = {}
        for vid, pep in run_stats["blocked_403"]:
            vendors_403.setdefault(vid, []).append(pep)
        for vid, peps in vendors_403.items():
            report_lines.append(f"- **{vid}** ({len(peps)} products blocked): {', '.join(peps[:5])}")

    if run_stats["timeouts"]:
        report_lines += ["", "## ⏱ Timeouts"]
        vendors_to = {}
        for vid, pep, elapsed in run_stats["timeouts"]:
            vendors_to.setdefault(vid, []).append(f"{pep} ({elapsed:.0f}s)")
        for vid, items in vendors_to.items():
            report_lines.append(f"- **{vid}**: {', '.join(items[:5])}")
        slow_vendors = set(v for v, p, e in run_stats["timeouts"] if e > 45)
        if slow_vendors:
            report_lines.append(f"\n**Consistently slow vendors:** {', '.join(slow_vendors)}")

    if run_stats["url_404"]:
        report_lines += ["", "## ❌ 404 Not Found (URL needs updating)"]
        for vid, pep in run_stats["url_404"]:
            report_lines.append(f"- {vid}/{pep} — check URL in PRODUCT_URLS")

    if run_stats["price_capped"]:
        report_lines += ["", "## 🔒 Price Cap Failures"]
        report_lines.append("These prices were blocked by caps — may need cap adjustment:")
        for vid, pep, price, cap in run_stats["price_capped"]:
            report_lines.append(f"- {vid}/{pep}: got ${price:.2f}, cap is ${cap:.2f}")

    if run_stats["sanity_failed"]:
        report_lines += ["", "## ⚠️ Sanity Check Failures"]
        report_lines.append("Price changed too dramatically — investigate:")
        for vid, pep, prev, new_p in run_stats["sanity_failed"]:
            pct = ((new_p/prev)-1)*100 if prev else 0
            report_lines.append(f"- {vid}/{pep}: ${prev:.2f} → ${new_p:.2f} ({pct:+.0f}%)")

    if run_stats["not_found"]:
        report_lines += ["", "## 🔍 Price Not Found"]
        vendors_nf = {}
        for item in run_stats["not_found"]:
            vid, pep = item[0], item[1]
            vendors_nf.setdefault(vid, []).append(pep)
        for vid, peps in vendors_nf.items():
            report_lines.append(f"- **{vid}** ({len(peps)}): {', '.join(peps[:8])}")

    report_lines += [
        "",
        "## 📊 Summary",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| ✅ Prices fetched | {len(run_stats['successes'])} |",
        f"| 💰 Prices updated | {count} |",
        f"| 🚫 Cloudflare 403 | {len(run_stats['blocked_403'])} |",
        f"| ⏱ Timeouts | {len(run_stats['timeouts'])} |",
        f"| ❌ 404 URLs | {len(run_stats['url_404'])} |",
        f"| 🔒 Price capped | {len(run_stats['price_capped'])} |",
        f"| ⚠️ Sanity failed | {len(run_stats['sanity_failed'])} |",
        f"| 📦 OOS | {len(run_stats['oos'])} |",
    ]

    report = "\n".join(report_lines)
    log.info("\n" + "="*60)
    log.info("DIAGNOSTICS REPORT:")
    log.info(report)
    log.info("="*60)

    # Push report to GitHub as SCRAPER_REPORT.md
    try:
        report_file = "SCRAPER_REPORT.md"
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{report_file}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
        report_sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {
            "message": f"📊 Scraper report {now_str}",
            "content": base64.b64encode(report.encode()).decode(),
            "branch": "main"
        }
        if report_sha:
            payload["sha"] = report_sha
        requests.put(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"}, json=payload)
        log.info("Pushed diagnostics report to SCRAPER_REPORT.md")
    except Exception as e:
        log.warning(f"Could not push report: {e}")

    log.info(f"=== Run complete. Check SCRAPER_REPORT.md in GitHub for full diagnostics ===")

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
