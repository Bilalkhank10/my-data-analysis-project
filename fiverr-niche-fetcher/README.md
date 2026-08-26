# Fiverr Gig Growth System — Phase 4

For normal users, start with **`SIMPLE_USER_GUIDE.md`**. For complete technical operation, read **`COMPLETE_USER_TUTORIAL.md`**. For installation and troubleshooting, read **`LOCAL_SETUP_GUIDE.md`**.

Local research-to-action system with four layers:

1. **Phase 1:** public crawl, rank positions and SQLite snapshots
2. **Phase 2:** deterministic market intelligence — no LLM
3. **Phase 3:** optional OpenRouter semantic audits
4. **Phase 4:** evidence-led, human-approved Fiverr gig drafts

## Critical security rule

Never paste API keys into chat or source code. If a key has been pasted into chat, revoke it and create a new limited-credit key.

The application reads `OPENROUTER_API_KEY` only from the process environment. It never returns or stores the key in UI, JavaScript, SQLite, logs, JSON, CSV or Markdown exports.

## Phase 4 outputs

- three positioning options
- recommended gig title
- exactly five tags
- category, subcategory and service type
- complete description
- Basic/Standard/Premium packages
- price, delivery, revisions, ideal buyer, deliverables and features
- FAQs
- buyer requirements
- scope exclusions
- CTA
- thumbnail headline/subheadline
- three gallery-image briefs
- five-part video script
- evidence basis
- model self-check
- deterministic compliance validation
- existing-vs-proposed comparison
- Markdown download
- draft approval state

Generated assets are never auto-published. Human approval is required.

## Evidence pipeline

Phase 4 compacts and uses:

- Phase 2 top keywords and clusters
- market price percentiles
- package/feature patterns
- buyer review language
- transparent market gaps
- optional target/current gig
- optional completed Phase 3 semantic audit

Competitor text is context only; prompts explicitly prohibit verbatim copying.

## Modes

### Dry run — default

- zero API requests
- zero tokens
- zero cost
- context and target availability check
- projected token/cost estimate
- planned outputs

### Tiny live draft

- one constrained Gemini generation call
- intended for minimum-cost connection/schema validation

### Standard draft

- one Gemini structured generation call
- deterministic compliance validation

### Deep refine

- Gemini draft
- deterministic validator
- Claude Sonnet 5 refinement using validation issues
- final deterministic validator

## Default models

```text
Draft:      google/gemini-3.7-flash
Embedding:  google/gemini-embedding-001  (Phase 3)
Refinement: anthropic/claude-sonnet-5
```

## Deterministic compliance checks

- title presence and 15–80-character target
- 300–1200-character description target
- exactly five unique tags
- exactly three ordered packages
- ascending Basic/Standard/Premium prices
- minimum FAQ depth
- off-platform contact/payment patterns
- unverifiable guarantees
- keyword stuffing
- thumbnail headline readability

These checks assist human review; they are not a substitute for Fiverr’s current policies.

## Setup

Python 3.11+ required. No Node.js, Chrome, Playwright, Docker or GPU is required.

### Windows — one click

1. Extract the ZIP.
2. Double-click **`START_HERE.bat`**.

It finds/installs Python when possible, creates `.venv`, hash-checks and installs requirements, creates `.env`, runs diagnostics, chooses a free port, starts the server, and opens the browser. Later, use the same file again.

`setup_windows.bat` and `run.bat` remain available as separate alternatives.

### macOS/Linux

```bash
cd fiverr-niche-fetcher
chmod +x setup_unix.sh run.sh
./setup_unix.sh
./run.sh
```

### Manual diagnostics

```bash
python doctor.py
python doctor.py --online
python -m unittest discover -s tests -v
```

`doctor.py` checks Python, packages, SQLite, write access, port availability and key configuration without printing the key. Online checks are optional.

### OpenRouter key

Edit the local `.env` file and add a **new rotated** key only when real Phase 3/4 runs are needed:

```env
OPENROUTER_API_KEY=YOUR_NEW_ROTATED_KEY
OPENROUTER_MAX_COST_USD=0.10
```

Restart `run.bat`/`run.sh` after editing `.env`. Without a key, Phases 1–2 and Phase 3/4 dry runs still work.

## Environment variables

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-3.7-flash
OPENROUTER_EMBEDDING_MODEL=google/gemini-embedding-001
OPENROUTER_DEEP_MODEL=anthropic/claude-sonnet-5
OPENROUTER_MAX_COST_USD=2.00
OPENROUTER_MAX_GIGS=25
OPENROUTER_GIGS_PER_BATCH=1
OPENROUTER_MAX_OUTPUT_TOKENS=4000
OPENROUTER_TIMEOUT_SECONDS=120
```

For the first real smoke test, set a newly generated key limit and local run cap around `$0.10`, then choose **Tiny live draft**.

## Phase 4 API

### Configuration — key never returned

```http
GET /api/generation/config
```

### Start generation

```http
POST /api/jobs/{job_id}/generation-runs
Content-Type: application/json

{
  "mode": "dry_run",
  "target_gig_url": null,
  "target_buyer": "ecommerce marketing teams",
  "positioning_goal": "premium GA4 reporting specialist",
  "tone": "professional",
  "output_language": "English",
  "pricing_preference": "market_aligned"
}
```

Modes: `dry_run`, `test`, `standard`, `deep`.

### Status

```http
GET /api/generation-runs/{run_id}
```

### Result

```http
GET /api/generation-runs/{run_id}/result
```

### Markdown export

```http
GET /api/generation-runs/{run_id}/export.md
```

### Human approval state

```http
POST /api/generation-runs/{run_id}/approval
Content-Type: application/json

{"status":"approved"}
```

A dry-run plan cannot be approved.

### History

```http
GET /api/jobs/{job_id}/generation-runs
```

## SQLite additions

- `generation_runs` — status, models, preferences, usage, cost, result and approval state
- existing `ai_cache` — generation prompt/result cache

## Testing

```bash
python -m unittest discover -s tests -v
```

All OpenRouter calls in development tests are mocked. Dry-run integration tests use real stored Fiverr data but consume no tokens.

## Structured JSON reliability

OpenRouter requests enable the `response-healing` plugin. The local parser also handles JSON code fences, mixed prose, content-part arrays, double-encoded JSON and trailing commas. Phase 3 defaults to one gig per model request to reduce output truncation.

If an older `.env` still has previous settings, use:

```env
OPENROUTER_GIGS_PER_BATCH=1
OPENROUTER_MAX_OUTPUT_TOKENS=4000
```

Restart the server after editing `.env`.

If OpenRouter reports `No endpoints found that can handle the requested parameters`, the client now retries automatically with: strict JSON Schema → JSON Object mode → compatible plain JSON parsing. Deep mode also falls back from the requested premium model to the primary Gemini model instead of failing the whole run.

```env
OPENROUTER_ALLOW_PARAMETER_FALLBACK=true
```

## Boundaries

The system does not:

- auto-publish to Fiverr
- bypass login/CAPTCHA/access controls
- generate or encourage fake reviews
- copy competitor descriptions verbatim
- guarantee rankings or orders
- claim access to private feedback, CTR/CR, Success Score internals or secret algorithm weights

Always review current Fiverr policies before publishing a draft.
