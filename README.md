# PepsTracker Price Scraper

Automatically scrapes peptide prices from all 11 vendor sites and updates `pepstracker_fixed/index.html` hourly via GitHub Actions.

## How it works

1. **GitHub Action** triggers every hour
2. **scraper.py** fetches `index.html` from GitHub, scrapes live prices, patches the file, and pushes back
3. **Netlify** detects the push and auto-deploys the updated site

## Setup (one-time)

### 1. Add these files to your repo

Copy into the root of `Thepepstracker/pepstracker`:
- `scraper.py`
- `requirements.txt`
- `.github/workflows/scrape-prices.yml`

### 2. Create a GitHub Personal Access Token

Go to: **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**

- Token name: `PepsTracker Scraper`
- Expiration: No expiration (or 1 year)
- Repository access: Only `Thepepstracker/pepstracker`
- Permissions:
  - **Contents** → Read and write
  - **Actions** → Read (optional, for triggering manually)

Copy the token.

### 3. Add token as a GitHub Secret

Go to: `github.com/Thepepstracker/pepstracker` → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

- Name: `SCRAPER_GITHUB_TOKEN`
- Value: paste your token

### 4. Verify Netlify auto-deploy is on

In Netlify → pepstracker.com → **Project configuration** → **Continuous deployment** → make sure auto-publishing is enabled.

That's it! The scraper will run every hour automatically.

## Manual run

Go to: `github.com/Thepepstracker/pepstracker` → **Actions** → **PepsTracker Price Scraper** → **Run workflow**

## What gets scraped

- All 11 vendors in rotating batches of 15 peptides per hour
- Only updates prices where vendors currently carry the product (null entries stay null)
- Commits to main branch with message: `🤖 Auto-update prices: X changes (YYYY-MM-DD HH:MM UTC)`

## Troubleshooting

- Check **Actions** tab in GitHub for logs
- If a vendor blocks scraping, that vendor's prices stay unchanged (safe fallback)
- The scraper uses polite 1-second delays between requests
