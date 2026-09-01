# GigCraft

**Premium local studio for Fiverr market research, keyword & health analytics, and copy-ready AI gig drafts.**

You type a niche (e.g. `looker studio dashboard`), GigCraft crawls the public Fiverr market for that niche, computes real market intelligence from the crawled sample, and — optionally with Google Gemini — drafts a complete, compliance-checked Fiverr gig (title, 5 tags, description, 3 packages, FAQs, thumbnail + video script) for you to review and publish manually.

```
fiverr-niche-fetcher/   Python FastAPI app (4-phase "Gig Growth System", SQLite, OpenRouter AI)
fiverr-mcp/             Standalone MCP server (Claude Desktop / LobeHub / Cursor tools)
<root>                  GigCraft v6 — TypeScript + Express web app (this README)
```

---

## 1. The TypeScript app (root)

### Stack
TypeScript · Express 5 · `@google/genai` (Gemini) · `node:sqlite` (persistence) · run with `tsx`, bundle with esbuild.

### Quick start

```bash
npm install
cp .env.example .env        # then optionally set GEMINI_API_KEY / JINA_API_KEY (a key is already in .env)
npm run dev                 # http://localhost:3000
```

> **Access model:** the login system has been **removed** — the studio is open
> because it is a local tool. The API is still rate-limited, every response
> carries security headers, and downloads are filename-whitelisted. Keep the
> server on localhost/LAN (it serves exported gig data).

Production:

```bash
npm run build && npm start
```

### What it does

| Workspace | Endpoint | What happens |
|---|---|---|
| **Studio** (`/`) | `POST /api/simple-workflows` | One-click: crawl → analyze → AI gig draft → Markdown export |
| **Lab** (`/advanced`) | `POST /api/jobs` / `POST /api/fetch` | Full crawl with progress, 15+ analysis sections, per-section CSV export |
| **Semantic audit** | `POST /api/jobs/:id/ai-runs` | Real Gemini audit (batched) or labelled deterministic fallback |
| **Gig builder** | `POST /api/jobs/:id/generation-runs` | Evidence-based gig draft + deterministic compliance checks + approval + `.md` export |

### Live crawling

Crawling goes through the **public Jina Reader proxy** (`r.jina.ai`) — no Fiverr account, no CAPTCHA.

- **Recommended:** set a **free** `JINA_API_KEY` — keyless is limited to ~20 RPM; a free key gives ~500 RPM + 10M free tokens.
- Live pages are cached in SQLite (`CRAWL_CACHE_TTL_SECONDS`, default 6h) so re-crawls don't burn quota.
- When live data is unavailable (offline/blocked), the app falls back to an **explicitly-labelled illustrative sample** — never silent fabrication.

### Data honesty

- Rankings, prices, keywords, clusters (union-find + Jaccard), sentiment, package/feature coverage, market gaps and rank-movement are **computed from the crawled sample**.
- Without `GEMINI_API_KEY`, AI features run a **clearly-labelled deterministic** mode: `llm_used: false`, `total_tokens: 0`, `actual_cost_usd: 0`.
- With `GEMINI_API_KEY`, token counts come from the API's `usageMetadata`; cost is a list-price **estimate** labelled as such.
- `dry_run` modes make **zero** API calls and only report honest projections.

### Persistence

Jobs, results, analyses, AI runs, drafts, rank snapshots and the reader cache persist in `data/gigcraft.db` (SQLite, WAL). A restart does **not** lose finished work. Finished jobs are capped at `MAX_JOBS` (default 50).

### Security model

- **Open local tool** — the password/login system was removed on request; the app is meant to run bound to localhost (no public exposure; it serves exported gig data).
- **Rate limiting:** general per-IP limit on `/api` (hammering guard).
- **Security headers** on every response (CSP, `X-Frame-Options: DENY`, nosniff, referrer policy).
- **Downloads** are filename-whitelisted with strict directory containment (no path traversal, no query-string secrets).
- CSV exports are sanitized against spreadsheet formula injection.

### Development

```bash
npm test          # Node test runner: parser, analyzer, AI engine, security, persistence
npm run lint      # tsc --noEmit (strict mode)
npm run build     # esbuild bundle -> dist/server.cjs
```

---

## 2. `fiverr-niche-fetcher/` (Python app)

The 4-phase Gig Growth System (crawl → deterministic intelligence → OpenRouter semantic audits → human-approved gig drafts) with **SQLite snapshots**, cost-capped OpenRouter usage, embeddings + cosine similarity, and deterministic compliance validation.

```bash
cd fiverr-niche-fetcher
python3 -m venv .venv && . .venv/bin/activate     # (Windows: START_HERE.bat one-click)
pip install -r requirements.txt
cp ../.env.example .env                            # set APP_PASSWORD, optionally OPENROUTER_API_KEY
python start.py                                    # auto port + browser, http://127.0.0.1:8000
python -m pytest tests/ -q                         # 50+ tests
```

The web app is an **open local tool** (login system removed on request) with filename-whitelisted downloads — keep it on localhost.

## 3. `fiverr-mcp/` (MCP server)

Exposes the crawler as three MCP tools (`search_fiverr_gigs`, `fetch_gig_details`, `crawl_fiverr_niche`) for Claude Desktop, LobeHub, Cursor and other MCP clients. See `fiverr-mcp/README.md` for ready-to-paste configs.

> `fiverr-mcp/app.py` is a thin compatibility shim — the full web app lives in `fiverr-niche-fetcher/`.

## Repository layout & housekeeping

- Release zip archives and reference PDFs (`uploads/`) are **not** version controlled (see `.gitignore`); keep them on disk or attach them to GitHub Releases.
- The crawler (`fiverr_fetcher.py`) exists in two standalone distributions and must stay **identical**: run `python scripts/sync_fiverr_fetcher.py` after edits (CI fails if the copies drift).
- CI (`.github/workflows/ci.yml`): TypeScript typecheck + tests + build, Python tests, fetcher-sync check.

## Audit history

See `AUDIT_REPORT.md` (2026-08-31) for the original comprehensive security/quality audit, and the commit history for the follow-up hardening pass (real analyzer data, real AI usage, auth for both apps, persistence, signed downloads, rate limiting, strict typing).
