"""Offline sample market used when the public reader cannot be reached."""

from __future__ import annotations

import re
from typing import Any

from fiverr_fetcher import SearchResultRecord, utc_now

_LEVELS = ["Top Rated", "Level 2", "Level 2", "Level 1", "Vetted Pro", "Level 1"]
_COUNTRIES = ["Pakistan", "United States", "India", "Ukraine", "United Kingdom", "Canada"]
_PRICES = [25, 40, 50, 75, 90, 120, 35, 60, 150, 45, 80, 200]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "service")[:40]


def sample_warning() -> str:
    return (
        "Live Fiverr crawl is unavailable from this host (HTTPS/TLS is blocked). "
        "GigCraft loaded a bundled sample market so you can keep working. "
        "On your own computer with internet access, crawls use live public pages."
    )


def build_sample_market(niche: str, limit: int) -> tuple[list[SearchResultRecord], list[dict[str, Any]]]:
    niche = " ".join(niche.split()).strip() or "Looker Studio"
    limit = max(1, min(50, int(limit)))
    slug = _slug(niche)
    records: list[SearchResultRecord] = []
    results: list[dict[str, Any]] = []
    now = utc_now()
    templates = [
        ("marketing dashboard", "I will build a {niche} marketing dashboard"),
        ("sales report", "I will create a {niche} sales report"),
        ("ga4 dashboard", "I will connect GA4 to a {niche} dashboard"),
        ("executive report", "I will design an executive {niche} report"),
        ("automated reporting", "I will automate {niche} reporting"),
        ("interactive dashboard", "I will design an interactive {niche} dashboard"),
        ("ecommerce analytics", "I will build ecommerce {niche} analytics"),
        ("data studio fix", "I will fix and improve your {niche} file"),
        ("kpi dashboard", "I will create a KPI {niche} dashboard"),
        ("white label report", "I will deliver white-label {niche} reports"),
        ("real time dashboard", "I will build a real-time {niche} dashboard"),
        ("agency reporting", "I will set up agency {niche} reporting"),
    ]
    for index, (handle, title_tmpl) in enumerate(templates[:limit], start=1):
        username = f"sample{index}"
        title = title_tmpl.format(niche=niche)
        url = f"https://www.fiverr.com/{username}/{slug}-{handle.replace(' ', '-')}"
        price = float(_PRICES[(index - 1) % len(_PRICES)])
        sponsored = index == 3
        level = _LEVELS[(index - 1) % len(_LEVELS)]
        country = _COUNTRIES[(index - 1) % len(_COUNTRIES)]
        rating = round(4.7 + (index % 4) * 0.1, 1)
        reviews = 12 * index + 8
        record = SearchResultRecord(
            url=url,
            niche=niche,
            page_number=1,
            page_position=index,
            global_position=index,
            organic_position=None if sponsored else index,
            sponsored_position=1 if sponsored else None,
            is_sponsored=sponsored,
            seller_online=index % 2 == 1,
            card_title=title,
            card_seller_name=f"Sample Seller {index}",
            card_seller_username=username,
            card_seller_level=level,
            card_rating=rating,
            card_review_count=reviews,
            card_price=price,
            currency="USD",
            badges=[level],
            raw_card_text=title,
            discovered_at=now,
        )
        records.append(record)
        result = {
            "url": url,
            "fetched_at": now,
            "fetch_method": "sample",
            "title": title,
            "seller_username": username,
            "seller_name": f"Sample Seller {index}",
            "seller_level": level,
            "seller_country": country,
            "member_since": "Mar 2021",
            "average_response_time": "1 hour",
            "last_delivery": "2 days",
            "rating": rating,
            "review_count": reviews,
            "starting_price_usd": price,
            "currency": "USD",
            "hourly_rate_usd": None,
            "category_path": ["Data", "Data Visualization"],
            "meta_description": f"Professional {niche} service.",
            "about_text": (
                f"I build clear {niche} deliverables for marketing and operations teams. "
                "The work includes source connection, KPI mapping, filters, and a short walkthrough."
            ),
            "packages": [
                {
                    "name": "Basic",
                    "price": price,
                    "currency": "USD",
                    "description": "One focused dashboard",
                    "delivery_time": "2 days",
                    "revisions": "2",
                    "features": {"Dashboards": "1", "Filters": "Yes"},
                },
                {
                    "name": "Standard",
                    "price": round(price * 2.2, 2),
                    "currency": "USD",
                    "description": "Multi-page reporting with QA",
                    "delivery_time": "4 days",
                    "revisions": "3",
                    "features": {"Dashboards": "3", "Filters": "Yes", "Documentation": "Yes"},
                },
                {
                    "name": "Premium",
                    "price": round(price * 4.0, 2),
                    "currency": "USD",
                    "description": "Full reporting system with training",
                    "delivery_time": "7 days",
                    "revisions": "Unlimited",
                    "features": {"Dashboards": "5", "Web embedding": "Yes", "Training": "Yes"},
                },
            ],
            "faqs": [
                {
                    "question": "What do you need to start?",
                    "answer": "Access to the data source, the KPIs that matter, and any brand references.",
                },
                {
                    "question": "Can you work with my existing file?",
                    "answer": "Yes. Share the current file and I will rebuild or repair it.",
                },
            ],
            "visible_reviews": [
                {
                    "username": "buyer",
                    "country": "Canada",
                    "rating": 5,
                    "relative_date": "1 month ago",
                    "text": "Excellent fast communication and an accurate dashboard.",
                    "price": f"${int(price)}-${int(price * 2)}",
                    "duration": "3 days",
                    "ongoing_collaboration": index == 1,
                    "work_sample_url": None,
                    "seller_response": "Thank you",
                }
            ],
            "related_tags": [niche.lower(), "data visualization", "reporting", "dashboard"],
            "gallery_count": 3 + (index % 3),
            "has_video": index % 2 == 1,
            "error": None,
            "search": record.to_dict(),
        }
        results.append(result)
    return records, results
