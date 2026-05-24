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
  },
}

def scraper_get(url, render_js=False, timeout=45):
    params = {
        "api_key": SCRAPERAPI_KEY,
        "url": url,
        "render": "true" if render_js else "false",
        "keep_headers": "true",
    }
    return requests.get("https://api.scraperapi.com/", params=params, timeout=timeout)

def parse_price(val):
    try:
        v = float(str(val).replace(",", "").replace("$", "").strip())
        return v if 1.0 < v < 10000 else None
    except Exception:
        return None

def is_out_of_stock(html):
    oos_signals = [
        'class="out-of-stock"', 'stock_status":"outofstock"',
        '"availability":"http://schema.org/OutOfStock"',
        'availability":"OutOfStock"', '>Out of stock<',
        '>Currently unavailable<', '>Sold out<',
        'sold_out":true', '"sold_out": true',
        'outofstock', 'out-of-stock',
    ]
    html_lower = html.lower()
    return any(s.lower() in html_lower for s in oos_signals)

def extract_main_product_price(html):
    # Strip shipping banners
    html = re.sub(r'[^<]{0,80}free\s*ship[^<]{0,150}\$\s*[\d,]+\.?\d*[^<]{0,80}', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\$\s*[\d,]+\.?\d*[^<]{0,80}free\s*ship[^<]{0,150}', '', html, flags=re.IGNORECASE)

    # Cut off related sections
    for pattern in [r'<section[^>]*class="[^"]*related', r'<div[^>]*class="[^"]*related',
                    r'<section[^>]*class="[^"]*upsell', r'id="related']:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            html = html[:m.start()]

    # JSON-LD
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Product":
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        prices = [parse_price(o.get("price") or o.get("lowPrice")) for o in offers]
                        prices = [p for p in prices if p]
                        if prices: return min(prices)
                    else:
                        p = parse_price(offers.get("price") or offers.get("lowPrice"))
                        if p: return p
        except Exception:
            pass

    # WooCommerce price spans
    for pattern in [
        r'class="woocommerce-Price-amount[^"]*"[^>]*>.*?<bdi>.*?\$\s*([\d,]+\.?\d*)',
        r'"price"\s*:\s*"([\d.]+)"',
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
    log.info(f"  Fetching {vendor_id}/{product} → {product_url}")
    try:
        resp = scraper_get(product_url, render_js=False)
        if resp.status_code != 200:
            log.warning(f"  HTTP {resp.status_code}")
            return None, False
        html = resp.text
        if is_out_of_stock(html):
            log.info(f"  OUT OF STOCK: {vendor_id}/{product}")
            return None, True
        price = extract_main_product_price(html)
        if not price:
            log.info(f"  Retrying with JS...")
            resp2 = scraper_get(product_url, render_js=True)
            if resp2.status_code == 200:
                html2 = resp2.text
                if is_out_of_stock(html2):
                    return None, True
                price = extract_main_product_price(html2)
        log.info(f"  {'OK' if price else '--'} {vendor_id}/{product}: {'${:.2f}'.format(price) if price else 'not found'}")
        return price, False
    except Exception as e:
        log.warning(f"  ERR {vendor_id}/{product}: {e}")
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
        r'^(\s*)(\w+):((?:\{price:)([\d.]+)(,mg:[\d.]+,listing:"[^"]*")((?:,oos:true)?)\})(,?)(\s*)$'
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
        if vm:
            indent    = vm.group(1)
            vid       = vm.group(2)
            price_val = vm.group(4)
            mg_list   = vm.group(5)   # e.g. ,mg:10,listing:"BPC-157 10mg"
            trailing  = vm.group(7)   # comma after }
            is_oos    = (current_peptide, vid) in oos_set

            # Check if we have a price update for this vendor
            new_price = updates.get(current_peptide, {}).get(vid)

            if new_price is not None:
                price_str = f"{new_price:.2f}"
                oos_flag = ",oos:true" if is_oos else ""
                new_line = f'{indent}{vid}:{{price:{price_str}{mg_list}{oos_flag}}}{trailing}'
                new_lines.append(new_line)
                patched += 1
                log.info(f"  PATCHED {current_peptide}/{vid}: ${price_val} → ${price_str}{' [OOS]' if is_oos else ''}")
            elif is_oos:
                # No price update but mark OOS
                oos_flag = ",oos:true"
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

def main():
    log.info("=== PepsTracker Scraper v6 (daily + OOS) Starting ===")
    html, sha = github_get_file()

    existing = parse_prices_block(html)
    if not existing:
        log.error("Could not parse PRICES block — aborting")
        return
    log.info(f"Parsed {len(existing)} peptides from PRICES block")

    updates = {}
    oos_items = []

    for peptide, vendor_map in existing.items():
        for vid, info in vendor_map.items():
            url_info = PRODUCT_URLS.get(vid, {}).get(peptide)
            if not url_info:
                continue
            price, oos = fetch_price_from_url(vid, peptide, url_info["url"])
            if oos:
                oos_items.append((peptide, vid))
            elif price and abs(price - info["price"]) > 0.01:
                updates.setdefault(peptide, {})[vid] = price
                log.info(f"  CHANGE {peptide}/{vid}: ${info['price']:.2f} → ${price:.2f}")
            time.sleep(1.5)

    if not updates and not oos_items:
        log.info("No changes — skipping commit")
        return

    new_html, count = patch_prices(html, updates, oos_items)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    github_push_file(new_html, sha, f"🤖 Daily price update: {count} changes, {len(oos_items)} OOS ({now})")
    log.info(f"=== Done: {count} prices updated, {len(oos_items)} marked OOS ===")

if __name__ == "__main__":
    main()
