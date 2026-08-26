"""Phase 1 Fiverr public-market crawler.

The crawler collects public search-card/rank metadata and public gig-page data.
It intentionally does not bypass authentication, CAPTCHAs, private analytics,
or access controls. Reader mode sends public URLs to r.jina.ai and can be
turned off with ALLOW_READER_FALLBACK=false.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import inspect
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

FIVERR_BASE = "https://www.fiverr.com"
EXCLUDED_FIRST_PATHS = {
    "about_us",
    "agencies",
    "business",
    "categories",
    "community",
    "content",
    "events",
    "gigs",
    "login",
    "logout",
    "pe",
    "pro",
    "resources",
    "search",
    "start_selling",
    "support",
    "users",
}
GIG_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?fiverr\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_-]+(?:\?[^)\s\]]*)?",
    re.I,
)
CLOUDINARY_PATTERN = re.compile(
    r"https?://(?:fiverr-res|fiverr-dev-res)\.cloudinary\.com/[^\s\]\)>\"']+",
    re.I,
)

ProgressCallback = Callable[[dict[str, Any]], Any]
RecordsCallback = Callable[[list[dict[str, Any]]], Any]
ResultCallback = Callable[[dict[str, Any]], Any]
CancelCheck = Callable[[], bool]


class FetcherError(RuntimeError):
    pass


class CrawlCancelled(FetcherError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FetcherSettings:
    max_concurrency: int = field(
        default_factory=lambda: max(1, min(5, int(os.getenv("MAX_CONCURRENCY", "2"))))
    )
    delay_seconds: float = field(
        default_factory=lambda: max(
            0.0, min(30.0, float(os.getenv("REQUEST_DELAY_SECONDS", "2.0")))
        )
    )
    max_search_pages: int = field(
        default_factory=lambda: max(1, min(50, int(os.getenv("MAX_SEARCH_PAGES", "30"))))
    )
    search_page_delay_seconds: float = field(
        default_factory=lambda: max(
            0.0, min(10.0, float(os.getenv("SEARCH_PAGE_DELAY_SECONDS", "0.75")))
        )
    )
    retry_count: int = field(
        default_factory=lambda: max(0, min(5, int(os.getenv("RETRY_COUNT", "3"))))
    )
    retry_base_delay_seconds: float = field(
        default_factory=lambda: max(
            0.1, min(30.0, float(os.getenv("RETRY_BASE_DELAY_SECONDS", "1.0")))
        )
    )
    reader_timeout_seconds: float = field(
        default_factory=lambda: max(
            15.0, min(180.0, float(os.getenv("READER_TIMEOUT_SECONDS", "90")))
        )
    )
    allow_reader_fallback: bool = field(
        default_factory=lambda: os.getenv("ALLOW_READER_FALLBACK", "true").lower()
        not in {"0", "false", "no"}
    )


@dataclass
class SearchResultRecord:
    url: str
    niche: str
    page_number: int
    page_position: int
    global_position: int
    organic_position: int | None
    sponsored_position: int | None
    is_sponsored: bool
    seller_online: bool
    card_title: str | None = None
    card_seller_name: str | None = None
    card_seller_username: str | None = None
    card_seller_level: str | None = None
    card_rating: float | None = None
    card_review_count: int | None = None
    card_price: float | None = None
    currency: str | None = None
    thumbnail_url: str | None = None
    badges: list[str] = field(default_factory=list)
    raw_card_text: str | None = None
    discovered_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryOutcome:
    records: list[SearchResultRecord]
    source: str
    pages_scanned: int
    available_results: int | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class GigRecord:
    url: str
    fetched_at: str
    fetch_method: str | None = None
    title: str | None = None
    seller_username: str | None = None
    seller_name: str | None = None
    seller_level: str | None = None
    seller_country: str | None = None
    member_since: str | None = None
    average_response_time: str | None = None
    last_delivery: str | None = None
    rating: float | None = None
    review_count: int | None = None
    starting_price_usd: float | None = None
    currency: str | None = None
    hourly_rate_usd: float | None = None
    meta_description: str | None = None
    category_path: list[str] = field(default_factory=list)
    about_text: str | None = None
    packages_text: str | None = None
    packages: list[dict[str, Any]] = field(default_factory=list)
    faq_text: str | None = None
    faqs: list[dict[str, str]] = field(default_factory=list)
    reviews_text: str | None = None
    review_summary: dict[str, Any] = field(default_factory=dict)
    visible_reviews: list[dict[str, Any]] = field(default_factory=list)
    related_tags: list[str] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)
    gallery_count: int = 0
    has_video: bool = False
    json_ld: list[dict[str, Any]] = field(default_factory=list)
    raw_visible_text: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def _emit(callback: Callable[..., Any] | None, *args: Any) -> None:
    if callback is None:
        return
    value = callback(*args)
    if inspect.isawaitable(value):
        await value


def _cancelled(check: CancelCheck | None) -> bool:
    return bool(check and check())


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_gig_url(href: str | None) -> str | None:
    if not href:
        return None
    href = html_lib.unescape(href.strip())
    parsed_pre = urlparse(href)
    if "duckduckgo.com" in parsed_pre.netloc:
        target = parse_qs(parsed_pre.query).get("uddg", [None])[0]
        if target:
            href = unquote(target)

    absolute = urljoin(FIVERR_BASE, href)
    parsed = urlparse(absolute)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host not in {"fiverr.com", "www.fiverr.com"}:
        return None
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        return None
    first, second = parts
    if first.lower() in EXCLUDED_FIRST_PATHS:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", first):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]+", second):
        return None
    if second.lower() in {"portfolio", "reviews", "about"}:
        return None
    return f"{FIVERR_BASE}/{first}/{second}"


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d[\d,]*", str(value))
    return int(match.group(0).replace(",", "")) if match else None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _clean_inline(value: str) -> str:
    value = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _markdown_to_text(markdown: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    cleaned: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^\s{0,4}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if "Markdown Content:" in text[:1000]:
        text = text.split("Markdown Content:", 1)[1].lstrip()
    return text.strip()


def _section(text: str, starts: tuple[str, ...], ends: tuple[str, ...], max_chars: int = 60000) -> str | None:
    lowered = text.lower()
    candidates = [(lowered.find(marker.lower()), marker) for marker in starts]
    candidates = [(position, marker) for position, marker in candidates if position >= 0]
    if not candidates:
        return None
    start_position, marker = min(candidates, key=lambda item: item[0])
    content_start = start_position + len(marker)
    endings = [lowered.find(end.lower(), content_start) for end in ends]
    endings = [position for position in endings if position >= 0]
    content_end = min(endings) if endings else len(text)
    value = text[content_start:content_end].strip()
    return value[:max_chars] if value else None


def _markdown_heading_section(markdown: str, heading_pattern: str) -> str | None:
    match = re.search(heading_pattern, markdown, re.I | re.M)
    if not match:
        return None
    rest = markdown[match.end():]
    # Stop at the next heading at the same or higher level (# or ##).
    next_heading = re.search(r"^#{1,2}\s+", rest, re.M)
    return rest[: next_heading.start() if next_heading else len(rest)].strip()


def _meta_content(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str | None:
    attrs: dict[str, str] = {}
    if name:
        attrs["name"] = name
    if prop:
        attrs["property"] = prop
    node = soup.find("meta", attrs=attrs)
    value = node.get("content") if node else None
    return str(value).strip() if value else None


def _parse_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                records.extend(item for item in graph if isinstance(item, dict))
            else:
                records.append(candidate)
    return records


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _first_value(objects: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    for root in objects:
        for obj in _walk_dicts(root):
            for key in keys:
                value = obj.get(key)
                if value not in (None, "", [], {}):
                    return value
    return None


def _entity_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict) and value.get("name"):
        return str(value["name"]).strip()
    return None


def _regex_group(pattern: str, text: str, flags: int = re.I | re.M) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def parse_search_page(
    markdown: str,
    niche: str,
    page_number: int,
    *,
    seen: set[str] | None = None,
    global_start: int = 0,
    organic_start: int = 0,
    sponsored_start: int = 0,
) -> tuple[list[SearchResultRecord], int | None]:
    """Parse ordered search cards, including rank and paid/organic status."""
    seen = seen if seen is not None else set()
    first_matches: list[tuple[int, str, str]] = []
    local_seen: set[str] = set()
    for match in GIG_URL_PATTERN.finditer(markdown):
        raw_url = html_lib.unescape(match.group(0))
        canonical = normalize_gig_url(raw_url)
        if not canonical or canonical in local_seen or canonical in seen:
            continue
        local_seen.add(canonical)
        first_matches.append((match.start(), raw_url, canonical))

    total_match = re.search(r"\b([\d,]+)\s+results\b", markdown, re.I)
    available_results = _to_int(total_match.group(1)) if total_match else None
    records: list[SearchResultRecord] = []
    organic_position = organic_start
    sponsored_position = sponsored_start

    for index, (position, raw_url, canonical) in enumerate(first_matches):
        next_position = first_matches[index + 1][0] if index + 1 < len(first_matches) else len(markdown)
        card_start = markdown.rfind("\n[![", max(0, position - 2500), position)
        if card_start < 0:
            card_start = max(0, position - 800)
        segment = markdown[card_start:next_position]
        parsed_raw = urlparse(raw_url)
        query = parse_qs(parsed_raw.query)
        page_position = _to_int(query.get("pos", [None])[0]) or index + 1
        username = canonical.split("/")[3]

        title: str | None = None
        for link_match in re.finditer(
            r"\[([^\]\n]{3,350})\]\((https?://[^)\s]+)\)", segment, re.I
        ):
            label = _clean_inline(link_match.group(1))
            target = normalize_gig_url(link_match.group(2))
            if target == canonical and re.match(r"(?i)^(?:I will|Our agency will|We will)", label):
                title = label
                break
        if not title:
            image_alt = re.search(r"Image\s+\d+\s*:\s*([^\]]+)", segment, re.I)
            title = _clean_inline(image_alt.group(1)) if image_alt else None

        seller_name = None
        profile_pattern = re.compile(
            rf"\[([^\]\n]{{2,120}})\]\(https?://(?:www\.)?fiverr\.com/{re.escape(username)}(?:\?[^)]*)?\)",
            re.I,
        )
        profile_match = profile_pattern.search(segment)
        if profile_match:
            seller_name = _clean_inline(profile_match.group(1))

        badges = _unique(
            match.group(1)
            for match in re.finditer(
                r"\b(Vetted Pro|Top Rated|Level\s*[12]|Fiverr'?s Choice|Pro)\b",
                segment,
                re.I,
            )
        )
        level = next(
            (badge for badge in badges if re.match(r"(?i)^(?:Level|Top Rated|Vetted Pro)", badge)),
            None,
        )
        rating_match = re.search(
            r"\*\*([1-5](?:\.\d)?)\*\*\s*\(([\d,]+)", segment
        )
        price_match = re.search(r"(?:From|Starting at)\s*\$\s*([\d,.]+)", segment, re.I)
        sponsored = bool(re.search(r"(?im)^\s*(?:Ad|Promoted)\s*$", segment))
        if sponsored:
            sponsored_position += 1
            current_organic: int | None = None
            current_sponsored: int | None = sponsored_position
        else:
            organic_position += 1
            current_organic = organic_position
            current_sponsored = None

        cloudinary_urls = [html_lib.unescape(value) for value in CLOUDINARY_PATTERN.findall(segment)]
        thumbnail = next(
            (
                value
                for value in cloudinary_urls
                if "t_gig_cards" in value or "/gigs/" in value or "/gigs2/" in value
            ),
            cloudinary_urls[0] if cloudinary_urls else None,
        )

        records.append(
            SearchResultRecord(
                url=canonical,
                niche=niche,
                page_number=page_number,
                page_position=page_position,
                global_position=global_start + len(records) + 1,
                organic_position=current_organic,
                sponsored_position=current_sponsored,
                is_sponsored=sponsored,
                seller_online=(
                    query.get("seller_online", [""])[0].lower() == "true"
                    or bool(re.search(r"(?im)^\s*Online\s*$", segment))
                ),
                card_title=title,
                card_seller_name=seller_name,
                card_seller_username=username,
                card_seller_level=level,
                card_rating=_to_float(rating_match.group(1)) if rating_match else None,
                card_review_count=_to_int(rating_match.group(2)) if rating_match else None,
                card_price=_to_float(price_match.group(1)) if price_match else None,
                currency="USD" if price_match else None,
                thumbnail_url=thumbnail,
                badges=badges,
                raw_card_text=segment[:6000].strip(),
            )
        )
        seen.add(canonical)

    return records, available_results


def parse_packages_from_markdown(markdown: str) -> tuple[list[dict[str, Any]], str | None]:
    section = _markdown_heading_section(markdown, r"^##\s+Compare packages\s*$")
    packages: list[dict[str, Any]] = []
    if section:
        table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
        rows: list[list[str]] = []
        for line in table_lines:
            cells = [_clean_inline(cell) for cell in line.strip("|").split("|")]
            if all(re.fullmatch(r"[-: ]+", cell or "-") for cell in cells):
                continue
            rows.append(cells)
        if rows and len(rows[0]) >= 2:
            headers = rows[0]
            package_count = len(headers) - 1
            for column in range(1, package_count + 1):
                raw_header = headers[column] if column < len(headers) else f"Package {column}"
                name_match = re.search(r"(Basic|Standard|Premium)", raw_header, re.I)
                name = name_match.group(1).title() if name_match else re.sub(r"\$[\d,.]+", "", raw_header).strip()
                package: dict[str, Any] = {
                    "name": name or f"Package {column}",
                    "price": _to_float(raw_header),
                    "currency": "USD" if "$" in raw_header else None,
                    "description": None,
                    "delivery_time": None,
                    "revisions": None,
                    "features": {},
                }
                for row in rows[1:]:
                    if not row:
                        continue
                    label = row[0].strip() if row else ""
                    value = row[column].strip() if column < len(row) else ""
                    if not label and value and not package["description"]:
                        package["description"] = value
                        continue
                    if not label:
                        continue
                    lowered = label.lower()
                    if lowered == "total" and package["price"] is None:
                        package["price"] = _to_float(value)
                    elif "delivery" in lowered:
                        package["delivery_time"] = value or None
                    elif "revision" in lowered:
                        package["revisions"] = value or None
                    elif lowered != "package":
                        package["features"][label] = value or None
                packages.append(package)

    if not packages:
        # Fiverr often renders only the selected package above the page body.
        selected = re.search(
            r"^###\s+\*\*(Basic|Standard|Premium)\*\*\s*(.*?)(?=^###\s+|^#\s+I will|\nContinue\s*$)",
            markdown,
            re.I | re.M | re.S,
        )
        if selected:
            name, block = selected.group(1).title(), selected.group(2)
            price_match = re.search(r"\$\s*([\d,.]+)", block)
            delivery_match = re.search(r"\*\*([^*]*delivery)\*\*", block, re.I)
            revision_match = re.search(r"\*\*([^*]*Revision[^*]*)\*\*", block, re.I)
            features = [
                _clean_inline(match.group(1))
                for match in re.finditer(r"(?m)^\*\s+(.+)$", block)
            ]
            plain_lines = [
                _clean_inline(line)
                for line in block.splitlines()
                if _clean_inline(line)
                and "$" not in line
                and "service fees" not in line.lower()
                and "delivery" not in line.lower()
                and "revision" not in line.lower()
                and not line.lstrip().startswith("*")
            ]
            packages.append(
                {
                    "name": name,
                    "price": _to_float(price_match.group(1)) if price_match else None,
                    "currency": "USD" if price_match else None,
                    "description": plain_lines[0] if plain_lines else None,
                    "delivery_time": _clean_inline(delivery_match.group(1)) if delivery_match else None,
                    "revisions": _clean_inline(revision_match.group(1)) if revision_match else None,
                    "features": {feature: True for feature in features},
                }
            )

    return packages, _markdown_to_text(section) if section else None


def parse_faqs_from_markdown(markdown: str) -> tuple[list[dict[str, str]], str | None]:
    # Match any heading level (# / ## / ###) with common FAQ label variants:
    # "FAQ", "FAQs", "Frequently Asked Question", "Frequently Asked Questions"
    section = _markdown_heading_section(
        markdown, r"^#{1,3}\s+(?:FAQs?|Frequently Asked Questions?)\s*$"
    )
    if not section:
        return [], None
    faqs: list[dict[str, str]] = []

    # Strategy 1: ### sub-heading per question (most common Jina format)
    headings = list(re.finditer(r"^###\s+(.+?)\s*$", section, re.M))
    for index, heading in enumerate(headings):
        question = _clean_inline(heading.group(1))
        end = headings[index + 1].start() if index + 1 < len(headings) else len(section)
        answer = _markdown_to_text(section[heading.end():end]).strip()
        if question and answer:
            faqs.append({"question": question, "answer": answer})

    if not faqs:
        # Strategy 2: **Bold question** / paragraph answer layout.
        # Relax the trailing '?' requirement so questions without it are also captured.
        matches = list(re.finditer(r"(?m)^\*\*(.+?)\*\*\s*$", section))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
            answer = _markdown_to_text(section[match.end():end]).strip()
            if answer:
                faqs.append({"question": _clean_inline(match.group(1)), "answer": answer})

    if not faqs:
        # Strategy 3: Q&A paragraph style — alternating non-blank lines where
        # odd lines are questions (end with '?' or are short) and even lines are answers.
        # Split on blank lines to get paragraph pairs.
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", section) if p.strip()]
        index = 0
        while index < len(paragraphs) - 1:
            candidate_q = _markdown_to_text(paragraphs[index]).strip()
            candidate_a = _markdown_to_text(paragraphs[index + 1]).strip()
            # A question paragraph: short (≤200 chars), does not start with a list marker,
            # and ideally ends with '?' or starts with a question word.
            looks_like_question = (
                len(candidate_q) <= 200
                and not candidate_q.startswith(("-", "*", "#"))
                and (
                    candidate_q.endswith("?")
                    or re.match(r"(?i)^(?:what|how|why|when|can|do|does|is|are|will|should|who)", candidate_q)
                )
            )
            if looks_like_question and candidate_a and not candidate_a.endswith("?"):
                faqs.append({"question": candidate_q, "answer": candidate_a})
                index += 2
            else:
                index += 1

    return faqs, _markdown_to_text(section)



def _review_markdown_section(markdown: str) -> str | None:
    marker = re.search(r"^##\s+[\d,]+\s+reviews?\s+for\s+this\s+Gig\s*$", markdown, re.I | re.M)
    if not marker:
        marker = re.search(r"^Reviews\s*$", markdown, re.I | re.M)
    if not marker:
        return None
    tail = markdown[marker.start():]
    endings: list[int] = []
    related = re.search(r"^##\s+Related tags\s*$", tail, re.I | re.M)
    if related:
        endings.append(related.start())
    duplicate = re.search(
        r"^Reviews\s*\n\s*##\s+[\d,]+\s+reviews?\s+for\s+this\s+Gig",
        tail[200:],
        re.I | re.M,
    )
    if duplicate:
        endings.append(200 + duplicate.start())
    end = min(endings) if endings else len(tail)
    return tail[:end].strip()


def parse_reviews_from_markdown(markdown: str) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    section = _review_markdown_section(markdown)
    if not section:
        return {}, [], None

    total_match = re.search(r"##\s+([\d,]+)\s+reviews?", section, re.I)
    overall_match = re.search(r"\n\*\*([1-5](?:\.\d)?)\*\*\s*\n", section)
    stars: dict[str, int] = {}
    for star, count in re.findall(r"([1-5])\s+Stars?\s*\(([\d,]+)\)", section, re.I):
        stars[star] = _to_int(count) or 0
    breakdown: dict[str, float] = {}
    for label, value in re.findall(
        r"(?m)^\*\s+([^\n*]+?)\s+\*\*([1-5](?:\.\d)?)\*\*\s*$", section
    ):
        breakdown[_clean_inline(label)] = float(value)
    files_match = re.search(r"Only show reviews with files\s*\(([\d,]+)\)", section, re.I)
    summary: dict[str, Any] = {
        "total_reviews": _to_int(total_match.group(1)) if total_match else None,
        "overall_rating": _to_float(overall_match.group(1)) if overall_match else None,
        "star_distribution": stars,
        "rating_breakdown": breakdown,
        "reviews_with_files": _to_int(files_match.group(1)) if files_match else None,
    }

    entries: list[dict[str, Any]] = []
    entry_chunks = re.split(r"(?m)^\*\s{2,}", section)
    seen_keys: set[tuple[str, str, str]] = set()
    for chunk in entry_chunks:
        flag = re.search(
            r"!\[Image\s+\d+\s*:\s*([A-Z]{2})\]\(https?://fiverr-dev-res\.cloudinary\.com/general_assets/flags/[^)]+\)",
            chunk,
        )
        date_match = re.search(
            r"\b(\d+\s+(?:day|week|month|year)s?\s+ago)\b", chunk, re.I
        )
        rating_match = re.search(r"\*\*([1-5](?:\.\d)?)\*\*", chunk)
        if not flag or not date_match or not rating_match:
            continue

        before_flag = chunk[: flag.start()]
        before_flag = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", before_flag)
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.-]+", before_flag)
        username = tokens[-1] if tokens else "unknown"
        after_flag = chunk[flag.end():]
        country_match = re.match(r"\s*\n?\s*([^\n*]{2,80})", after_flag)
        country = _clean_inline(country_match.group(1)) if country_match else None

        rest = chunk[date_match.end():]
        price_match = re.search(r"\$[\d,]+(?:\s*-\s*\$[\d,]+)?", rest)
        review_end_candidates = [
            match.start()
            for pattern in (r"Seller's Response", r"Helpful\?", r"Price\s+")
            if (match := re.search(pattern, rest, re.I))
        ]
        if price_match:
            review_end_candidates.append(price_match.start())
        review_end = min(review_end_candidates) if review_end_candidates else len(rest)
        review_text = _markdown_to_text(rest[:review_end]).strip(" -\n")
        duration_match = re.search(
            r"Price\s+(.{1,40}?)\s+Duration", rest, re.I | re.S
        )
        response_match = re.search(
            r"Seller's Response\s+(.*?)\s+Helpful\?", rest, re.I | re.S
        )
        sample_match = re.search(
            r"(https?://fiverr-res\.cloudinary\.com/[^\s\)]*t_delivery_large[^\s\)]*)",
            rest,
            re.I,
        )
        key = (username, date_match.group(1).lower(), review_text[:100])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        entries.append(
            {
                "username": username,
                "country_code": flag.group(1),
                "country": country,
                "rating": _to_float(rating_match.group(1)),
                "relative_date": date_match.group(1),
                "text": review_text or None,
                "price": price_match.group(0).replace(" ", "") if price_match else None,
                "duration": _clean_inline(duration_match.group(1)) if duration_match else None,
                "ongoing_collaboration": "ongoing collaboration" in chunk.lower(),
                "work_sample_url": html_lib.unescape(sample_match.group(1)) if sample_match else None,
                "seller_response": _markdown_to_text(response_match.group(1)).strip() if response_match else None,
            }
        )
        if len(entries) >= 50:
            break

    summary["visible_reviews_parsed"] = len(entries)
    return summary, entries, _markdown_to_text(section)


def parse_category_path(markdown: str) -> list[str]:
    h1 = re.search(r"^#\s+I will\b", markdown, re.I | re.M)
    prefix = markdown[: h1.start()] if h1 else markdown[:10000]
    labels = re.findall(
        r"\[([^\]]+)\]\(https?://(?:www\.)?fiverr\.com/categories/[^)]+\)",
        prefix,
        re.I,
    )
    return _unique(_clean_inline(label) for label in labels if _clean_inline(label))[-5:]


def _extract_media_urls(soup: BeautifulSoup, source_text: str = "") -> list[str]:
    urls: list[str] = []
    for image in soup.find_all("img"):
        for attribute in ("src", "data-src", "data-lazy-src"):
            value = image.get(attribute)
            if isinstance(value, str) and "cloudinary.com" in value:
                urls.append(value)
        srcset = image.get("srcset")
        if isinstance(srcset, str):
            urls.extend(
                item.strip().split(" ", 1)[0]
                for item in srcset.split(",")
                if "cloudinary.com" in item
            )
    urls.extend(html_lib.unescape(match) for match in CLOUDINARY_PATTERN.findall(source_text))
    return _unique(urls)[:150]


def _reader_title(markdown: str, url: str) -> str:
    heading = re.search(r"^#\s+(.+?)\s*$", markdown, re.M)
    if heading:
        return _clean_inline(heading.group(1))
    metadata = re.search(r"^Title:\s*(.+?)\s*$", markdown, re.M)
    if metadata:
        value = metadata.group(1).strip()
        value = re.sub(r"^[^:]{1,80}:\s+(?=I will\b)", "", value, flags=re.I)
        value = re.sub(r"\s+for\s+\$[\d,.]+\s+on\s+fiverr\.com\s*$", "", value, flags=re.I)
        return value.strip()
    return urlparse(url).path.rstrip("/").split("/")[-1].replace("-", " ").title()


def parse_gig_page(
    url: str,
    html: str,
    visible_text: str,
    page_title: str = "",
    fetch_method: str = "reader",
    source_markdown: str = "",
) -> GigRecord:
    soup = BeautifulSoup(html, "html.parser")
    json_ld = _parse_json_ld(soup)
    path = [part for part in urlparse(url).path.split("/") if part]
    username = path[0] if path else None
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else None
    title = title or _meta_content(soup, prop="og:title") or page_title or None
    if title:
        title = re.sub(r"\s+by\s+[^|]+\|\s*Fiverr\s*$", "", title, flags=re.I).strip()

    service_nodes = [
        node
        for node in json_ld
        if str(node.get("@type", "")).lower() in {"product", "service", "professionalservice"}
    ]
    primary_nodes = service_nodes or json_ld
    aggregate: dict[str, Any] = {}
    for root in primary_nodes:
        for node in _walk_dicts(root):
            if isinstance(node.get("aggregateRating"), dict):
                aggregate = node["aggregateRating"]
                break
        if aggregate:
            break
    rating = _to_float(aggregate.get("ratingValue"))
    review_count = _to_int(aggregate.get("reviewCount") or aggregate.get("ratingCount"))
    rating_match = re.search(
        r"\b([1-5](?:\.\d)?)\s*\(([\d,]+)(?:\s+reviews?)?\)", visible_text[:9000], re.I
    )
    if rating_match:
        rating = rating or _to_float(rating_match.group(1))
        review_count = review_count or _to_int(rating_match.group(2))

    offers = _first_value(primary_nodes, ("offers",))
    offer_list = offers if isinstance(offers, list) else [offers] if offers else []
    prices: list[float] = []
    currency: str | None = None
    for offer in offer_list:
        if not isinstance(offer, dict):
            continue
        price = _to_float(offer.get("lowPrice") or offer.get("price"))
        if price is not None:
            prices.append(price)
        currency = currency or offer.get("priceCurrency")

    packages, packages_text_md = parse_packages_from_markdown(source_markdown) if source_markdown else ([], None)
    package_prices = [float(item["price"]) for item in packages if item.get("price") is not None]
    starting_price = min(prices + package_prices) if prices or package_prices else None
    if starting_price is None:
        price_match = re.search(r"(?:From|Starting at)\s*\$\s*([\d,.]+)", visible_text[:15000], re.I)
        starting_price = _to_float(price_match.group(1)) if price_match else None
    if starting_price is not None:
        currency = currency or "USD"

    seller_name = _regex_group(r"Get to know\s+([^\n\r]+)", visible_text)
    if not seller_name:
        for key in ("seller", "provider", "author", "brand"):
            seller_name = _entity_name(_first_value(primary_nodes, (key,)))
            if seller_name:
                break
    seller_level = _regex_group(
        r"\b(Level\s*[12]|Top Rated|Vetted Pro|New Seller)\b", visible_text[:12000]
    )
    seller_country = _regex_group(r"(?:^|\n)From\s*(?:\n\s*)?([^\n\r]+)", visible_text)
    member_since = _regex_group(r"Member since\s*(?:\n\s*)?([^\n\r]+)", visible_text)
    response_time = _regex_group(r"Avg\.? response time\s*:?\s*(?:\n\s*)?([^\n\r]+)", visible_text)
    last_delivery = _regex_group(r"Last delivery\s*(?:\n\s*)?([^\n\r]+)", visible_text)

    about = _section(
        visible_text,
        ("About this gig", "Gig Summary"),
        ("Get to know", "Compare packages", "About the seller"),
    )
    packages_text = packages_text_md or _section(
        visible_text,
        ("Compare packages",),
        ("Other Data Visualization Services", "Recommended for you", "Reviews", "FAQ"),
    )
    faqs, faq_text = parse_faqs_from_markdown(source_markdown) if source_markdown else ([], None)
    review_summary, visible_reviews, reviews_text_md = (
        parse_reviews_from_markdown(source_markdown) if source_markdown else ({}, [], None)
    )
    reviews_text = reviews_text_md or _section(
        visible_text,
        ("Reviews",),
        ("Related tags", "Message the seller", "Message "),
    )
    if not review_count and review_summary.get("total_reviews"):
        review_count = review_summary["total_reviews"]
    if not rating and review_summary.get("overall_rating"):
        rating = review_summary["overall_rating"]

    tags_text = _section(
        visible_text,
        ("Related tags",),
        ("Message the seller", "Message ", "About Fiverr"),
        max_chars=4000,
    )
    tags = _unique(
        line.strip("•- \t")
        for line in (tags_text or "").splitlines()
        if 1 < len(line.strip("•- \t")) < 80
    )[:30]
    source_for_media = source_markdown or visible_text
    media_urls = _extract_media_urls(soup, source_for_media)
    gallery_urls = [
        item
        for item in media_urls
        if any(token in item for token in ("/gigs/", "/gigs2/", "t_delivery", "attachments/delivery"))
    ]
    hourly_match = re.search(r"\*\*\$\s*([\d,.]+)\*\*\s*/hour", source_markdown, re.I)

    return GigRecord(
        url=url,
        fetched_at=utc_now(),
        fetch_method=fetch_method,
        title=title,
        seller_username=username,
        seller_name=seller_name,
        seller_level=seller_level,
        seller_country=seller_country,
        member_since=member_since,
        average_response_time=response_time,
        last_delivery=last_delivery,
        rating=rating,
        review_count=review_count,
        starting_price_usd=starting_price,
        currency=currency,
        hourly_rate_usd=_to_float(hourly_match.group(1)) if hourly_match else None,
        meta_description=_meta_content(soup, name="description") or _meta_content(soup, prop="og:description"),
        category_path=parse_category_path(source_markdown) if source_markdown else [],
        about_text=about,
        packages_text=packages_text,
        packages=packages,
        faq_text=faq_text,
        faqs=faqs,
        reviews_text=reviews_text,
        review_summary=review_summary,
        visible_reviews=visible_reviews,
        related_tags=tags,
        media_urls=media_urls,
        gallery_count=len(_unique(gallery_urls)),
        has_video=("video/upload" in source_markdown or bool(re.search(r"\[Video\s+\d+", source_markdown))),
        json_ld=json_ld[:25],
        raw_visible_text=visible_text.strip(),
    )


class FiverrNicheFetcher:
    def __init__(self, settings: FetcherSettings | None = None) -> None:
        self.settings = settings or FetcherSettings()
        if not self.settings.allow_reader_fallback:
            raise FetcherError(
                "Phase 1 background crawler currently requires public reader mode. "
                "Set ALLOW_READER_FALLBACK=true."
            )

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Accept": "text/markdown", "User-Agent": "Mozilla/5.0"}

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.settings.retry_count + 1):
            try:
                response = await client.get(url)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        f"Retryable status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                if len(response.text.strip()) < 200:
                    raise FetcherError("Reader returned an empty or unusable response.")
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.retry_count:
                    break
                retry_after = None
                if isinstance(exc, httpx.HTTPStatusError):
                    retry_after = exc.response.headers.get("Retry-After")
                wait = (
                    _to_float(retry_after)
                    if retry_after
                    else self.settings.retry_base_delay_seconds * (2**attempt)
                )
                await asyncio.sleep(min(float(wait or 1), 30.0))
        raise FetcherError(f"Reader request failed after retries: {last_error}")

    async def discover_search(
        self,
        niche: str,
        limit: int,
        *,
        on_progress: ProgressCallback | None = None,
        on_records: RecordsCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> DiscoveryOutcome:
        niche = " ".join(niche.split()).strip()
        limit = max(1, min(500, int(limit)))
        query = quote_plus(niche)
        collected: list[SearchResultRecord] = []
        seen: set[str] = set()
        pages_without_new = 0
        pages_scanned = 0
        available_results: int | None = None
        organic_count = 0
        sponsored_count = 0
        warnings: list[str] = []

        timeout = httpx.Timeout(self.settings.reader_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=self._headers()) as client:
            for page_number in range(1, self.settings.max_search_pages + 1):
                if _cancelled(cancel_check):
                    raise CrawlCancelled("Job cancelled during search discovery.")
                source = (
                    f"http://www.fiverr.com/search/gigs?query={query}"
                    f"&source=top-bar&search_in=everywhere&page={page_number}"
                )
                reader_url = f"https://r.jina.ai/{source}"
                try:
                    markdown = await self._get_text(client, reader_url)
                except Exception as exc:
                    if collected:
                        warnings.append(f"Search page {page_number} stopped pagination: {exc}")
                        break
                    raise
                pages_scanned = page_number
                page_records, page_total = parse_search_page(
                    markdown,
                    niche,
                    page_number,
                    seen=seen,
                    global_start=len(collected),
                    organic_start=organic_count,
                    sponsored_start=sponsored_count,
                )
                if page_total is not None:
                    available_results = page_total
                if page_records:
                    pages_without_new = 0
                    for record in page_records:
                        if record.is_sponsored:
                            sponsored_count = max(sponsored_count, record.sponsored_position or 0)
                        else:
                            organic_count = max(organic_count, record.organic_position or 0)
                        collected.append(record)
                        if len(collected) >= limit:
                            break
                    await _emit(on_records, [record.to_dict() for record in page_records if record.global_position <= limit])
                else:
                    pages_without_new += 1

                await _emit(
                    on_progress,
                    {
                        "stage": "discovering",
                        "pages_scanned": pages_scanned,
                        "available_results": available_results,
                        "discovered_count": min(len(collected), limit),
                        "progress_percent": min(15.0, 2.0 + pages_scanned * 0.75),
                    },
                )
                if len(collected) >= limit or pages_without_new >= 2:
                    break
                await asyncio.sleep(self.settings.search_page_delay_seconds)

        return DiscoveryOutcome(
            records=collected[:limit],
            source="reader-search",
            pages_scanned=pages_scanned,
            available_results=available_results,
            warnings=warnings,
        )

    async def _fetch_gig(self, client: httpx.AsyncClient, url: str) -> GigRecord:
        parsed = urlparse(url)
        source = f"https://{parsed.netloc}{parsed.path}"
        reader_url = f"https://r.jina.ai/{source}"
        try:
            markdown = (await self._get_text(client, reader_url)).strip()
            title = _reader_title(markdown, url)
            visible_text = _markdown_to_text(markdown)
            media_urls = _unique(html_lib.unescape(match) for match in CLOUDINARY_PATTERN.findall(markdown))[:150]
            synthetic_html = (
                "<html><body><h1>"
                + html_lib.escape(title)
                + "</h1>"
                + "".join(
                    f'<img src="{html_lib.escape(media_url, quote=True)}">'
                    for media_url in media_urls
                )
                + "</body></html>"
            )
            return parse_gig_page(
                url,
                synthetic_html,
                visible_text,
                title,
                fetch_method="reader",
                source_markdown=markdown,
            )
        except Exception as exc:
            path = [part for part in parsed.path.split("/") if part]
            return GigRecord(
                url=url,
                fetched_at=utc_now(),
                fetch_method="failed",
                seller_username=path[0] if path else None,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def crawl(
        self,
        niche: str,
        limit: int = 5,
        *,
        on_progress: ProgressCallback | None = None,
        on_search_records: RecordsCallback | None = None,
        on_result: ResultCallback | None = None,
        cancel_check: CancelCheck | None = None,
        collect_results: bool = True,
    ) -> dict[str, Any]:
        niche = " ".join(niche.split()).strip()
        if len(niche) < 2:
            raise FetcherError("Niche kam az kam 2 characters ka hona chahiye.")
        limit = max(1, min(500, int(limit)))
        started_at = utc_now()
        await _emit(on_progress, {"stage": "discovering", "progress_percent": 1.0})
        discovery = await self.discover_search(
            niche,
            limit,
            on_progress=on_progress,
            on_records=on_search_records,
            cancel_check=cancel_check,
        )
        records = discovery.records
        discovered_count = len(records)
        await _emit(
            on_progress,
            {
                "stage": "fetching",
                "pages_scanned": discovery.pages_scanned,
                "available_results": discovery.available_results,
                "discovered_count": discovered_count,
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "progress_percent": 15.0,
                "discovery_source": discovery.source,
                "warnings": discovery.warnings,
            },
        )
        if not records:
            return {
                "niche": niche,
                "started_at": started_at,
                "finished_at": utc_now(),
                "discovery_source": discovery.source,
                "pages_scanned": discovery.pages_scanned,
                "available_results": discovery.available_results,
                "discovered_count": 0,
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "cancelled": False,
                "warnings": discovery.warnings,
                "results": [],
            }

        queue: asyncio.Queue[SearchResultRecord] = asyncio.Queue()
        for record in records:
            queue.put_nowait(record)
        processed = 0
        successes = 0
        failures = 0
        results: list[dict[str, Any]] = []
        counter_lock = asyncio.Lock()
        timeout = httpx.Timeout(self.settings.reader_timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=self._headers()) as client:
            async def worker() -> None:
                nonlocal processed, successes, failures
                while not queue.empty():
                    if _cancelled(cancel_check):
                        return
                    try:
                        search_record = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    try:
                        gig = await self._fetch_gig(client, search_record.url)
                        # Search-card metadata is a useful fallback when a detail
                        # page omits an agency/seller field in its public rendering.
                        gig.title = gig.title or search_record.card_title
                        gig.seller_name = gig.seller_name or search_record.card_seller_name
                        gig.seller_username = gig.seller_username or search_record.card_seller_username
                        gig.seller_level = gig.seller_level or search_record.card_seller_level
                        gig.rating = gig.rating or search_record.card_rating
                        gig.review_count = gig.review_count or search_record.card_review_count
                        gig.starting_price_usd = gig.starting_price_usd or search_record.card_price
                        gig.currency = gig.currency or search_record.currency
                        if not gig.review_summary:
                            gig.review_summary = {}
                        if not gig.review_summary.get("total_reviews"):
                            gig.review_summary["total_reviews"] = gig.review_count
                        if not gig.review_summary.get("overall_rating"):
                            gig.review_summary["overall_rating"] = gig.rating
                        result = gig.to_dict()
                        result["search"] = search_record.to_dict()
                        await _emit(on_result, result)
                        if collect_results:
                            results.append(result)
                        async with counter_lock:
                            processed += 1
                            if gig.error:
                                failures += 1
                            else:
                                successes += 1
                            progress = 15.0 + (85.0 * processed / discovered_count)
                            snapshot = {
                                "stage": "fetching",
                                "pages_scanned": discovery.pages_scanned,
                                "available_results": discovery.available_results,
                                "discovered_count": discovered_count,
                                "processed_count": processed,
                                "success_count": successes,
                                "failed_count": failures,
                                "progress_percent": min(99.5, progress),
                                "discovery_source": discovery.source,
                                "warnings": discovery.warnings,
                            }
                        await _emit(on_progress, snapshot)
                    finally:
                        queue.task_done()
                        await asyncio.sleep(self.settings.delay_seconds)

            workers = [
                asyncio.create_task(worker())
                for _ in range(min(self.settings.max_concurrency, discovered_count))
            ]
            await asyncio.gather(*workers)

        was_cancelled = _cancelled(cancel_check)
        if collect_results:
            results.sort(key=lambda item: (item.get("search") or {}).get("global_position", 999999))
        finished_at = utc_now()
        return {
            "niche": niche,
            "started_at": started_at,
            "finished_at": finished_at,
            "discovery_source": discovery.source,
            "pages_scanned": discovery.pages_scanned,
            "available_results": discovery.available_results,
            "discovered_count": discovered_count,
            "processed_count": processed,
            "success_count": successes,
            "failed_count": failures,
            "cancelled": was_cancelled,
            "warnings": discovery.warnings,
            "results": results,
        }

    async def run(self, niche: str, limit: int = 5) -> dict[str, Any]:
        """Compatibility synchronous-style API used by tests and scripts."""
        return await self.crawl(niche, limit, collect_results=True)
