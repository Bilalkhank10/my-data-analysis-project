# Fiverr Niche Fetcher — MCP Server

A plug-and-play **Model Context Protocol (MCP)** server that exposes Fiverr
public market data as AI tools.  Works with **LobeHub**, **Claude Desktop**,
**Cursor**, **Antigravity**, and any other MCP-compatible client.

---

## What tools does it expose?

| Tool | Description |
|------|-------------|
| `search_fiverr_gigs` | Search Fiverr for a niche keyword and get ranked gig cards (title, seller, price, rating, badges, thumbnails) |
| `fetch_gig_details` | Fetch a single gig URL and get full detail: packages (Basic/Standard/Premium), FAQs, reviews, related tags, media |
| `crawl_fiverr_niche` | Full pipeline — search **+** fetch detail pages for every discovered gig in one call |

> All data is fetched via the **public Jina Reader proxy** (`r.jina.ai`).
> No Fiverr account or API key is needed.

---

## Files in this folder

```
fiverr-mcp/
├── mcp_server.py            # The MCP server (run this)
├── fiverr_fetcher.py        # Core crawl engine (do not rename/move)
├── requirements.txt         # Python dependencies
├── lobehub_config.json      # Ready-to-paste config for LobeHub
├── claude_desktop_config.json  # Config for Claude Desktop
└── README.md                # This file
```

---

## Quick Setup

### Step 1 — Install Python dependencies

Open a terminal inside this folder and run:

```bash
pip install -r requirements.txt
```

Or with a virtual environment:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2 — Note the full path of this folder

**Windows example:**
```
C:\Users\YourName\fiverr-mcp
```
**Mac / Linux example:**
```
/home/yourname/fiverr-mcp
```

---

## Platform Setup

### LobeHub (recommended)

1. Open LobeHub → **Settings** → **Skills** → **Add custom skill**
2. Click **Import JSON config**
3. Open `lobehub_config.json`, replace BOTH `REPLACE_WITH_FULL_PATH` placeholders
   with the actual path to this folder, then paste the JSON.
4. Save and enable the skill.

**Windows example after replacing:**
```json
{
  "mcpServers": {
    "fiverr-niche-fetcher": {
      "type": "stdio",
      "command": "python",
      "args": ["C:\\Users\\YourName\\fiverr-mcp\\mcp_server.py"],
      "env": {
        "PYTHONPATH": "C:\\Users\\YourName\\fiverr-mcp",
        "ALLOW_READER_FALLBACK": "true",
        "MAX_CONCURRENCY": "2",
        "REQUEST_DELAY_SECONDS": "2.0",
        "MAX_SEARCH_PAGES": "10",
        "SEARCH_PAGE_DELAY_SECONDS": "0.75",
        "RETRY_COUNT": "3",
        "RETRY_BASE_DELAY_SECONDS": "1.0",
        "READER_TIMEOUT_SECONDS": "90"
      }
    }
  }
}
```

> Tip: If you used a virtual environment, change `"command"` to the full path of
> `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` (Mac/Linux).

---

### Claude Desktop

1. Open your Claude Desktop config file:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Merge the contents of `claude_desktop_config.json` into it,
   replacing both `REPLACE_WITH_FULL_PATH` with your actual folder path.
3. Restart Claude Desktop.

---

### Cursor / Windsurf / other stdio clients

Add this to your client's MCP config, replacing the path:

```json
{
  "mcpServers": {
    "fiverr-niche-fetcher": {
      "command": "python",
      "args": ["FULL_PATH_TO/fiverr-mcp/mcp_server.py"],
      "env": {
        "PYTHONPATH": "FULL_PATH_TO/fiverr-mcp"
      }
    }
  }
}
```

---

## Tool Reference

### `search_fiverr_gigs`

```json
{
  "niche": "logo design",
  "limit": 20,
  "max_search_pages": 5
}
```

**Returns:** list of gig cards with `url`, `card_title`, `card_seller_name`,
`card_seller_level`, `card_rating`, `card_review_count`, `card_price`,
`thumbnail_url`, `is_sponsored`, `organic_position`, `badges`.

---

### `fetch_gig_details`

```json
{
  "url": "https://www.fiverr.com/someuser/design-amazing-logo"
}
```

**Returns:** full `GigRecord` with `title`, `seller_*` fields, `rating`,
`packages` (Basic/Standard/Premium with prices and features), `faqs`,
`visible_reviews`, `related_tags`, `media_urls`, `json_ld`.

---

### `crawl_fiverr_niche`

```json
{
  "niche": "python web scraping",
  "limit": 10,
  "max_concurrency": 2,
  "delay_seconds": 2.0
}
```

**Returns:** `{ niche, started_at, finished_at, discovered_count,
success_count, failed_count, results: [ { ...GigRecord, search: SearchRecord } ] }`

---

## Environment Variables

You can override defaults via the `env` block in the config:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENCY` | `2` | Parallel gig-detail workers |
| `REQUEST_DELAY_SECONDS` | `2.0` | Delay between gig fetches |
| `MAX_SEARCH_PAGES` | `10` | Max search pages to scan |
| `SEARCH_PAGE_DELAY_SECONDS` | `0.75` | Delay between search pages |
| `RETRY_COUNT` | `3` | Retry attempts on network errors |
| `RETRY_BASE_DELAY_SECONDS` | `1.0` | Base delay for exponential backoff |
| `READER_TIMEOUT_SECONDS` | `90` | Timeout per Jina Reader request |
| `ALLOW_READER_FALLBACK` | `true` | Must stay `true` |

---

## Notes

- Data is **public only** — no login, no CAPTCHA bypass, no private analytics.
- All HTTP goes through `r.jina.ai` (Jina Reader public proxy).
- Rate-limit settings are intentionally conservative — do not reduce delays aggressively.
