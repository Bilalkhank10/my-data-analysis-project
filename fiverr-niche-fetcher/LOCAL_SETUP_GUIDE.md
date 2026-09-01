# Complete Local PC Setup Guide

## Fiverr Gig Growth System — Phases 1–4

This guide covers Windows, macOS and Linux. The easiest Windows route is one file: **`START_HERE.bat`**.

---

## 1. What runs locally?

The following stay on your computer:

- FastAPI web application
- SQLite database
- crawl jobs and progress
- Phase 2 statistics
- Phase 3/4 run history and caches
- JSON, CSV and Markdown exports
- OpenRouter key loaded from your private environment

External network services:

- `r.jina.ai` reads public Fiverr pages
- `openrouter.ai` is contacted only when you explicitly run a real Phase 3/4 mode
- Dry runs make no OpenRouter request

The application never logs into Fiverr or auto-publishes a gig.

---

## 2. System requirements

### Required

- Windows 10/11, recent macOS, or modern Linux
- Python 3.11, 3.12 or 3.13
- Internet connection
- Modern browser: Chrome, Edge, Firefox or Safari
- Approximately 500 MB free space initially

Large 500-gig databases/exports can require more space over time.

### Not required

- Node.js
- ChromeDriver
- Playwright
- Docker
- GPU
- MySQL/PostgreSQL
- OpenRouter key for Phases 1–2 or dry runs

---

# Windows setup — one click

## Step 1: Extract the ZIP

Extract the complete project folder. Do not run files from inside the ZIP preview.

Example location:

```text
C:\Users\YourName\Documents\fiverr-niche-fetcher
```

Avoid protected folders such as `C:\Program Files`.

## Step 2: Start everything

Double-click:

```text
START_HERE.bat
```

It automatically:

1. Finds Python
2. Offers a Winget Python install if Python is missing
3. Creates `.venv`
4. Hash-checks `requirements.txt`
5. Installs or updates only when needed
6. Creates private `.env`
7. Runs `doctor.py`
8. Finds an available local port
9. Starts the server
10. Opens the browser

Keep the terminal window open while using the app. Press `Ctrl+C` to stop.

## First run duration

The first run can take a few minutes because Python dependencies are installed. Later runs normally skip dependency installation.

---

# Windows manual setup

Use this only if `START_HERE.bat` cannot run.

```bat
cd C:\path\to\fiverr-niche-fetcher
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe doctor.py --online
.venv\Scripts\python.exe start.py
```

Open the URL printed in the terminal, normally:

```text
http://127.0.0.1:8000
```

---

# macOS/Linux setup

```bash
cd /path/to/fiverr-niche-fetcher
chmod +x setup_unix.sh run.sh
./setup_unix.sh
./run.sh
```

Manual alternative:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python doctor.py --online
.venv/bin/python start.py
```

---

# 3. OpenRouter setup — optional

## Important

Any key pasted into chat should be revoked. Create a new key with a very small test spending limit.

Never place a real key in:

- chat messages
- source code
- screenshots
- Git repositories
- exported JSON/CSV/Markdown

## Configure locally

Open the `.env` file in Notepad and set:

```env
OPENROUTER_API_KEY=YOUR_NEW_ROTATED_KEY
OPENROUTER_MAX_COST_USD=0.10
OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731
OPENROUTER_EMBEDDING_MODEL=google/gemini-embedding-001
OPENROUTER_DEEP_MODEL=anthropic/claude-sonnet-5
```

Save `.env`, stop the terminal with `Ctrl+C`, then run `START_HERE.bat` again.

The app only shows `configured: true/false`; it never displays the key.

---

# 4. Recommended first workflow

## Phase 1 — Crawl

1. Open **Crawl**
2. Enter a niche, e.g. `Looker Studio`
3. Start with 3–10 gigs
4. Click **Start background job**
5. Wait for Completed

Move to 100–500 only after a small crawl succeeds. Large jobs can take a long time.

## Phase 2 — Intelligence

Open **Intelligence** to view:

- overview
- rankings
- rank movement
- keywords and clusters
- prices and packages
- competitors
- review intelligence
- market gaps

## Phase 3 — AI Audit

1. Open **AI Audit**
2. Run **Dry run — $0** first
3. Review estimated cost
4. If a new key is configured, run **Tiny live test**
5. Use Standard/Deep only when the test succeeds

## Phase 4 — Gig Builder

1. Open **Gig Builder**
2. Enter target buyer and positioning goal
3. Optionally paste your existing gig URL from the crawled result set
4. Run **Dry run — $0**
5. Review estimated cost
6. Run Tiny/Standard/Deep only with a secure key
7. Review compliance
8. Download Markdown
9. Approve only after human review

The app never publishes the draft automatically.

---

# 5. Local configuration

Main `.env` options:

```env
HOST=127.0.0.1
PORT=8000
AUTO_FIND_PORT=true
AUTO_OPEN_BROWSER=true

MAX_ACTIVE_JOBS=1
MAX_CONCURRENCY=2
REQUEST_DELAY_SECONDS=2.0
MAX_SEARCH_PAGES=30
SEARCH_PAGE_DELAY_SECONDS=0.75
RETRY_COUNT=3
RETRY_BASE_DELAY_SECONDS=1.0
READER_TIMEOUT_SECONDS=90

OPENROUTER_API_KEY=
OPENROUTER_MAX_COST_USD=0.10
OPENROUTER_MAX_GIGS=25
OPENROUTER_MAX_OUTPUT_TOKENS=2500
```

Restart the app after changing `.env`.

---

# 6. Data locations and backup

Database:

```text
data\fiverr_phase1.db
```

Exports:

```text
data\exports\
```

To back up your work:

1. Stop the server
2. Copy the entire `data` folder
3. Store it in a safe backup location

To reset all jobs/analytics, stop the server and delete the database plus its `-wal`/`-shm` companions. This permanently removes saved runs.

---

# 7. Diagnostics

Basic local checks:

```bat
.venv\Scripts\python.exe doctor.py
```

Network checks:

```bat
.venv\Scripts\python.exe doctor.py --online
```

Full test suite:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

# 8. Troubleshooting

## Python was not found

Install Python 3.11+ from:

```text
https://www.python.org/downloads/windows/
```

Enable **Add Python to PATH**, then run `START_HERE.bat` again.

## Virtual environment creation failed

Try:

```bat
py -3 -m ensurepip --upgrade
py -3 -m venv .venv
```

Delete a partially created `.venv` folder before retrying.

## ModuleNotFoundError

Run:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Or delete `.venv` and rerun `START_HERE.bat`.

## Port 8000 is busy

The launcher automatically tries nearby ports. Use the URL printed in the terminal.

To choose manually:

```env
PORT=8001
```

## Browser did not open

Open manually using the terminal URL, usually:

```text
http://127.0.0.1:8000
```

Set this if automatic opening is unwanted:

```env
AUTO_OPEN_BROWSER=false
```

## Fiverr/Jina error

- Check internet/firewall
- Run `doctor.py --online`
- Wait and retry later
- Keep concurrency low

Required public HTTPS destinations:

```text
r.jina.ai
fiverr.com
```

## OpenRouter says not configured

- Use a new rotated key
- Put it in `.env`
- Do not add quotes unless needed
- Restart the app
- Check `/api/ai/config` or the UI status

## OpenRouter 401

The key is invalid/revoked. Create a new key and restart.

## OpenRouter budget exceeded

Increase only if intentional:

```env
OPENROUTER_MAX_COST_USD=0.25
```

The key-level OpenRouter spending cap should remain the final safety limit.

## Model returned invalid JSON / structured mode error

The current release enables OpenRouter response healing and a tolerant local JSON parser. Update/re-extract the latest project files, then ensure `.env` contains:

```env
OPENROUTER_GIGS_PER_BATCH=1
OPENROUTER_MAX_OUTPUT_TOKENS=4000
```

Restart the app and try **Tiny live test** first. The one-gig batch avoids large truncated responses. If a request still says `truncated`, increase output tokens cautiously to `5000` while keeping the USD cost cap low.

## No endpoints found that can handle requested parameters

This means the selected model exists, but no currently routed provider endpoint supports every requested parameter combination. The latest release automatically tries:

```text
Strict JSON Schema
→ JSON Object mode
→ plain JSON with tolerant local parsing
→ primary Gemini fallback for Deep refinement/synthesis
```

Ensure:

```env
OPENROUTER_ALLOW_PARAMETER_FALLBACK=true
```

Then restart and run the failed job again. The successful Gemini draft is locally cached, so a repeated Deep run can usually reuse it and retry only refinement.

## Model unavailable

Model catalogs change. Update model IDs in `.env`, restart, and use Dry run first.

## Windows firewall prompt

Allow Python on **Private networks** only for local use. The default host `127.0.0.1` is local-only.

## Antivirus quarantines BAT files

Inspect the file contents—it only creates a virtual environment, installs `requirements.txt`, runs diagnostics, and starts `start.py`. You can use the manual Python commands instead.

---

# 9. Updating the project

1. Stop the server
2. Back up `data`
3. Replace code files with the updated release
4. Preserve `.env` and `data`
5. Run `START_HERE.bat`

The launcher detects a changed `requirements.txt` hash and updates dependencies.

---

# 10. Uninstall

1. Stop the server
2. Delete the extracted project folder

No Windows service, browser extension or system database is installed. Python itself remains installed unless you remove it separately.

---

# 11. Reliability notes

The application code is cross-platform and tested, but no software can guarantee zero errors on every PC. Main external variables are:

- Python installation
- firewall/proxy
- disk permissions
- port conflicts
- Jina/Fiverr page availability or markup changes
- OpenRouter model/provider availability

`START_HERE.bat`, `.venv`, `.env`, automatic port fallback, retries, SQLite WAL, caches, and `doctor.py` are included to reduce these risks.
