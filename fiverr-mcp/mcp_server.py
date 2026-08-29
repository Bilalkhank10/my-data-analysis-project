"""
Fiverr Niche Fetcher - MCP Server
==================================
Exposes the full Fiverr data-fetch pipeline as MCP (Model Context Protocol) tools
over the stdio transport (JSON-RPC 2.0 newline-delimited).

Three tools:
  1. search_fiverr_gigs  -- Search Fiverr and return ranked gig cards
  2. fetch_gig_details   -- Fetch a single gig detail page
  3. crawl_fiverr_niche  -- Full pipeline: search + fetch all detail pages

Usage (stdio):
  python mcp_server.py

Registration (mcp_config.json):
  See mcp_config.json in this directory.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
import threading
from typing import Any

# ---------------------------------------------------------------------------
# Add this file's directory to sys.path so fiverr_fetcher can be imported
# from any working directory.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from fiverr_fetcher import (
    FetcherError,
    FetcherSettings,
    FiverrNicheFetcher,
    GigRecord,
    normalize_gig_url,
)
import httpx

# ---------------------------------------------------------------------------
# MCP Protocol Constants
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "fiverr-niche-fetcher"
SERVER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Tool Definitions (sent in response to tools/list)
# ---------------------------------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_fiverr_gigs",
        "description": (
            "Search Fiverr for gigs matching a niche keyword and return ranked search-card "
            "metadata: title, seller name/level, rating, review count, starting price, "
            "thumbnail URL, sponsored/organic rank position, and badges (Top Rated, Level 1/2, etc.). "
            "Data is fetched via the public Jina Reader proxy - no Fiverr account required."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "niche": {
                    "type": "string",
                    "description": "Search keyword or niche, e.g. 'logo design' or 'python web scraping'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum gig cards to return (1-500). Default: 20.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 500,
                },
                "max_search_pages": {
                    "type": "integer",
                    "description": "Maximum Fiverr search pages to scan (1-30). Default: 5.",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 30,
                },
            },
            "required": ["niche"],
        },
    },
    {
        "name": "fetch_gig_details",
        "description": (
            "Fetch and parse a single Fiverr gig detail page. Returns comprehensive gig data: "
            "title, seller info (name, level, country, member since, response time), "
            "rating and review count, pricing packages (Basic/Standard/Premium), FAQs, "
            "visible reviews with text, related tags, media/gallery URLs, and JSON-LD metadata. "
            "Data is fetched via the public Jina Reader proxy - no Fiverr account required."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full Fiverr gig URL, e.g. 'https://www.fiverr.com/seller/gig-title'.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "crawl_fiverr_niche",
        "description": (
            "Run the complete two-stage Fiverr crawl pipeline for a niche: "
            "Stage 1 - search Fiverr and collect ranked gig URLs; "
            "Stage 2 - fetch full detail pages for every discovered gig concurrently. "
            "Returns merged results containing both search-card metadata and full gig details, "
            "plus crawl statistics (pages scanned, success/failure counts, timing). "
            "Rate-limited and polite by default. No Fiverr account required."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "niche": {
                    "type": "string",
                    "description": "Search keyword or niche.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum gigs to crawl end-to-end (1-50). Default: 10.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "max_concurrency": {
                    "type": "integer",
                    "description": "Parallel gig-detail fetch workers (1-5). Default: 2.",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 5,
                },
                "delay_seconds": {
                    "type": "number",
                    "description": "Seconds between individual gig fetches (0.5-10). Default: 2.0.",
                    "default": 2.0,
                    "minimum": 0.5,
                    "maximum": 10.0,
                },
            },
            "required": ["niche"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------

async def _tool_search_fiverr_gigs(args: dict[str, Any]) -> Any:
    niche: str = str(args.get("niche", "")).strip()
    if not niche:
        raise ValueError("'niche' is required and must not be empty.")
    limit: int = int(args.get("limit", 20))
    max_pages: int = int(args.get("max_search_pages", 5))

    settings = FetcherSettings()
    settings.max_search_pages = max(1, min(30, max_pages))
    fetcher = FiverrNicheFetcher(settings)
    outcome = await fetcher.discover_search(niche, limit)

    return {
        "niche": niche,
        "pages_scanned": outcome.pages_scanned,
        "available_results": outcome.available_results,
        "returned_count": len(outcome.records),
        "warnings": outcome.warnings,
        "records": [r.to_dict() for r in outcome.records],
    }


async def _tool_fetch_gig_details(args: dict[str, Any]) -> Any:
    url: str = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("'url' is required.")
    canonical = normalize_gig_url(url)
    if not canonical:
        raise ValueError(f"'{url}' does not look like a valid Fiverr gig URL (expected fiverr.com/<user>/<slug>).")

    settings = FetcherSettings()
    fetcher = FiverrNicheFetcher(settings)
    async with httpx.AsyncClient(**fetcher._client_kwargs()) as client:
        gig: GigRecord = await fetcher._fetch_gig(client, canonical)
    return gig.to_dict()


async def _tool_crawl_fiverr_niche(args: dict[str, Any]) -> Any:
    niche: str = str(args.get("niche", "")).strip()
    if not niche:
        raise ValueError("'niche' is required and must not be empty.")
    limit: int = int(args.get("limit", 10))
    max_concurrency: int = int(args.get("max_concurrency", 2))
    delay_seconds: float = float(args.get("delay_seconds", 2.0))

    settings = FetcherSettings()
    settings.max_concurrency = max(1, min(5, max_concurrency))
    settings.delay_seconds = max(0.5, min(10.0, delay_seconds))
    fetcher = FiverrNicheFetcher(settings)
    return await fetcher.crawl(niche, limit=limit, collect_results=True)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------
TOOL_HANDLERS: dict[str, Any] = {
    "search_fiverr_gigs": _tool_search_fiverr_gigs,
    "fetch_gig_details": _tool_fetch_gig_details,
    "crawl_fiverr_niche": _tool_crawl_fiverr_niche,
}


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


_write_lock = threading.Lock()


def _send(obj: dict[str, Any]) -> None:
    """Thread-safe write of one JSON-RPC line to stdout."""
    line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
    with _write_lock:
        sys.stdout.buffer.write(line.encode("utf-8"))
        sys.stdout.buffer.flush()


# ---------------------------------------------------------------------------
# Request dispatch
# ---------------------------------------------------------------------------

async def _dispatch(msg: dict[str, Any]) -> None:
    req_id = msg.get("id")
    method: str = msg.get("method", "")
    params: dict = msg.get("params") or {}

    # Notifications have no id -- silently ignore
    if req_id is None and method not in ("initialize", "initialized"):
        return

    if method == "initialize":
        _send(_ok(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }))

    elif method == "initialized":
        pass  # notification, no response needed

    elif method == "tools/list":
        _send(_ok(req_id, {"tools": TOOLS}))

    elif method == "tools/call":
        tool_name: str = params.get("name", "")
        args: dict[str, Any] = params.get("arguments", {}) or {}
        handler = TOOL_HANDLERS.get(tool_name)

        if handler is None:
            _send(_err(req_id, -32601, f"Unknown tool: '{tool_name}'"))
            return

        try:
            result = await handler(args)
            _send(_ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str, indent=2)}],
                "isError": False,
            }))
        except (ValueError, FetcherError) as exc:
            _send(_ok(req_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }))
        except Exception as exc:
            _send(_ok(req_id, {
                "content": [{"type": "text", "text": f"Internal error: {exc}\n{traceback.format_exc()}"}],
                "isError": True,
            }))

    elif method == "ping":
        _send(_ok(req_id, {}))

    else:
        _send(_err(req_id, -32601, f"Method not found: '{method}'"))


# ---------------------------------------------------------------------------
# Main: blocking stdin reader + asyncio event loop
# ---------------------------------------------------------------------------

async def _run_server() -> None:
    """Read newline-delimited JSON from stdin and dispatch each message."""
    stdin_bin = sys.stdin.buffer
    loop = asyncio.get_event_loop()

    while True:
        # Read one line in a thread so we do not block the event loop.
        raw: bytes = await loop.run_in_executor(None, stdin_bin.readline)
        if not raw:
            break  # EOF

        raw_str = raw.decode("utf-8", errors="replace").strip()
        if not raw_str:
            continue

        try:
            msg = json.loads(raw_str)
        except json.JSONDecodeError as exc:
            _send(_err(None, -32700, f"Parse error: {exc}"))
            continue

        # Dispatch without awaiting so we can keep reading in parallel
        # (important for streaming clients that pipeline requests).
        asyncio.ensure_future(_dispatch(msg))


def main() -> None:
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
