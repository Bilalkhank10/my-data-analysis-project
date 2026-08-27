"""Model Context Protocol (MCP) server for the public Fiverr crawl pipeline.

Exposes the exact fetching logic used by the web app
(:class:`fiverr_fetcher.FiverrNicheFetcher`) as MCP tools, so any MCP-capable
agent (Claude Desktop, Cursor, VS Code, etc.) can research public Fiverr
niches:

========================= ===================================================
Tool                      Purpose
========================= ===================================================
``fiverr_search``         Ordered public search cards (rank, price, rating,
                          sponsored/organic status, seller badges).
``fiverr_gig``            Full public gig page (packages, FAQs, reviews,
                          related tags, media, seller stats).
``fiverr_crawl``          Search discovery + gig detail pages for a whole
                          niche in one call (the same pipeline the web UI runs).
``fiverr_listing_quality`` Deterministic listing-completeness score for one
                          gig (not Fiverr's private Success Score).
``fiverr_field_limits``   Static Fiverr form limits and public rank signals.
========================= ===================================================

The boundaries are identical to the rest of the project: only **public**
Fiverr pages are read, via the r.jina.ai reader service. There is no login,
CAPTCHA bypass, private analytics, or access-control circumvention.

Run over stdio (default — for desktop MCP clients)::

    python mcp_server.py

...or over HTTP (for remote clients and sandboxed previews)::

    python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8765

Requires ``pip install -r requirements-mcp.txt`` on top of the regular
project requirements. Tuning env vars are the same as the crawler's
(``REQUEST_DELAY_SECONDS``, ``MAX_CONCURRENCY``, ``MAX_SEARCH_PAGES``,
``RETRY_COUNT``, ``READER_TIMEOUT_SECONDS`` ...) plus MCP-specific caps:
``MCP_SEARCH_LIMIT_MAX`` (default 100), ``MCP_CRAWL_LIMIT_MAX`` (default 25)
and ``MCP_MAX_VISIBLE_REVIEWS`` (default 50).
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import httpx

from fiverr_fetcher import (
    FetcherError,
    FiverrNicheFetcher,
    normalize_gig_url,
)
from fiverr_metadata import FIELD_LIMITS, PUBLIC_RANK_SIGNALS, listing_quality

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only without the mcp extra
    FastMCP = None  # type: ignore[assignment]

# MCP calls share one client conversation, so per-call work is capped far below
# the web app's 500-gig jobs to respect client-side tool timeouts. Large jobs
# belong in the FastAPI app, which stores everything in SQLite.
SEARCH_LIMIT_CAP = max(1, min(500, int(os.getenv("MCP_SEARCH_LIMIT_MAX", "100"))))
CRAWL_LIMIT_CAP = max(1, min(500, int(os.getenv("MCP_CRAWL_LIMIT_MAX", "25"))))
REVIEW_CAP = max(0, min(50, int(os.getenv("MCP_MAX_VISIBLE_REVIEWS", "50"))))
ABOUT_TEXT_CAP = max(200, int(os.getenv("MCP_ABOUT_TEXT_CAP", "4000")))
MEDIA_URL_CAP = 10

# Structured fields (packages/faqs/review_summary) already carry this content;
# the plain-text copies and raw page dumps only bloat agent context windows.
GIG_HEAVY_FIELDS = (
    "raw_visible_text",
    "json_ld",
    "packages_text",
    "faq_text",
    "reviews_text",
)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _public_error(exc: BaseException) -> str:
    if isinstance(exc, FetcherError):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def _make_fetcher() -> FiverrNicheFetcher:
    return FiverrNicheFetcher()


def trim_search_record(
    record: dict[str, Any], *, include_raw: bool = False
) -> dict[str, Any]:
    """Drop the raw card markdown unless explicitly requested."""
    if include_raw:
        return dict(record)
    return {key: value for key, value in record.items() if key != "raw_card_text"}


def trim_gig_record(
    gig: dict[str, Any], *, include_reviews: int = 10, include_raw: bool = False
) -> dict[str, Any]:
    """Keep the agent-useful parts of a gig record and cap the heavy ones."""
    if include_raw:
        return dict(gig)
    trimmed = {key: value for key, value in gig.items() if key not in GIG_HEAVY_FIELDS}
    about = trimmed.get("about_text")
    if isinstance(about, str) and len(about) > ABOUT_TEXT_CAP:
        trimmed["about_text"] = about[:ABOUT_TEXT_CAP].rstrip() + " … [truncated]"
    media = trimmed.get("media_urls")
    if isinstance(media, list) and len(media) > MEDIA_URL_CAP:
        trimmed["media_urls"] = media[:MEDIA_URL_CAP]
    reviews = trimmed.get("visible_reviews")
    if isinstance(reviews, list):
        keep = _clamp(include_reviews, 0, REVIEW_CAP)
        trimmed["visible_reviews"] = reviews[:keep]
    return trimmed


def _clean_niche(niche: str) -> tuple[str | None, dict[str, Any] | None]:
    value = " ".join(str(niche or "").split()).strip()
    if len(value) < 2:
        return None, {
            "ok": False,
            "error": "niche must be at least 2 characters long",
            "niche": value,
        }
    return value, None


async def _fiverr_search(
    niche: str, limit: int = 10, include_raw: bool = False
) -> dict[str, Any]:
    niche, invalid = _clean_niche(niche)
    if invalid is not None:
        return invalid
    limit = _clamp(limit, 1, SEARCH_LIMIT_CAP)
    try:
        fetcher = _make_fetcher()
        outcome = await fetcher.discover_search(niche, limit)
    except Exception as exc:  # FetcherError and transport failures alike
        return {"ok": False, "niche": niche, "error": _public_error(exc)}
    records = [
        trim_search_record(record.to_dict(), include_raw=include_raw)
        for record in outcome.records
    ]
    return {
        "ok": True,
        "niche": niche,
        "count": len(records),
        "available_results": outcome.available_results,
        "pages_scanned": outcome.pages_scanned,
        "source": outcome.source,
        "warnings": outcome.warnings,
        "results": records,
    }


async def _fiverr_gig(
    url: str, include_reviews: int = 10, include_raw: bool = False
) -> dict[str, Any]:
    canonical = normalize_gig_url(url)
    if not canonical:
        return {
            "ok": False,
            "url": url,
            "error": (
                "Not a public Fiverr gig URL. Expected "
                "https://www.fiverr.com/<seller>/<gig-slug>."
            ),
        }
    try:
        fetcher = _make_fetcher()
        async with httpx.AsyncClient(**fetcher._client_kwargs()) as client:
            gig = await fetcher._fetch_gig(client, canonical)
    except Exception as exc:
        return {"ok": False, "url": canonical, "error": _public_error(exc)}
    payload = trim_gig_record(
        gig.to_dict(), include_reviews=include_reviews, include_raw=include_raw
    )
    response: dict[str, Any] = {"ok": not bool(gig.error), "url": canonical, "gig": payload}
    if gig.error:
        response["error"] = gig.error
    return response


async def _fiverr_crawl(
    niche: str, limit: int = 5, include_reviews: int = 5, include_raw: bool = False
) -> dict[str, Any]:
    niche, invalid = _clean_niche(niche)
    if invalid is not None:
        return invalid
    limit = _clamp(limit, 1, CRAWL_LIMIT_CAP)
    try:
        fetcher = _make_fetcher()
        payload = await fetcher.crawl(niche, limit, collect_results=True)
    except Exception as exc:
        return {"ok": False, "niche": niche, "error": _public_error(exc)}
    trimmed_results = []
    for result in payload.get("results", []):
        search = result.get("search") or {}
        trimmed = trim_gig_record(
            result, include_reviews=include_reviews, include_raw=include_raw
        )
        trimmed["search"] = trim_search_record(search, include_raw=include_raw)
        trimmed_results.append(trimmed)
    payload["results"] = trimmed_results
    payload["ok"] = True
    payload["note"] = (
        f"MCP calls are capped at {CRAWL_LIMIT_CAP} gigs per request "
        "(MCP_CRAWL_LIMIT_MAX). For larger jobs use the web app, which "
        "streams every record into SQLite and exports JSON/CSV."
    )
    return payload


async def _fiverr_listing_quality(url: str) -> dict[str, Any]:
    fetched = await _fiverr_gig(url, include_reviews=0)
    if not fetched.get("ok"):
        return fetched
    return {
        "ok": True,
        "url": fetched["url"],
        "quality": listing_quality(fetched["gig"]),
        "explanation": (
            "How complete the public listing is (title window, description, "
            "packages, FAQ depth, media, tags). This is NOT Fiverr's private "
            "Success Score or any internal ranking metric."
        ),
    }


def _fiverr_field_limits() -> dict[str, Any]:
    return {
        "ok": True,
        "field_limits": FIELD_LIMITS,
        "public_rank_signals": PUBLIC_RANK_SIGNALS,
        "disclaimer": (
            "Private CTR/conversion/Success Score internals are not observable "
            "from public pages and are not claimed here."
        ),
    }


# ---------------------------------------------------------------------------
# MCP wiring. Tools are registered from the plain functions above so tests can
# call the logic directly without the MCP SDK.
# ---------------------------------------------------------------------------

mcp = None
if FastMCP is not None:
    mcp = FastMCP(
        "fiverr-niche-fetcher",
        instructions=(
            "Fetch public Fiverr marketplace data (search rankings, gig pages, "
            "packages, FAQs, reviews) through this repository's public reader "
            "pipeline. Typical workflow: fiverr_search to map a niche, "
            "fiverr_gig for detail on specific URLs, fiverr_crawl to analyse a "
            "whole niche end to end. Only public pages are read; there is no "
            "login, CAPTCHA or private-analytics access."
        ),
    )


if mcp is not None:

    @mcp.tool()
    async def fiverr_search(niche: str, limit: int = 10, include_raw: bool = False) -> dict[str, Any]:
        """Search public Fiverr results for a niche keyword.

        Returns the ordered search cards exactly as the crawler records them:
        organic vs sponsored rank positions, card title, seller name/username,
        seller level/badges, star rating, review count, starting price, online
        status and thumbnail. Results are deduplicated and capped at `limit`
        (max {search_cap} per call).

        Args:
            niche: Search keyword, e.g. "logo design" or "looker studio".
            limit: Number of search cards to return (1-{search_cap}).
            include_raw: Also include the raw card markdown for debugging.

        Returns:
            Dict with ok, count, available_results, pages_scanned, warnings and
            the ordered results list (global_position = overall search rank).
        """.format(search_cap=SEARCH_LIMIT_CAP)
        return await _fiverr_search(niche, limit, include_raw)

    @mcp.tool()
    async def fiverr_gig(
        url: str, include_reviews: int = 10, include_raw: bool = False
    ) -> dict[str, Any]:
        """Fetch the full public detail page of one Fiverr gig.

        Returns title, seller name/level/country, member-since, average
        response time, last delivery, rating and review count, starting price,
        hourly rate when shown, category path, about/gig description, the
        Basic/Standard/Premium package table, FAQs, review summary with star
        distribution, a sample of visible buyer reviews (country, date, price
        range, duration, seller response), related search tags, media gallery
        counts and video presence.

        Args:
            url: Public gig URL, e.g. https://www.fiverr.com/seller/gig-slug.
            include_reviews: How many individual reviews to include (0-50).
            include_raw: Also include raw page text/JSON-LD for debugging.

        Returns:
            Dict with ok, url and the gig record (or error with ok=false).
        """
        return await _fiverr_gig(url, include_reviews, include_raw)

    @mcp.tool()
    async def fiverr_crawl(
        niche: str, limit: int = 5, include_reviews: int = 5, include_raw: bool = False
    ) -> dict[str, Any]:
        """Crawl a whole Fiverr niche: search discovery + every gig page.

        This runs the same two-stage pipeline as the web app: first the public
        search pages are scanned for ranked gig cards, then each gig's public
        detail page is fetched and parsed (packages, FAQs, reviews, tags,
        seller stats). Each result contains the gig record plus its `search`
        rank metadata. Be polite with `limit` — every gig is a separate public
        page request with the project's configured delays.

        Args:
            niche: Search keyword, e.g. "social media manager".
            limit: Gigs to fetch end to end (1-{crawl_cap}; MCP calls are
                   capped lower than the web app's 500-gig jobs).
            include_reviews: Individual reviews per gig (0-50).
            include_raw: Also include raw page/card text for debugging.

        Returns:
            Dict with ok, discovery stats, success/failure counts, warnings
            and the results list ordered by global search position.
        """.format(crawl_cap=CRAWL_LIMIT_CAP)
        return await _fiverr_crawl(niche, limit, include_reviews, include_raw)

    @mcp.tool()
    async def fiverr_listing_quality(url: str) -> dict[str, Any]:
        """Score how complete one public Fiverr gig listing is (deterministic).

        Fetches the gig and checks: title length vs the search-card display
        window, description presence, 3-package ladder, FAQ depth, video,
        gallery size, rating presence and tag signal. The score is a local
        completeness heuristic — it is not Fiverr's private Success Score.

        Args:
            url: Public gig URL, e.g. https://www.fiverr.com/seller/gig-slug.
        """
        return await _fiverr_listing_quality(url)

    @mcp.tool()
    def fiverr_field_limits() -> dict[str, Any]:
        """Return Fiverr's public field limits and rank signals (no network).

        Includes title/description/package/FAQ/tag character limits verified
        against the live gig form, plus the public ranking-signal language from
        Fiverr's help center and what of it is observable from a public crawl.
        Use this before drafting or critiquing gig copy.
        """
        return _fiverr_field_limits()


TOOL_NAMES = (
    "fiverr_search",
    "fiverr_gig",
    "fiverr_crawl",
    "fiverr_listing_quality",
    "fiverr_field_limits",
)


def main() -> None:
    if mcp is None:
        raise SystemExit(
            "The 'mcp' package is not installed. Run:\n"
            "  pip install -r requirements.txt -r requirements-mcp.txt"
        )
    parser = argparse.ArgumentParser(description="Fiverr niche fetcher MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="stdio for desktop clients; streamable-http/sse for remote access",
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("MCP_PORT", "8765"))
    )
    args = parser.parse_args()
    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
