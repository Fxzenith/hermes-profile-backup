---
name: yellosa-cdp-scrape
description: Scrape Yellosa leads, merge into one deduped CSV, optionally push to Google Sheets.
version: 0.2.0
author: Hermes
platforms: [linux]
metadata.hermes.tags: [Yellosa, Leads, Scraping, Composio, Google-Sheets]
---

# Yellosa Leads Pipeline

End-to-end: scrape business profiles from yellosa.co.za via the Chrome DevTools
Protocol, structure the data (contacts, website, year, employees, Q&A), export each
run to CSV, then **always merge every per-run CSV in the output folder into one
deduped master file**. Optionally push the master CSV to Google Sheets through
Composio. Uses system Chromium (snap) driven by puppeteer-core; no browser download.

NOTE: Telegram delivery was removed — the pipeline no longer sends CSVs to chat.
The single source of truth is the merged master CSV in the output folder.

## When to Use
- "Get businesses from Yellosa", "scrape Yellosa <city> leads", "pull Pretoria companies".
- "Put these Yellosa leads into a Google Sheet".
- Any task needing Yellosa company contacts, WhatsApp, websites, or Q&A.

## Prerequisites
- Linux with snap Chromium: `/snap/chromium/current/usr/lib/chromium-browser/chrome`.
  If missing: `snap install chromium`.
- Node + puppeteer-core in the project dir: `npm init -y && npm install puppeteer-core@23`.
  Run node scripts FROM that dir (require() resolution depends on it).
- For Sheets push: Composio CLI at `~/.composio/composio`, logged into the SAME Google
  account you'll authorize Sheets with. `composio whoami` must show that identity.

## How to Run
- Scrape (parameterized): `cd /root/scraper && CITY=pretoria CATEGORY=electrical-service TARGET=20 node scripts/scrape.js`.
  Output JSON lands at `/root/scraper/<city>[_<category>]_businesses.json`.
- Export CSV: `python3 scripts/export_csv.py <city>[_<category>]_businesses.json "/root/projects/Yellosa Leads/<city>[_<category>]_businesses.csv"`.
- **Merge (ALWAYS, final step):** `python3 scripts/merge_csv.py --dir "/root/projects/Yellosa Leads" --out "/root/projects/Yellosa Leads/<city>_all_businesses.csv"`.
  Dedups across all CSVs in the folder by company URL then normalized name; the master
  file is auto-excluded from its own inputs.
- **Push to Notion (new):** See NOTION upsert section below.
- Sheets (optional — removed): previously required Composio Google Sheets connection.

## Quick Reference
- Listings: `https://yellosa.co.za/location/<city>` · page N: `?page=N`
- Category listings: `https://yellosa.co.za/category/<slug>/city:<city>` (NOT `/location/<city>/<slug>` — that silently serves the default page). Discover slugs: `node /root/scraper/find_cats.js` (prints all `/category/.../city:pretoria` links).
- Profile: `https://yellosa.co.za/company/<id>/<slug>` · Q&A: `https://yellosa.co.za/question/<id>`
- Field DOM: `.cmp_details .info .label` + `.text`; categories `.cmp_details .tags a`.
- Composio toolkit slug: `googlesheets`; tools `GOOGLESHEETS_CREATE_GOOGLE_SHEET1`, `GOOGLESHEETS_VALUES_UPDATE`, `GOOGLESHEETS_VALUES_GET`.

## Procedure
1. **Env check** (terminal): confirm Chromium path, node, puppeteer-core present.
2. **Scrape** (terminal): `cd /root/scraper && CITY=pretoria CATEGORY=electrical-service TARGET=20 node scripts/scrape.js`.
   Collects listing links from the category/location page (page 2 is a duplicate, so it stops at
   page 1), opens each profile, reads fields + Q&A, saves `/root/scraper/<city>[_<category>]_businesses.json`.
   One tab per business, `networkidle2`, 300ms gaps. Fault-tolerant: a failed business is logged, not fatal.
3. **Export CSV** (terminal): `python3 scripts/export_csv.py <city>[_<category>]_businesses.json "/root/projects/Yellosa Leads/<city>[_<category>]_businesses.csv"`.
   Decodes `redir?u=<encoded>` website URLs to clean domains; strips "View MapGet Directions"
   from address; flattens Q&A to `Q: .. | A: ..` joined by ` || `.
4. **MERGE (mandatory, final step)** — combine all per-run CSVs in the output folder into one
   deduped master file. Run from any cwd:
   ```bash
   python3 scripts/merge_csv.py --dir "/root/projects/Yellosa Leads" \
     --out "/root/projects/Yellosa Leads/<city>_all_businesses.csv"
   ```
   Dedup key is company URL then normalized name; the master file is auto-excluded from its own
   inputs, so re-running merge is safe and idempotent. The master CSV is now the single source of truth.
5. **Notion upsert** (new step): parse the master CSV and upsert rows into Notion database.
   See the `upsert_notion` command below.
6. **Push to Google Sheets via Composio** — *removed; Notion is now the single source of truth*.

## Pitfalls