"""Public Fiverr listing metadata used to tune GigCraft.

Sources are Fiverr help-center ranking language (relevance, performance,
satisfaction, responsiveness, pricing, personalization) plus 2026 field
limits verified against live gig forms. Private CTR/CR/Success Score
internals are not available and are not claimed here.
"""

from __future__ import annotations

from typing import Any

# Hard limits on the gig create/edit form.
TITLE_MAX = 80
TITLE_PREFIX = "I will "
TITLE_PREFIX_LEN = len(TITLE_PREFIX)
TITLE_OWN_MAX = TITLE_MAX - TITLE_PREFIX_LEN  # 74
TITLE_CARD_DESKTOP = 59
TITLE_CARD_MOBILE = 45
TITLE_MIN_USEFUL = 24

DESCRIPTION_MAX = 1200
DESCRIPTION_MIN_USEFUL = 300
DESCRIPTION_CARD_PREVIEW = 110

PACKAGE_DESCRIPTION_MAX = 100
TAG_MAX_CHARS = 20
TAG_COUNT = 5

FAQ_QUESTION_MAX = 70
FAQ_ANSWER_MAX = 300
FAQ_MIN_USEFUL = 5
FAQ_MAX = 10

BUYER_REQUIREMENT_MAX = 200
PROFILE_BIO_MAX = 600

FIELD_LIMITS: dict[str, Any] = {
    "title_max": TITLE_MAX,
    "title_prefix": TITLE_PREFIX.strip(),
    "title_own_max": TITLE_OWN_MAX,
    "title_card_desktop": TITLE_CARD_DESKTOP,
    "title_card_mobile": TITLE_CARD_MOBILE,
    "description_max": DESCRIPTION_MAX,
    "description_card_preview": DESCRIPTION_CARD_PREVIEW,
    "package_description_max": PACKAGE_DESCRIPTION_MAX,
    "tag_max_chars": TAG_MAX_CHARS,
    "tag_count": TAG_COUNT,
    "faq_question_max": FAQ_QUESTION_MAX,
    "faq_answer_max": FAQ_ANSWER_MAX,
    "faq_max": FAQ_MAX,
    "buyer_requirement_max": BUYER_REQUIREMENT_MAX,
}

# What Fiverr says publicly that search uses vs what GigCraft can observe.
PUBLIC_RANK_SIGNALS = {
    "relevance_metadata": "Title, tags, description, category, subcategory, service type, gig metadata.",
    "historical_attractiveness": "Private (impressions/CTR). Proxy: rank, video, thumbnail, title card length.",
    "satisfaction": "Public rating + review count. Private reviews are not available.",
    "responsiveness": "Public 'Avg. response time' when shown.",
    "pricing": "Public starting price and package ladder.",
    "personalization": "Buyer-specific; not observable from a public crawl.",
}


def normalize_title(title: str) -> str:
    value = " ".join((title or "").split()).strip()
    if value.lower().startswith("i will "):
        return value
    if value:
        return TITLE_PREFIX + value[0].lower() + value[1:] if value[0].isupper() else TITLE_PREFIX + value
    return value


def title_own_text(title: str) -> str:
    value = " ".join((title or "").split()).strip()
    if value.lower().startswith("i will "):
        return value[TITLE_PREFIX_LEN:]
    return value


def listing_quality(gig: dict[str, Any]) -> dict[str, Any]:
    """Score how complete a public gig listing is — not a Fiverr Success Score."""
    title = str(gig.get("title") or "")
    about = str(gig.get("about_text") or "")
    tags = [str(tag).strip() for tag in gig.get("related_tags") or [] if str(tag).strip()]
    packages = gig.get("packages") or []
    faqs = gig.get("faqs") or []
    own = title_own_text(title)
    checks = {
        "title_in_card_window": 1 <= len(title) <= TITLE_CARD_DESKTOP,
        "description_present": len(about) >= DESCRIPTION_MIN_USEFUL,
        "three_packages": len(packages) >= 3,
        "faq_depth": len(faqs) >= FAQ_MIN_USEFUL,
        "has_video": bool(gig.get("has_video")),
        "has_gallery": int(gig.get("gallery_count") or 0) >= 3,
        "has_rating": gig.get("rating") is not None,
        "tag_signal": len(tags) >= 3,
    }
    score = round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 1)
    return {
        "score": score,
        "title_chars": len(title),
        "title_own_chars": len(own),
        "description_chars": len(about),
        "tag_count": len(tags),
        "package_count": len(packages),
        "faq_count": len(faqs),
        "checks": checks,
    }
