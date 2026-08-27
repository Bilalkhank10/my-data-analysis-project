# Task: Build a Python MCP server that fetches public Fiverr market data

## Goal

Create `mcp_server.py` — a Model Context Protocol (MCP) server that lets any
MCP client (Claude Desktop, Cursor, LobeHub, etc.) research **public** Fiverr
marketplace data. It must (a) run the same "reader pipeline" architecture:
public Fiverr page URLs are fetched through the free reader proxy
`https://r.jina.ai/<url>`, which returns clean Markdown, and the Markdown is
parsed into structured records; (b) expose 5 tools; (c) be polite (delays,
retries, small concurrency) and (d) never bypass login, CAPTCHA, or private
analytics.

## Hard constraints

- Python 3.11+. Dependencies ONLY: `httpx`, `beautifulsoup4`, `mcp>=1.9,<2.0`
  (the stable FastMCP API; do NOT target mcp 2.x).
- No Playwright/Selenium/Chrome, no Fiverr login, no anti-bot circumvention,
  no Fiverr private APIs. Only public pages via the reader service.
- No API keys required for anything.
- `pip install` must work offline-from-repo; pin all deps.

## Tool surface (FastMCP, stdio default)

Server name: `fiverr-niche-fetcher`. Register these tools:

1. `fiverr_search(niche: str, limit: int = 10, include_raw: bool = False) -> dict`
   Ordered public search cards. For each card return: `url` (canonical
   `https://www.fiverr.com/<seller>/<slug>`), `global_position`,
   `organic_position`, `sponsored_position`, `is_sponsored`,
   `seller_online`, `card_title`, `card_seller_name`, `card_seller_username`,
   `card_seller_level`, `card_rating`, `card_review_count`, `card_price`,
   `currency`, `thumbnail_url`, `badges`, `page_number`, `page_position`.
   Response wrapper: `{ok, niche, count, available_results, pages_scanned,
   source, warnings, results}`.
2. `fiverr_gig(url: str, include_reviews: int = 10, include_raw: bool = False) -> dict`
   Full public gig page: title, seller (username/name/level/country,
   member since, avg response time, last delivery), rating + review_count,
   starting_price_usd, currency, hourly_rate_usd, category_path, about_text,
   `packages` (Basic/Standard/Premium: name, price, description, delivery,
   revisions, features), `faqs` (question/answer), `review_summary`
   (total, overall, star distribution, breakdown, with-files count),
   `visible_reviews` (username, country, rating, relative date, text, price
   range, duration, seller response), related_tags, media_urls, gallery_count,
   has_video. Wrapper: `{ok, url, gig}` (+`error` on failure).
3. `fiverr_crawl(niche: str, limit: int = 5, include_reviews: int = 5,
   include_raw: bool = False) -> dict` — discovery + every gig page; each
   result = gig record + its `search` rank metadata. Wrapper includes
   discovered/processed/success/failed counts and warnings.
4. `fiverr_listing_quality(url: str) -> dict` — deterministic completeness
   score (title-fit, description, 3 packages, FAQ depth, video, gallery,
   rating, tags). Must state it is NOT Fiverr's private Success Score.
5. `fiverr_field_limits() -> dict` — static, no network: title 80 chars
   (incl. "I will " prefix), description <=1200, 5 tags <=20 chars, FAQ
   q<=70/a<=300 chars max 10, package description <=100, packages Basic/
   Standard/Premium ordered, plus public rank-signal notes.

All tools return JSON dicts with an `ok` boolean; failures return
`{"ok": false, "error": "<public-safe message>"}` — never raise through MCP.

## Pipeline behavior (important details)

**Search discovery**: GET `https://r.jina.ai/https://www.fiverr.com/search/
gigs?query=<quote_plus(niche)>&source=top-bar&search_in=everywhere&page=N`
with headers `Accept: text/markdown`, `X-Return-Format: markdown`,
`User-Agent: Mozilla/5.0 (compatible; GigCraft/1.0)`. Paginate with a 0.75 s
delay until `limit` reached or 2 consecutive pages yield no new cards.
Parse cards from Markdown: gig links match
`https?://(?:www\.)?fiverr\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_-]+`; canonicalize
(discard query params; reject non-gig first paths: about_us, search, gigs,
login, pro, support, users, categories, ...; reject second segments
`portfolio|reviews|about`). Per-card segment: title from an "I will ..." link
label matching the card URL; seller name from the profile link to
`fiverr.com/<username>`; badges `Vetted Pro|Top Rated|Level 1|Level 2|
Fiverr's Choice|Pro`; rating from `**4.9**(123)`; price from `From $X` or
`Starting at $X`; sponsored if a standalone `Ad`/`Promoted` line exists;
`pos` query param = page_position; online from `seller_online=true` or an
`Online` line; total from `\d+ results`. Maintain separate running
organic/sponsored counters. Also extract `fiverr-res.cloudinary.com` URLs.

**Gig detail**: GET `https://r.jina.ai/<gig url>`; parse the returned
Markdown. Title from first `# ` heading (strip `by <name> | Fiverr` suffix);
seller via `Get to know <name>`, level/country/`Member since`/`Avg. response
time`/`Last delivery` regexes; rating/review count from `4.9 (169)` style
text; packages from the `## Compare packages` Markdown table (fallback:
single selected `### **Basic|Standard|Premium**` block); FAQs from a
`#{1,3} FAQ(s)` / `Frequently Asked Questions` section; reviews from the
`## N reviews for this Gig` section (star distribution `5 Stars(9)`,
breakdown lines, entries split on `^\*\s{2,}` with Cloudinary country-flag
images, `X days/weeks ago` dates, `$50-$100` price, `Price … Duration`,
`Seller's Response … Helpful?`; cap 50). Starting price = min(JSON-LD offer
prices, package prices). If a detail page lacks a field, fall back to the
search-card value.

**HTTP hardening**: custom TLS context with `OP_IGNORE_UNEXPECTED_EOF` when
available; retries (env `RETRY_COUNT`, default 3) with exponential backoff
honoring `Retry-After` on 429/5xx; treat TLS EOF/reset/timeout as retryable;
90 s reader timeout (env). On final failure return the structured error, do
not crash. Concurrency = env `MAX_CONCURRENCY` (default 2, max 5); delay
between requests = `REQUEST_DELAY_SECONDS` (default 2.0 s).

## MCP-specific behavior

- Default limits: search cap 100, crawl cap 25, max 50 visible reviews —
  all overridable via `MCP_SEARCH_LIMIT_MAX`, `MCP_CRAWL_LIMIT_MAX`,
  `MCP_MAX_VISIBLE_REVIEWS`. Larger jobs belong in the companion web app.
- Context-size trimming by default: drop `raw_card_text`,
  `raw_visible_text`, `json_ld`, and the `*_text` copies when structured
  fields exist; cap about_text at 4000 chars and media_urls at 10. Each raw
  field returns when `include_raw=true`.
- Validate: niche >= 2 chars; gig URLs must canonicalize via the rules above.
- CLI: `python mcp_server.py` (stdio), plus `--transport stdio|sse|
  streamable-http`, `--host 0.0.0.0`, `--port 8765` (env equivalents
  `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`); streamable-http serves `/mcp`.
- If `mcp` is not installed: exit with a clear "pip install -r
  requirements-mcp.txt" message (do not traceback).

## Deliverables

1. `mcp_server.py` (single file, plain functions for tool logic separate from
   MCP registration so tests can call them without the SDK).
2. `requirements.txt` + `requirements-mcp.txt` (`mcp>=1.9,<2.0`; note that
   mcp 2.x renamed FastMCP — do not use it).
3. `README.md` / `MCP_SERVER.md`: stdio + HTTP run instructions; client
   configs for Claude Desktop (`command/args/env` JSON), Cursor (`mcp.json`),
   and LobeHub (Desktop Quick-Import JSON for stdio; self-hosted needs
   `--transport streamable-http` with `http://host:8765/mcp`, plus the
   `host.docker.internal` Docker caveat and the ~30 s default MCP tool
   timeout warning for long crawls). Include tool reference and example
   trimmed JSON.
4. `tests/test_mcp_server.py` — stdlib `unittest`, fully mocked network
   (monkeypatch the HTTP layer with canned search-card and gig-page
   Markdown fixtures); assert: ranked/sponsored parsing, price/rating/badge
   extraction, packages/FAQs/reviews parsing incl. caps, URL validation
   rejecting non-gig URLs without network, crawl merging card+detail, error
   dicts instead of exceptions, tool registry contains exactly the 5 names.
5. Everything must run: `python -m unittest discover -s tests -v` green, and
   a stdio JSON-RPC smoke test (initialize -> tools/list -> tools/call
   fiverr_field_limits) must succeed.

## Boundaries to state in docs

No auto-publish, no login/CAPTCHA/access-control bypass, no fake reviews, no
verbatim copying of competitor text, no claims of Fiverr private metrics
(CTR/CR/Success Score). Public pages via the reader service only.

## Reference implementation

A working implementation of this exact spec lives in this repository:
`mcp_server.py` + `fiverr_fetcher.py` (the crawl/parse engine it reuses) +
`fiverr_metadata.py` (field limits / rank signals) +
`tests/test_mcp_server.py` + `MCP_SERVER.md`. Prefer reusing those modules
over re-implementing them if they are available.
