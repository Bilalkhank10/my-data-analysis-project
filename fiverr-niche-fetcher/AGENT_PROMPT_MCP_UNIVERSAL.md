# Universal Agent Prompt — Build a Fiverr public-data MCP server that works on EVERY AI chat platform

Copy everything below the line into any AI agent (ChatGPT, Claude, Gemini,
Cursor, Qwen, Kimi, Grok...). The agent will build a complete MCP server
whose output files run on **any** MCP-capable chat app.

---

# Task: Build a Python MCP server for public Fiverr market data, usable from ANY AI chat app

## Goal

Create a complete, working MCP (Model Context Protocol) server package that
lets ANY MCP-capable chat client research **public** Fiverr marketplace data.
"Working everywhere" is a hard requirement: the server must support **both**

1. **stdio transport** — for desktop/CLI apps that launch the server as a
   local process (Claude Desktop, Cursor, LobeHub Desktop, VS Code, Gemini
   CLI, Codex, Qwen Code, Cline, Roo Code...), and
2. **Streamable HTTP transport** — for web/self-hosted/remote apps that can
   only reach a URL (LobeHub Web/Docker, ChatGPT connectors, team servers).

The built files must be copy-paste usable: for every client, the README must
contain a ready-made config block that the user only needs to adjust paths in.

## Working principle ("reader pipeline")

Public Fiverr pages are fetched **through the free reader proxy**
`https://r.jina.ai/<url>`, which returns clean Markdown. The server parses
that Markdown into structured JSON. NO browser automation, NO login, NO
CAPTCHA bypass, NO private Fiverr analytics, NO API keys.

- Search URLs: `https://www.fiverr.com/search/gigs?query=<niche>&source=top-bar&search_in=everywhere&page=N` → wrapped as `https://r.jina.ai/<url>`.
- Gig URLs: `https://www.fiverr.com/<seller>/<gig-slug>` → wrapped the same way.

## Hard constraints

- Python 3.11+, deps only `httpx`, `beautifulsoup4`, `mcp>=1.9,<2.0`
  (pin below mcp 2.x — the FastMCP API was renamed there).
- Serve tools over BOTH transports selected by CLI flags:
  `python mcp_server.py` (stdio, default) and
  `python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8765`
  (HTTP endpoint `/mcp`). Env overrides: MCP_TRANSPORT, MCP_HOST, MCP_PORT.
- Politeness: 2 s delay between requests, 0.75 s between search pages,
  concurrency ≤ 2 (env-tunable REQUEST_DELAY_SECONDS, MAX_CONCURRENCY,
  SEARCH_PAGE_DELAY_SECONDS, RETRY_COUNT).
- Robustness: TLS context that tolerates abrupt CDN closes
  (OP_IGNORE_UNEXPECTED_EOF when available), retries with exponential
  backoff honoring Retry-After on 429/5xx, 90 s reader timeout (env).
- Every tool returns `{"ok": true, ...}` or `{"ok": false, "error": "..."}`
  — NEVER throw through MCP. Never print anything but JSON-RPC on stdout in
  stdio mode (logs to stderr).

## Tools (exact names, signatures, fields)

1. `fiverr_search(niche: str, limit: int = 10, include_raw: bool = False)`
   → ordered public search cards. Per card: url (canonical
   `https://www.fiverr.com/<seller>/<slug>`), niche, page_number,
   page_position (from `pos` query param), global_position,
   organic_position, sponsored_position, is_sponsored, seller_online,
   card_title, card_seller_name, card_seller_username, card_seller_level,
   card_rating, card_review_count, card_price, currency, thumbnail_url,
   badges, discovered_at. Wrapper: ok, niche, count, available_results
   (`\d+ results` total), pages_scanned, source, warnings, results.
2. `fiverr_gig(url: str, include_reviews: int = 10, include_raw: bool = False)`
   → one public gig page: title, seller_username/name/level/country,
   member_since, average_response_time, last_delivery, rating, review_count,
   starting_price_usd, currency, hourly_rate_usd, meta_description,
   category_path, about_text, packages (Basic/Standard/Premium: name, price,
   description, delivery_time, revisions, features), faqs (question/answer),
   review_summary (total, overall, star_distribution, rating_breakdown,
   with-files), visible_reviews (username, country, rating, relative_date,
   text, price range, duration, seller_response; cap 50), related_tags,
   media_urls, gallery_count, has_video. Reject non-gig URLs with ok=false
   before touching the network.
3. `fiverr_crawl(niche, limit=5, include_reviews=5, include_raw=False)`
   → discovery + all gig detail pages; each result = gig record + its
   `search` rank metadata, sorted by global_position; wrapper carries
   discovered/processed/success/failed counts and warnings.
4. `fiverr_listing_quality(url)` → deterministic listing completeness score
   (title fits 59-char card window, description ≥300 chars, 3 packages,
   ≥5 FAQs, has video, ≥3 gallery images, has rating, ≥3 tags). MUST state
   it is not Fiverr's private Success Score.
5. `fiverr_field_limits()` → static, no network: Fiverr form limits
   (title 80 incl. "I will " prefix; description 1200; 5 tags × 20 chars;
   FAQ 70/300 chars; package description 100; ...) + public rank signals.

## Parsing details (do not skip)

- Gig link regex: `https?://(?:www\.)?fiverr\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_-]+`;
  canonicalize and reject non-gig first segments (search, gigs, categories,
  users, login, pro, support, about_us, ...) and second segments
  `portfolio|reviews|about`.
- Search cards: slice markdown between consecutive gig links; title = "I
  will ..." link label whose href equals the canonical URL (fallback: image
  alt); seller name = label of the profile link `fiverr.com/<username>`;
  badges: Vetted Pro / Top Rated / Level 1 / Level 2 / Fiverr's Choice / Pro
  (level = first Level/Top Rated/Vetted Pro badge); rating `**4.9**(120)`;
  price `(From|Starting at) $X`; sponsored = standalone `Ad` or `Promoted`
  line; online = `seller_online=true` in URL or standalone `Online` line;
  thumbnails = fiverr-res.cloudinary.com URLs; keep separate running
  organic vs sponsored position counters; dedupe across pages.
- Gig page: title from first `# ...` heading or `Title:` line (strip
  " by Name | Fiverr"); seller stats via regexes (`Get to know X`, `XFrom Y`,
  `Member since X`, `Avg. response time X`, `Last delivery X`); packages
  from the `## Compare packages` markdown table (fallback single `###
  **Basic|Standard|Premium**` block); FAQs from `## FAQ(s)` / `Frequently
  Asked Questions` (### subheadings, or bold-question, or Q&A paragraph
  strategies); reviews from `## N reviews for this Gig` (overall, star
  distribution `5 Stars(9)`, breakdown bullets, entries split on
  `^\*\s{2,}` with Cloudinary flag images for country codes,
  `N days/weeks/... ago` dates, `$50-$100` price, `Price X Duration`,
  `Seller's Response ... Helpful?`); JSON-LD aggregateRating/offers when
  present; starting price = min of all offer/package prices.
- Search-card values are FALLBACKS for missing detail fields.

## MCP layer behavior

- Cap per call (env-tunable): search ≤ 100, crawl ≤ 25, ≤ 50 visible
  reviews; document that big jobs belong in a queue-based web app.
- Default-output trimming to keep chat context small: drop raw_card_text,
  raw_visible_text, json_ld, plain-text section copies; cap about_text at
  4000 chars, media_urls at 10. `include_raw=true` returns everything.
- Validate niche (≥2 chars) BEFORE network calls.
- If the `mcp` package is missing, exit with a clear hint:
  `pip install -r requirements-mcp.txt`.

## Deliverables (all required)

1. `mcp_server.py` — single file; keep tool logic in plain async functions
   separately from MCP registration so tests don't need the SDK.
2. `requirements.txt` and `requirements-mcp.txt` (`mcp>=1.9,<2.0`).
3. `tests/test_mcp_server.py` — stdlib unittest ONLY, fully mocked
   network (patch the GET function with canned search + gig markdown
   fixtures; zero real requests): ranked/sponsored parsing, price/rating/
   badge extraction, packages/FAQs/reviews parsing with caps, URL
   validation without network, crawl card+detail merge with fallbacks,
   error dicts on failure, tool registry contains exactly the 5 names.
4. `README.md` with a "**Works on every AI platform**" section containing a
   ready-made config block for EACH of these, adjusted only for paths:
   - Claude Desktop / Claude Code (stdio JSON, command+args+env)
   - Cursor (`mcp.json` with `servers`)
   - LobeHub Desktop (Quick Import JSON Configuration — stdio)
   - LobeHub Web/Docker (`"type": "http"` URL config; note Docker must use
     `host.docker.internal` or the LAN IP, and that the default ~30 s MCP
     tool timeout should be raised for `fiverr_crawl`, e.g.
     MCP_TOOL_TIMEOUT=300000)
   - ChatGPT connectors / any HTTP-only client: run
     `--transport streamable-http --host 0.0.0.0 --port 8765`, URL
     `http://<host>:8765/mcp`; mention ngrok/cloudflared for exposing it
   - Gemini CLI (`.gemini/settings.json`) and Codex (`config.toml`
     `[mcp_servers.*]`), VS Code (`.vscode/mcp.json`)
   It must explain: install (`pip install -r requirements.txt
   -r requirements-mcp.txt`), run both transports, curl smoke test for HTTP
   mode, and the "enable the plugin in the agent's tools/settings" step
   each client needs after adding the config.
5. Example trimmed JSON responses for `fiverr_search` and `fiverr_gig`.

## Acceptance criteria

- `python -m unittest discover -s tests -v` → all green, no network.
- stdio JSON-RPC smoke test: initialize → notifications/initialized →
  `tools/list` returns the 5 tools → `tools/call fiverr_field_limits`
  returns ok=true.
- HTTP mode: POST to `/mcp` with an initialize body returns serverInfo.
- Same config block formats as listed above, with no platform left out.

## Boundaries (state them in docs)

Public pages via the reader service only. No login/CAPTCHA/access-control
bypass, no fake reviews, no scraping of private analytics (CTR/CR/Success
Score), no auto-publish, no verbatim copying of competitor text.

## Reference implementation (optional shortcut)

If you have access to the repo `fiverr-niche-fetcher/`, reuse
`fiverr_fetcher.py` (crawl/parse engine) and `fiverr_metadata.py` (field
limits) and model `mcp_server.py` on them instead of re-inventing parsers.
