"""Deterministic Phase 2 market intelligence (no LLM, no embeddings)."""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable

from fiverr_metadata import listing_quality
from storage import Storage, utc_now

ANALYSIS_VERSION = "phase2-v1"
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+.#-]*", re.I)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "get", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "our", "that", "the", "this", "to", "we", "will", "with", "you", "your",
    "aka", "using", "use", "make", "professional", "best", "expert", "service",
    "services", "custom", "create", "build", "provide", "design", "help",
}
CLUSTER_GENERIC = {
    "dashboard", "dashboards", "report", "reports", "data", "studio", "create",
    "professional", "custom", "service", "services", "expert", "using",
}
POSITIVE_WORDS = {
    "accurate", "amazing", "awesome", "clear", "excellent", "exceptional", "fast",
    "great", "helpful", "impressed", "outstanding", "patient", "perfect",
    "professional", "quality", "quick", "recommend", "responsive", "satisfied",
    "skilled", "smooth", "timely", "wonderful",
}
NEGATIVE_WORDS = {
    "bad", "confusing", "delay", "delayed", "disappointed", "error", "errors",
    "inaccurate", "issue", "issues", "late", "missing", "poor", "problem",
    "problems", "revision", "slow", "unprofessional", "unresponsive", "wrong",
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _rounded(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def _quantile(sorted_values: list[float], probability: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def numeric_stats(values: Iterable[Any]) -> dict[str, Any]:
    cleaned = sorted(value for raw in values if (value := _number(raw)) is not None)
    if not cleaned:
        return {
            "count": 0, "min": None, "q1": None, "median": None,
            "mean": None, "q3": None, "p90": None, "max": None,
        }
    return {
        "count": len(cleaned),
        "min": _rounded(cleaned[0]),
        "q1": _rounded(_quantile(cleaned, 0.25)),
        "median": _rounded(_quantile(cleaned, 0.50)),
        "mean": _rounded(statistics.fmean(cleaned)),
        "q3": _rounded(_quantile(cleaned, 0.75)),
        "p90": _rounded(_quantile(cleaned, 0.90)),
        "max": _rounded(cleaned[-1]),
    }


def _distribution(values: Iterable[str | None], limit: int = 30) -> list[dict[str, Any]]:
    counter = Counter(str(value).strip() for value in values if value and str(value).strip())
    total = sum(counter.values())
    return [
        {"label": label, "count": count, "share_pct": _rounded(100 * count / total, 1)}
        for label, count in counter.most_common(limit)
    ]


def _tokens(text: str | None, *, remove_stopwords: bool = True) -> list[str]:
    raw = [token.lower().strip("-.") for token in TOKEN_RE.findall(text or "")]
    result = []
    for token in raw:
        if not token or token.isdigit():
            continue
        if len(token) < 3 and token not in {"ai", "bi", "ga4", "ui", "ux", "3d"}:
            continue
        if remove_stopwords and token in STOPWORDS:
            continue
        result.append(token)
    return result


def _ngrams(tokens: list[str], size: int) -> list[str]:
    if len(tokens) < size:
        return []
    return [" ".join(tokens[index:index + size]) for index in range(len(tokens) - size + 1)]


def _rank_band(rank: int | None) -> str:
    if rank is None:
        return "Unknown"
    if rank <= 10:
        return "Top 10"
    if rank <= 20:
        return "11–20"
    if rank <= 50:
        return "21–50"
    if rank <= 100:
        return "51–100"
    return "101+"


def _normalize_feature(value: str) -> str:
    value = re.sub(r"[^a-z0-9+.# ]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def _flatten(prefix: str, value: Any, rows: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), child, rows)
    elif isinstance(value, list):
        rows.append({"metric": prefix, "value": str(value)})
    else:
        rows.append({"metric": prefix, "value": value})


class MarketAnalyzer:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def analyze(self, job_id: str) -> dict[str, Any]:
        job = self.storage.get_job(job_id)
        if job is None:
            raise ValueError("Job not found")
        search_rows = self.storage.get_all_search_results(job_id)
        details = self.storage.get_all_job_results(job_id)
        detail_by_url = {str(item.get("url")): item for item in details}
        competitors = self._competitors(search_rows, detail_by_url)
        documents = [(row, detail_by_url.get(row["url"], {})) for row in competitors]

        overview = self._overview(job, competitors, documents)
        rankings = self._rankings(competitors)
        rank_movement = self._rank_movement(job_id, job, competitors)
        keywords, keyword_internal = self._keywords(documents)
        clusters = self._clusters(keyword_internal, competitors)
        pricing = self._pricing(competitors, documents)
        packages, package_internal = self._packages(documents)
        reviews, review_internal = self._reviews(documents)
        gaps = self._gaps(
            keywords,
            keyword_internal,
            competitors,
            packages,
            package_internal,
            reviews,
            review_internal,
            pricing,
        )
        quality_rows = [
            listing_quality({**competitor, **detail}) for competitor, detail in documents
        ]
        scores = [row["score"] for row in quality_rows]
        listing = {
            "mean_score": _rounded(_mean(scores)),
            "complete_listings": sum(row["score"] >= 75 for row in quality_rows),
            "video_ready": sum(bool(detail.get("has_video") or competitor.get("has_video")) for competitor, detail in documents),
            "note": "Public listing-completeness score, not Fiverr Success Score or CTR.",
            "rows": quality_rows[:100],
        }

        analysis = {
            "version": ANALYSIS_VERSION,
            "generated_at": utc_now(),
            "job_id": job_id,
            "niche": job["niche"],
            "methodology": {
                "llm_used": False,
                "approach": "Deterministic SQL/statistics, n-grams, lexicons and transparent heuristics",
                "rank_note": "Observed public-session rank, not Fiverr's universal or secret score.",
                "opportunity_note": "Diagnostic market-research score, not an official Fiverr ranking factor.",
            },
            "overview": overview,
            "rankings": rankings,
            "rank_movement": rank_movement,
            "keywords": keywords,
            "keyword_clusters": clusters,
            "pricing": pricing,
            "packages": packages,
            "competitors": competitors,
            "reviews": reviews,
            "market_gaps": gaps,
            "listing_quality": listing,
        }
        return analysis

    @staticmethod
    def _competitors(
        search_rows: list[dict[str, Any]], detail_by_url: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for search in search_rows:
            url = str(search.get("url"))
            detail = detail_by_url.get(url, {})
            price = detail.get("starting_price_usd")
            if price is None:
                price = search.get("card_price")
            rating = detail.get("rating")
            if rating is None:
                rating = search.get("card_rating")
            review_count = detail.get("review_count")
            if review_count is None:
                review_count = search.get("card_review_count")
            seller = detail.get("seller_name") or search.get("card_seller_name")
            username = detail.get("seller_username") or search.get("card_seller_username")
            level = detail.get("seller_level") or search.get("card_seller_level")
            rank = search.get("global_position")
            packages = detail.get("packages") or []
            output.append(
                {
                    "url": url,
                    "title": detail.get("title") or search.get("card_title"),
                    "seller": seller,
                    "seller_username": username,
                    "seller_level": level,
                    "seller_country": detail.get("seller_country"),
                    "global_position": rank,
                    "organic_position": search.get("organic_position"),
                    "sponsored_position": search.get("sponsored_position"),
                    "page_number": search.get("page_number"),
                    "page_position": search.get("page_position"),
                    "is_sponsored": bool(search.get("is_sponsored")),
                    "seller_online": bool(search.get("seller_online")),
                    "price": _rounded(_number(price)),
                    "rating": _rounded(_number(rating)),
                    "review_count": int(_number(review_count) or 0),
                    "badges": search.get("badges") or [],
                    "thumbnail_url": search.get("thumbnail_url"),
                    "has_video": bool(detail.get("has_video")),
                    "gallery_count": int(detail.get("gallery_count") or 0),
                    "package_count": len(packages),
                    "faq_count": len(detail.get("faqs") or []),
                    "visible_review_count": len(detail.get("visible_reviews") or []),
                    "hourly_rate_usd": _rounded(_number(detail.get("hourly_rate_usd"))),
                    "category_path": detail.get("category_path") or [],
                    "rank_band": _rank_band(int(rank) if rank is not None else None),
                    "detail_status": "failed" if detail.get("error") else "success" if detail else "not_fetched",
                }
            )
        return sorted(output, key=lambda item: item.get("global_position") or 999999)

    @staticmethod
    def _overview(
        job: dict[str, Any],
        competitors: list[dict[str, Any]],
        documents: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> dict[str, Any]:
        count = len(competitors)
        organic = sum(not item["is_sponsored"] for item in competitors)
        sponsored = count - organic
        successful = sum(item["detail_status"] == "success" for item in competitors)
        unique_sellers = len({item.get("seller_username") for item in competitors if item.get("seller_username")})
        video_count = sum(item.get("has_video", False) for item in competitors)
        hourly_count = sum(item.get("hourly_rate_usd") is not None for item in competitors)
        package_count = sum(item.get("package_count", 0) > 0 for item in competitors)
        faq_count = sum(item.get("faq_count", 0) > 0 for item in competitors)
        return {
            "available_results": job.get("available_results"),
            "requested_limit": job.get("requested_limit"),
            "sampled_gigs": count,
            "detail_success_count": successful,
            "detail_coverage_pct": _rounded(100 * successful / count, 1) if count else 0,
            "unique_sellers": unique_sellers,
            "organic_count": organic,
            "sponsored_count": sponsored,
            "sponsored_share_pct": _rounded(100 * sponsored / count, 1) if count else 0,
            "starting_price": numeric_stats(item.get("price") for item in competitors),
            "rating": numeric_stats(item.get("rating") for item in competitors),
            "review_count": numeric_stats(item.get("review_count") for item in competitors),
            "gallery_count": numeric_stats(item.get("gallery_count") for item in competitors),
            "video_gig_count": video_count,
            "video_share_pct": _rounded(100 * video_count / count, 1) if count else 0,
            "hourly_offer_count": hourly_count,
            "hourly_offer_share_pct": _rounded(100 * hourly_count / count, 1) if count else 0,
            "package_data_count": package_count,
            "package_data_share_pct": _rounded(100 * package_count / count, 1) if count else 0,
            "faq_data_count": faq_count,
            "faq_data_share_pct": _rounded(100 * faq_count / count, 1) if count else 0,
            "seller_levels": _distribution(item.get("seller_level") or "Unknown" for item in competitors),
            "seller_countries": _distribution(item.get("seller_country") or "Unknown" for item in competitors),
            "rank_bands": _distribution(item.get("rank_band") for item in competitors),
        }

    @staticmethod
    def _rankings(competitors: list[dict[str, Any]]) -> dict[str, Any]:
        sellers: dict[str, dict[str, Any]] = {}
        for item in competitors:
            key = item.get("seller_username") or item.get("seller")
            if not key:
                continue
            bucket = sellers.setdefault(
                str(key),
                {
                    "seller": item.get("seller"),
                    "seller_username": item.get("seller_username"),
                    "gig_count": 0,
                    "ranks": [],
                    "sponsored_count": 0,
                },
            )
            bucket["gig_count"] += 1
            if item.get("global_position") is not None:
                bucket["ranks"].append(item["global_position"])
            bucket["sponsored_count"] += int(item.get("is_sponsored", False))
        concentration = []
        for bucket in sellers.values():
            ranks = bucket.pop("ranks")
            bucket["best_rank"] = min(ranks) if ranks else None
            bucket["average_rank"] = _rounded(_mean(ranks))
            concentration.append(bucket)
        concentration.sort(key=lambda row: (-row["gig_count"], row["best_rank"] or 999999))
        return {
            "top_gigs": competitors[:100],
            "top_10": competitors[:10],
            "top_20": competitors[:20],
            "seller_concentration": concentration[:100],
            "placement": {
                "organic": sum(not item["is_sponsored"] for item in competitors),
                "sponsored": sum(item["is_sponsored"] for item in competitors),
            },
        }

    def _rank_movement(
        self, job_id: str, job: dict[str, Any], competitors: list[dict[str, Any]]
    ) -> dict[str, Any]:
        previous_job = self.storage.get_previous_completed_job(job_id, job["niche"])
        if previous_job is None:
            return {
                "available": False,
                "reason": "Run the same niche again later to calculate rank movement.",
                "movements": [],
                "new_gigs": [],
                "removed_gigs": [],
            }
        previous_search = self.storage.get_all_search_results(previous_job["id"])
        previous_details = {
            item["url"]: item for item in self.storage.get_all_job_results(previous_job["id"])
        }
        previous = self._competitors(previous_search, previous_details)
        current_map = {item["url"]: item for item in competitors}
        previous_map = {item["url"]: item for item in previous}
        common = current_map.keys() & previous_map.keys()
        movements = []
        for url in common:
            current = current_map[url]
            old = previous_map[url]
            current_rank = current.get("global_position")
            previous_rank = old.get("global_position")
            if current_rank is None or previous_rank is None:
                continue
            movements.append(
                {
                    "url": url,
                    "title": current.get("title") or old.get("title"),
                    "seller": current.get("seller") or old.get("seller"),
                    "previous_rank": previous_rank,
                    "current_rank": current_rank,
                    "change": previous_rank - current_rank,
                    "previous_price": old.get("price"),
                    "current_price": current.get("price"),
                    "price_change": _rounded(
                        (current.get("price") or 0) - (old.get("price") or 0)
                    ) if current.get("price") is not None and old.get("price") is not None else None,
                    "previous_reviews": old.get("review_count"),
                    "current_reviews": current.get("review_count"),
                    "review_change": (current.get("review_count") or 0) - (old.get("review_count") or 0),
                }
            )
        movements.sort(key=lambda row: (-abs(row["change"]), row["current_rank"]))
        new_gigs = [current_map[url] for url in current_map.keys() - previous_map.keys()]
        removed = [previous_map[url] for url in previous_map.keys() - current_map.keys()]
        return {
            "available": True,
            "previous_job_id": previous_job["id"],
            "previous_created_at": previous_job["created_at"],
            "current_created_at": job["created_at"],
            "common_count": len(common),
            "gainers": sum(row["change"] > 0 for row in movements),
            "decliners": sum(row["change"] < 0 for row in movements),
            "unchanged": sum(row["change"] == 0 for row in movements),
            "movements": movements[:300],
            "new_gigs": sorted(new_gigs, key=lambda row: row.get("global_position") or 999999)[:100],
            "removed_gigs": sorted(removed, key=lambda row: row.get("global_position") or 999999)[:100],
        }

    @staticmethod
    def _keywords(
        documents: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> tuple[dict[str, Any], dict[str, dict[str, set[int]]]]:
        internal: dict[str, dict[str, set[int]]] = {
            "unigrams": defaultdict(set),
            "bigrams": defaultdict(set),
            "trigrams": defaultdict(set),
            "title_starts": defaultdict(set),
            "tags": defaultdict(set),
        }
        for index, (competitor, detail) in enumerate(documents):
            title_tokens = _tokens(competitor.get("title"))
            for token in set(title_tokens):
                internal["unigrams"][token].add(index)
            for phrase in set(_ngrams(title_tokens, 2)):
                internal["bigrams"][phrase].add(index)
            for phrase in set(_ngrams(title_tokens, 3)):
                internal["trigrams"][phrase].add(index)
            if len(title_tokens) >= 2:
                internal["title_starts"][" ".join(title_tokens[:2])].add(index)
            if len(title_tokens) >= 3:
                internal["title_starts"][" ".join(title_tokens[:3])].add(index)
            for tag in detail.get("related_tags") or []:
                cleaned = " ".join(_tokens(str(tag)))
                if cleaned:
                    internal["tags"][cleaned].add(index)

        def rows_for(kind: str, max_rows: int = 120) -> list[dict[str, Any]]:
            rows = []
            for phrase, indexes in internal[kind].items():
                if not indexes:
                    continue
                selected = [documents[index][0] for index in indexes]
                ranks = [item["global_position"] for item in selected if item.get("global_position") is not None]
                prices = [item["price"] for item in selected if item.get("price") is not None]
                ratings = [item["rating"] for item in selected if item.get("rating") is not None]
                reviews = [item["review_count"] for item in selected if item.get("review_count") is not None]
                rows.append(
                    {
                        "phrase": phrase,
                        "gig_count": len(indexes),
                        "share_pct": _rounded(100 * len(indexes) / len(documents), 1) if documents else 0,
                        "top_20_count": sum((rank or 999999) <= 20 for rank in ranks),
                        "average_rank": _rounded(_mean(ranks)),
                        "median_price": numeric_stats(prices)["median"],
                        "average_rating": _rounded(_mean(ratings)),
                        "average_reviews": _rounded(_mean(reviews)),
                    }
                )
            rows.sort(key=lambda row: (-row["gig_count"], row["average_rank"] or 999999, row["phrase"]))
            return rows[:max_rows]

        output = {
            "unigrams": rows_for("unigrams"),
            "bigrams": rows_for("bigrams"),
            "trigrams": rows_for("trigrams"),
            "title_starts": rows_for("title_starts", 80),
            "related_tags": rows_for("tags", 80),
        }
        return output, internal

    @staticmethod
    def _clusters(
        internal: dict[str, dict[str, set[int]]], competitors: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        phrase_gigs: dict[str, set[int]] = {}
        for kind in ("bigrams", "trigrams"):
            for phrase, indexes in internal[kind].items():
                if len(indexes) >= 2:
                    phrase_gigs[phrase] = set(indexes)
        phrases = sorted(phrase_gigs, key=lambda value: (-len(phrase_gigs[value]), value))[:100]
        parent = list(range(len(phrases)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(a: int, b: int) -> None:
            root_a, root_b = find(a), find(b)
            if root_a != root_b:
                parent[root_b] = root_a

        token_sets = [set(phrase.split()) - CLUSTER_GENERIC for phrase in phrases]
        for i in range(len(phrases)):
            for j in range(i + 1, len(phrases)):
                left, right = token_sets[i], token_sets[j]
                if not left or not right:
                    left, right = set(phrases[i].split()), set(phrases[j].split())
                overlap = left & right
                jaccard = len(overlap) / len(left | right) if left | right else 0
                if jaccard >= 0.5 or len(overlap) >= 2:
                    union(i, j)

        groups: dict[int, list[int]] = defaultdict(list)
        for index in range(len(phrases)):
            groups[find(index)].append(index)
        output = []
        for indexes in groups.values():
            if len(indexes) < 2:
                continue
            members = [phrases[index] for index in indexes]
            gig_indexes: set[int] = set()
            token_counter: Counter[str] = Counter()
            for phrase in members:
                gigs = phrase_gigs[phrase]
                gig_indexes.update(gigs)
                for token in set(phrase.split()) - CLUSTER_GENERIC:
                    token_counter[token] += len(gigs)
            if len(gig_indexes) < 2:
                continue
            label_tokens = [token for token, _ in token_counter.most_common(2)]
            label = " ".join(label_tokens).title() if label_tokens else members[0].title()
            selected = [competitors[index] for index in gig_indexes if index < len(competitors)]
            output.append(
                {
                    "cluster": label,
                    "phrases": sorted(members, key=lambda phrase: (-len(phrase_gigs[phrase]), phrase))[:15],
                    "phrase_count": len(members),
                    "gig_count": len(gig_indexes),
                    "share_pct": _rounded(100 * len(gig_indexes) / len(competitors), 1) if competitors else 0,
                    "average_rank": _rounded(_mean(item["global_position"] for item in selected if item.get("global_position") is not None)),
                    "median_price": numeric_stats(item.get("price") for item in selected)["median"],
                }
            )
        output.sort(key=lambda row: (-row["gig_count"], row["cluster"]))
        return output[:40]

    @staticmethod
    def _pricing(
        competitors: list[dict[str, Any]],
        documents: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> dict[str, Any]:
        overall_values = [item["price"] for item in competitors if item.get("price") is not None]
        tier_values: dict[str, list[float]] = defaultdict(list)
        multipliers = []
        for _, detail in documents:
            package_map: dict[str, float] = {}
            for package in detail.get("packages") or []:
                name = str(package.get("name") or "Unknown").title()
                price = _number(package.get("price"))
                if price is not None:
                    tier_values[name].append(price)
                    package_map[name] = price
            if package_map.get("Basic") and package_map.get("Premium"):
                multipliers.append(package_map["Premium"] / package_map["Basic"])

        by_level: dict[str, list[float]] = defaultdict(list)
        by_placement: dict[str, list[float]] = defaultdict(list)
        by_rank: dict[str, list[float]] = defaultdict(list)
        for item in competitors:
            if item.get("price") is None:
                continue
            by_level[item.get("seller_level") or "Unknown"].append(item["price"])
            by_placement["Sponsored" if item.get("is_sponsored") else "Organic"].append(item["price"])
            by_rank[item.get("rank_band") or "Unknown"].append(item["price"])

        stats = numeric_stats(overall_values)
        histogram = []
        if overall_values:
            maximum = max(overall_values)
            width = 10 if maximum <= 100 else 25 if maximum <= 250 else 50 if maximum <= 500 else 100
            upper = max(width, int(math.ceil(maximum / width) * width))
            for start in range(0, upper, width):
                end = start + width
                count = sum(start <= value < end or (end == upper and value == end) for value in overall_values)
                histogram.append({"label": f"${start}–${end}", "min": start, "max": end, "count": count})
        q1, q3 = stats.get("q1"), stats.get("q3")
        outlier_threshold = q3 + 1.5 * (q3 - q1) if q1 is not None and q3 is not None else None
        outliers = [item for item in competitors if outlier_threshold is not None and (item.get("price") or 0) > outlier_threshold]
        return {
            "overall": stats,
            "package_tiers": {name: numeric_stats(values) for name, values in sorted(tier_values.items())},
            "by_seller_level": [
                {"segment": name, **numeric_stats(values)} for name, values in sorted(by_level.items())
            ],
            "by_placement": [
                {"segment": name, **numeric_stats(values)} for name, values in sorted(by_placement.items())
            ],
            "by_rank_band": [
                {"segment": name, **numeric_stats(values)} for name, values in by_rank.items()
            ],
            "premium_to_basic_multiplier": numeric_stats(multipliers),
            "histogram": histogram,
            "outlier_threshold": _rounded(outlier_threshold),
            "outliers": outliers[:50],
        }

    @staticmethod
    def _packages(
        documents: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> tuple[dict[str, Any], dict[str, set[int]]]:
        tier_counts: Counter[str] = Counter()
        deliveries: dict[str, Counter[str]] = defaultdict(Counter)
        revisions: dict[str, Counter[str]] = defaultdict(Counter)
        feature_tier_counts: dict[str, Counter[str]] = defaultdict(Counter)
        feature_gigs: dict[str, set[int]] = defaultdict(set)
        gigs_with_packages = 0
        for index, (_, detail) in enumerate(documents):
            packages = detail.get("packages") or []
            if packages:
                gigs_with_packages += 1
            seen_tiers: set[str] = set()
            for package in packages:
                tier = str(package.get("name") or "Unknown").title()
                if tier not in seen_tiers:
                    tier_counts[tier] += 1
                    seen_tiers.add(tier)
                if package.get("delivery_time"):
                    deliveries[tier][str(package["delivery_time"])] += 1
                if package.get("revisions"):
                    revisions[tier][str(package["revisions"])] += 1
                for feature, value in (package.get("features") or {}).items():
                    normalized = _normalize_feature(str(feature))
                    if not normalized:
                        continue
                    # Blank cells mean the public renderer did not expose a value;
                    # do not incorrectly treat them as confirmed inclusion.
                    if value in (None, "", False):
                        continue
                    feature_tier_counts[normalized][tier] += 1
                    feature_gigs[normalized].add(index)
        feature_rows = []
        for feature, counts in feature_tier_counts.items():
            feature_rows.append(
                {
                    "feature": feature.title(),
                    "gig_count": len(feature_gigs[feature]),
                    "overall_coverage_pct": _rounded(100 * len(feature_gigs[feature]) / gigs_with_packages, 1) if gigs_with_packages else 0,
                    "basic_count": counts.get("Basic", 0),
                    "standard_count": counts.get("Standard", 0),
                    "premium_count": counts.get("Premium", 0),
                }
            )
        feature_rows.sort(key=lambda row: (-row["gig_count"], row["feature"]))
        output = {
            "gigs_with_packages": gigs_with_packages,
            "tier_counts": [{"tier": tier, "count": count} for tier, count in tier_counts.most_common()],
            "delivery_patterns": {
                tier: [{"label": label, "count": count} for label, count in counter.most_common(20)]
                for tier, counter in deliveries.items()
            },
            "revision_patterns": {
                tier: [{"label": label, "count": count} for label, count in counter.most_common(20)]
                for tier, counter in revisions.items()
            },
            "feature_matrix": feature_rows[:100],
        }
        return output, feature_gigs

    @staticmethod
    def _reviews(
        documents: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> tuple[dict[str, Any], dict[str, set[int]]]:
        review_rows: list[dict[str, Any]] = []
        phrase_gigs: dict[str, set[int]] = defaultdict(set)
        phrase_counts: Counter[str] = Counter()
        sentiment = Counter()
        praise = Counter()
        concerns = Counter()
        countries = Counter()
        prices = Counter()
        durations = Counter()
        ongoing = samples = responses = 0
        for gig_index, (_, detail) in enumerate(documents):
            for review in detail.get("visible_reviews") or []:
                review_rows.append(review)
                text = str(review.get("text") or "")
                tokens = _tokens(text)
                positive = sum(token in POSITIVE_WORDS for token in tokens)
                negative = sum(token in NEGATIVE_WORDS for token in tokens)
                label = "positive" if positive > negative else "negative" if negative > positive else "neutral"
                sentiment[label] += 1
                for token in tokens:
                    if token in POSITIVE_WORDS:
                        praise[token] += 1
                    if token in NEGATIVE_WORDS:
                        concerns[token] += 1
                phrases = set(_ngrams(tokens, 2) + _ngrams(tokens, 3))
                for phrase in phrases:
                    phrase_counts[phrase] += 1
                    phrase_gigs[phrase].add(gig_index)
                if review.get("country"):
                    countries[str(review["country"])] += 1
                if review.get("price"):
                    prices[str(review["price"])] += 1
                if review.get("duration"):
                    durations[str(review["duration"])] += 1
                ongoing += int(bool(review.get("ongoing_collaboration")))
                samples += int(bool(review.get("work_sample_url")))
                responses += int(bool(review.get("seller_response")))
        total = len(review_rows)
        top_phrases = [
            {"phrase": phrase, "review_count": count, "gig_count": len(phrase_gigs[phrase])}
            for phrase, count in phrase_counts.most_common(100)
            if count >= 2
        ]
        output = {
            "visible_reviews_analyzed": total,
            "sentiment": [
                {"label": label, "count": sentiment.get(label, 0), "share_pct": _rounded(100 * sentiment.get(label, 0) / total, 1) if total else 0}
                for label in ("positive", "neutral", "negative")
            ],
            "average_visible_rating": _rounded(_mean(_number(row.get("rating")) for row in review_rows if _number(row.get("rating")) is not None)),
            "buyer_countries": [{"label": label, "count": count} for label, count in countries.most_common(30)],
            "price_ranges": [{"label": label, "count": count} for label, count in prices.most_common(30)],
            "durations": [{"label": label, "count": count} for label, count in durations.most_common(30)],
            "ongoing_collaboration_count": ongoing,
            "ongoing_collaboration_share_pct": _rounded(100 * ongoing / total, 1) if total else 0,
            "work_sample_count": samples,
            "work_sample_share_pct": _rounded(100 * samples / total, 1) if total else 0,
            "seller_response_count": responses,
            "seller_response_share_pct": _rounded(100 * responses / total, 1) if total else 0,
            "praise_terms": [{"term": term, "count": count} for term, count in praise.most_common(40)],
            "concern_terms": [{"term": term, "count": count} for term, count in concerns.most_common(40)],
            "top_phrases": top_phrases,
        }
        return output, phrase_gigs

    @staticmethod
    def _gaps(
        keywords: dict[str, Any],
        keyword_internal: dict[str, dict[str, set[int]]],
        competitors: list[dict[str, Any]],
        packages: dict[str, Any],
        package_internal: dict[str, set[int]],
        reviews: dict[str, Any],
        review_internal: dict[str, set[int]],
        pricing: dict[str, Any],
    ) -> dict[str, Any]:
        candidates = keywords.get("bigrams", []) + keywords.get("trigrams", [])
        max_count = max((row["gig_count"] for row in candidates), default=1)
        max_reviews = max((row.get("average_reviews") or 0 for row in candidates), default=1) or 1
        price_reference = pricing.get("overall", {}).get("q3") or pricing.get("overall", {}).get("median") or 1
        opportunities = []
        for row in candidates:
            if row["gig_count"] < 2:
                continue
            presence = math.log1p(row["gig_count"]) / math.log1p(max_count)
            price_strength = min((row.get("median_price") or 0) / price_reference, 1.5) / 1.5
            review_demand = math.log1p(row.get("average_reviews") or 0) / math.log1p(max_reviews)
            top_ratio = row.get("top_20_count", 0) / row["gig_count"]
            competition = min(1.0, 0.55 * presence + 0.25 * top_ratio + 0.20 * review_demand)
            accessibility = 1 - competition
            score = 100 * (
                0.30 * presence
                + 0.25 * price_strength
                + 0.20 * review_demand
                + 0.25 * accessibility
            )
            opportunities.append(
                {
                    **row,
                    "opportunity_score": _rounded(score, 1),
                    "demand_proxy": _rounded(100 * (0.6 * presence + 0.4 * review_demand), 1),
                    "competition_proxy": _rounded(100 * competition, 1),
                    "price_potential": _rounded(100 * price_strength, 1),
                    "evidence": f"{row['gig_count']} gigs; median ${row.get('median_price') or 0}; avg reviews {row.get('average_reviews') or 0}",
                }
            )
        opportunities.sort(key=lambda row: (-row["opportunity_score"], -row["gig_count"], row["phrase"]))

        title_phrases = set(keyword_internal["bigrams"]) | set(keyword_internal["trigrams"])
        review_need_gaps = []
        for phrase, gig_indexes in review_internal.items():
            if len(gig_indexes) < 2 or phrase in title_phrases:
                continue
            review_need_gaps.append(
                {
                    "phrase": phrase,
                    "review_gig_count": len(gig_indexes),
                    "title_gig_count": 0,
                    "gap_type": "Buyer language appears in reviews but not dedicated titles",
                }
            )
        review_need_gaps.sort(key=lambda row: (-row["review_gig_count"], row["phrase"]))

        feature_gaps = []
        total_gigs = max(1, len(competitors))
        for feature, indexes in package_internal.items():
            top10_count = sum((competitors[index].get("global_position") or 999999) <= 10 for index in indexes if index < len(competitors))
            coverage = 100 * len(indexes) / total_gigs
            if top10_count >= 2 and coverage < 35:
                feature_gaps.append(
                    {
                        "feature": feature.title(),
                        "top_10_gig_count": top10_count,
                        "overall_gig_count": len(indexes),
                        "overall_coverage_pct": _rounded(coverage, 1),
                        "gap_type": "Seen in multiple Top-10 offers but uncommon across the sample",
                    }
                )
        feature_gaps.sort(key=lambda row: (-row["top_10_gig_count"], row["overall_coverage_pct"]))
        return {
            "keyword_opportunities": opportunities[:50],
            "review_language_gaps": review_need_gaps[:50],
            "offer_feature_gaps": feature_gaps[:50],
            "formula": {
                "opportunity_score": "30% market presence + 25% price potential + 20% review demand + 25% accessibility",
                "warning": "All components are public-data proxies; this is not Fiverr search volume or an official rank score.",
            },
        }

    @staticmethod
    def export_rows(analysis: dict[str, Any], section: str) -> list[dict[str, Any]]:
        if section == "overview":
            rows: list[dict[str, Any]] = []
            _flatten("", analysis.get("overview") or {}, rows)
            return rows
        if section == "rankings":
            return list((analysis.get("rankings") or {}).get("top_gigs") or [])
        if section == "movement":
            return list((analysis.get("rank_movement") or {}).get("movements") or [])
        if section == "keywords":
            rows = []
            for kind, values in (analysis.get("keywords") or {}).items():
                for item in values:
                    rows.append({"keyword_type": kind, **item})
            return rows
        if section == "clusters":
            return [
                {**row, "phrases": " | ".join(row.get("phrases") or [])}
                for row in analysis.get("keyword_clusters") or []
            ]
        if section == "pricing":
            rows = []
            rows.append({"segment_type": "overall", "segment": "All gigs", **(analysis.get("pricing") or {}).get("overall", {})})
            for group in ("by_seller_level", "by_placement", "by_rank_band"):
                for item in (analysis.get("pricing") or {}).get(group, []):
                    rows.append({"segment_type": group, **item})
            for tier, stats in (analysis.get("pricing") or {}).get("package_tiers", {}).items():
                rows.append({"segment_type": "package_tier", "segment": tier, **stats})
            return rows
        if section == "packages":
            return list((analysis.get("packages") or {}).get("feature_matrix") or [])
        if section == "competitors":
            return list(analysis.get("competitors") or [])
        if section == "reviews":
            return list((analysis.get("reviews") or {}).get("top_phrases") or [])
        if section == "gaps":
            rows = []
            for gap_type, values in (analysis.get("market_gaps") or {}).items():
                if not isinstance(values, list):
                    continue
                for item in values:
                    rows.append({"gap_section": gap_type, **item})
            return rows
        return []
