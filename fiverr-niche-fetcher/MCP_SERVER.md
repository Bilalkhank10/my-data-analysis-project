# MCP Server — Fiverr public market data for MCP clients

`mcp_server.py` exposes this project's **exact** Phase 1 public-crawl pipeline
(`fiverr_fetcher.FiverrNicheFetcher`) as [Model Context Protocol](https://modelcontextprotocol.io)
tools. Any MCP client — Claude Desktop, Claude Code, Cursor, VS Code Copilot,
or your own agent — can research public Fiverr niches through the same code the
web app uses.

Same pipeline, same parsed fields, same boundaries:

- public Fiverr pages only, fetched via the `r.jina.ai` reader service
- no login, no CAPTCHA bypass, no private analytics, no access-control circumvention
- same politeness knobs (`REQUEST_DELAY_SECONDS`, `MAX_CONCURRENCY`,
  `MAX_SEARCH_PAGES`, `RETRY_COUNT`, `READER_TIMEOUT_SECONDS`, `ALLOW_READER_FALLBACK`)

## Install

```bash
pip install -r requirements.txt -r requirements-mcp.txt
```

`requirements-mcp.txt` pins `mcp>=1.9,<2.0` (the stable FastMCP API).

## Tools

| Tool | What it does | Key arguments |
| --- | --- | --- |
| `fiverr_search` | Ordered public search cards for a niche: global rank, organic vs sponsored position, card title, seller name/username, level badges, rating, review count, starting price, online status, thumbnail, `available_results` total | `niche`, `limit` (1–100, env `MCP_SEARCH_LIMIT_MAX`), `include_raw` |
| `fiverr_gig` | Full public detail page for one gig URL: title, seller stats (level, country, member since, avg. response time, last delivery), rating + review count, starting price, category path, about text, Basic/Standard/Premium packages, FAQs, review summary + visible reviews (buyer country, date, price range, duration, seller response), related tags, gallery/video | `url`, `include_reviews` (0–50), `include_raw` |
| `fiverr_crawl` | The full two-stage pipeline in one call: search discovery, then every gig page. Each result = gig record + its `search` rank metadata. | `niche`, `limit` (1–25, env `MCP_CRAWL_LIMIT_MAX`), `include_reviews`, `include_raw` |
| `fiverr_listing_quality` | Deterministic listing-completeness score (title window, description, 3 packages, FAQ depth, video, gallery, rating, tags). **Not** Fiverr's private Success Score. | `url` |
| `fiverr_field_limits` | Static data, zero network: Fiverr form character limits and public rank-signal language from `fiverr_metadata.py` | — |

All tools return JSON dictionaries with an `ok` flag; failures come back as
`{"ok": false, "error": "..."}` so the agent can retry or explain the problem.

Typical agentic workflow:

1. `fiverr_field_limits` — learn the constraints (title ≤ 80 chars, 5 tags, …)
2. `fiverr_search "your niche"` — map who ranks, who is sponsored, price bands
3. `fiverr_gig <url>` or `fiverr_crawl "your niche" 10` — pull full detail
4. `fiverr_listing_quality <url>` — completeness check on a specific gig

## Run

### stdio (default — desktop clients)

```bash
python mcp_server.py
```

### HTTP (remote clients / sandboxed previews)

```bash
python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8765
# then connect clients to http://<host>:8765/mcp
```

`--transport sse` is also available for legacy clients. Host/port can also be
set via `MCP_HOST` / `MCP_PORT`; transport via `MCP_TRANSPORT`.

## Client configuration

### Claude Desktop / Claude Code (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "fiverr-niche-fetcher": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\fiverr-niche-fetcher\\mcp_server.py"],
      "env": {
        "REQUEST_DELAY_SECONDS": "2.0",
        "MAX_CONCURRENCY": "2",
        "MCP_CRAWL_LIMIT_MAX": "25"
      }
    }
  }
}
```

On macOS/Linux use the absolute path with `/`. Point `command` at the Python
that has both requirements files installed (a `.venv` interpreter is ideal).

### Cursor / VS Code (`mcp.json`)

```json
{
  "servers": {
    "fiverr-niche-fetcher": {
      "command": "python",
      "args": ["/full/path/to/fiverr-niche-fetcher/mcp_server.py"]
    }
  }
}
```

For HTTP mode use `"type": "http", "url": "http://localhost:8765/mcp"`.

### LobeHub / LobeChat

**Desktop app (easiest — supports stdio):** open LobeHub Desktop →
**Settings** → **Skill Settings** (on some versions: **Default Agent →
Plugin Settings**) → **Custom Skills / Custom Plugins** → **Quick Import JSON
Configuration**, paste:

```json
{
  "mcpServers": {
    "fiverr-niche-fetcher": {
      "type": "stdio",
      "command": "python",
      "args": ["C:\\full\\path\\to\\fiverr-niche-fetcher\\mcp_server.py"],
      "env": { "REQUEST_DELAY_SECONDS": "2.0" }
    }
  }
}
```

(use `/full/path/...` on macOS/Linux; best to point `command` at the venv
interpreter that has both requirements files installed).

**Self-hosted / web version (HTTP only):** start the server in HTTP mode,
then add a custom plugin of type streamable HTTP:

```bash
python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8765
```

```json
{
  "mcpServers": {
    "fiverr-niche-fetcher": {
      "type": "http",
      "url": "http://localhost:8765/mcp"
    }
  }
}
```

If LobeChat runs in Docker, `localhost` is the container — use
`host.docker.internal:8765` (Mac/Windows) or your host's LAN IP instead.

⚠️ **Timeout:** LobeHub's default MCP tool timeout is ~30 s. `fiverr_search`
with a small limit is fast, but `fiverr_crawl` can take minutes — raise
`MCP_TOOL_TIMEOUT` (e.g. `300000`) for self-hosted deployments or keep
crawl limits small.

**After installing:** enable the server for your agent (**Agent Settings →
Skills**) and toggle the individual tools you want it to use.

## Example response (trimmed)

```json
{
  "ok": true,
  "niche": "looker studio",
  "count": 2,
  "available_results": 567,
  "pages_scanned": 1,
  "results": [
    {
      "global_position": 1,
      "organic_position": 1,
      "is_sponsored": false,
      "card_title": "I will create a looker studio dashboard",
      "card_seller_name": "Alpha Seller",
      "card_rating": 5.0,
      "card_review_count": 120,
      "card_price": 50.0,
      "url": "https://www.fiverr.com/alpha/create-looker-dashboard"
    }
  ]
}
```

## Notes and limits

- **No API key is required** — the crawl path is keyless (the reader service is
  called without an account). OpenRouter keys are only for the optional
  Phase 3/4 AI features in the web app, which the MCP server does not call.
- MCP calls are capped at 100 search cards / 25 gigs per call by default
  (`MCP_SEARCH_LIMIT_MAX`, `MCP_CRAWL_LIMIT_MAX`) to respect client tool
  timeouts. Bigger jobs belong in the FastAPI web app, which streams progress,
  stores everything in SQLite, and exports JSON/CSV.
- Heavy fields (`raw_card_text`, `raw_visible_text`, JSON-LD, plain-text
  section copies) are stripped by default to keep agent context windows small;
  pass `include_raw=true` when debugging.
- If `fiverr_search` returns
  `Reader request failed after retries ... TLS connection`, the reader service
  or network path had a transient failure — retry. Persistent failures usually
  mean the host network blocks `r.jina.ai` or Fiverr's CDN.

## Testing

```bash
python -m unittest discover -s tests -p "test_mcp_server.py" -v
```

All network access is mocked; tests consume no tokens and never touch Fiverr.

## Boundaries (unchanged from the main app)

The MCP server does not: auto-publish to Fiverr, bypass login/CAPTCHA/access
controls, generate fake reviews, copy competitor descriptions, guarantee
rankings, or claim access to private analytics such as CTR/CR/Success Score.
Always review current Fiverr policies before acting on the data.
