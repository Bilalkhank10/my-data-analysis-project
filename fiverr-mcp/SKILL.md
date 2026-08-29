---
name: fiverr-niche-fetcher
description: >-
  Fiverr public market intelligence MCP server.
  Exposes three tools powered by the Jina Reader proxy (no login required):
  - search_fiverr_gigs: search a niche keyword and return ranked gig cards
    (title, seller, price, rating, badges, thumbnail, organic/sponsored rank).
  - fetch_gig_details: fetch a single gig URL and return full detail including
    packages (Basic/Standard/Premium with pricing), FAQs, visible reviews,
    related tags, media gallery URLs, and JSON-LD structured data.
  - crawl_fiverr_niche: run the complete two-stage pipeline (search then detail
    pages) and return merged results with crawl statistics.
  All data is public-only. No Fiverr account or API key required.
---

# Fiverr Niche Fetcher MCP

This skill installs the **Fiverr Niche Fetcher** MCP server, which crawls
Fiverr public search results and gig detail pages via the Jina Reader proxy.

## Tools

### `search_fiverr_gigs`
Search Fiverr for gigs matching a niche keyword.

**Inputs**
- `niche` (string, required) — e.g. `"logo design"`
- `limit` (integer, default 20) — max gig cards to return (1–500)
- `max_search_pages` (integer, default 5) — pages to scan (1–30)

### `fetch_gig_details`
Fetch the full detail page for one Fiverr gig URL.

**Inputs**
- `url` (string, required) — e.g. `"https://www.fiverr.com/user/gig-slug"`

### `crawl_fiverr_niche`
Full two-stage pipeline: search → fetch all detail pages.

**Inputs**
- `niche` (string, required)
- `limit` (integer, default 10, max 50)
- `max_concurrency` (integer, default 2, max 5)
- `delay_seconds` (number, default 2.0)

## Setup

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Register `mcp_server.py` in your MCP client config
   (see `lobehub_config.json` or `claude_desktop_config.json`).
