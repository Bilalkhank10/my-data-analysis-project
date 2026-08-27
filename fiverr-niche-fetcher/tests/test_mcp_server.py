"""Tests for the MCP server tool layer.

Network access is mocked by replacing ``FiverrNicheFetcher._get_text`` with
canned reader-markdown responses, so these tests never touch Fiverr or
r.jina.ai and consume no tokens.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("REQUEST_DELAY_SECONDS", "0")
os.environ.setdefault("SEARCH_PAGE_DELAY_SECONDS", "0")
os.environ.setdefault("MAX_CONCURRENCY", "2")

import mcp_server  # noqa: E402
from fiverr_fetcher import FiverrNicheFetcher  # noqa: E402

SEARCH_MARKDOWN = """
567 results

[![Image 1: create a looker studio dashboard](https://fiverr-res.cloudinary.com/t_gig_cards_web/gigs/1.jpg)](http://www.fiverr.com/alpha/create-looker-dashboard?context_referrer=search_gigs&pos=1&seller_online=true)

[Alpha Seller](http://www.fiverr.com/alpha?source=gig_cards)
Top Rated
[I will create a looker studio dashboard](http://www.fiverr.com/alpha/create-looker-dashboard?context_referrer=search_gigs&pos=1)
**5.0**(120)
[From$50](http://www.fiverr.com/alpha/create-looker-dashboard?context_referrer=search_gigs&pos=1)

[![Image 2: fix data studio reports](https://fiverr-res.cloudinary.com/t_gig_cards_web/gigs/2.jpg)](http://www.fiverr.com/beta/fix-data-studio?context_referrer=search_gigs&pos=2)

[Beta Seller](http://www.fiverr.com/beta?source=gig_cards)
Ad
Level 2
[I will fix data studio reports](http://www.fiverr.com/beta/fix-data-studio?context_referrer=search_gigs&pos=2)
**4.9**(42)
[From$25](http://www.fiverr.com/beta/fix-data-studio?context_referrer=search_gigs&pos=2)
"""

GIG_MARKDOWN = """
[Data Visualization](https://www.fiverr.com/categories/graphics-design/data-visualization?source=gig_page)

# I will create a looker studio dashboard for your business

Get to know Alpha Seller

From
Pakistan

Member since
Jan 2020

Avg. response time
1 hour

Last delivery
2 days

**4.9**(169)

About this gig

I create interactive Looker Studio dashboards with GA4 and Search Console data.

## Compare packages
Prices are before service fees.

| Package | $30 **Basic** | $80 **Standard** | $200 **Premium** |
| --- | --- | --- | --- |
|  | One dashboard | Two dashboards | Full reporting suite |
| Dashboards | 1 | 2 | 5 |
| Revisions | Unlimited | 3 | 5 |
| Delivery Time | 2 days | 3 days | 5 days |
| Total | $30 Select | $80 Select | $200 Select |

## Frequently Asked Questions

### What data sources do you support?
GA4, Search Console, and Google Sheets.

### Can you migrate Data Studio reports?
Yes, migration is included in Standard and Premium.

## 169 reviews for this Gig

**4.9**

5 Stars(165)
4 Stars(4)
3 Stars(0)
2 Stars(0)
1 Star(0)

*   Seller communication level **4.9**
*   Quality of delivery **5.0**

- [x] Only show reviews with files (2)

*   B buyer1 ![Image 1: US](https://fiverr-dev-res.cloudinary.com/general_assets/flags/us.png)
United States **5**
1 month ago Excellent dashboard and proactive communication. $50-$100

Price 3 days Duration
Seller's Response Thank you for the collaboration Helpful? Yes No

## Related tags

Data visualization
Looker Studio
GA4 reporting
"""


async def fake_get_text(self, client, url):
    if "search/gigs" in url:
        return SEARCH_MARKDOWN
    return GIG_MARKDOWN


class TrimFunctionTests(unittest.TestCase):
    def test_search_trim_drops_raw_card_text(self):
        record = {"url": "u", "card_title": "t", "raw_card_text": "x" * 100}
        trimmed = mcp_server.trim_search_record(record)
        self.assertNotIn("raw_card_text", trimmed)
        self.assertEqual(trimmed["card_title"], "t")
        kept = mcp_server.trim_search_record(record, include_raw=True)
        self.assertIn("raw_card_text", kept)

    def test_gig_trim_drops_heavy_fields_and_caps_reviews(self):
        gig = {
            "title": "t",
            "raw_visible_text": "x" * 500,
            "json_ld": [{"a": 1}],
            "packages_text": "p",
            "about_text": "y" * (mcp_server.ABOUT_TEXT_CAP + 50),
            "media_urls": [f"https://cdn/{i}.jpg" for i in range(20)],
            "visible_reviews": [{"text": f"r{i}"} for i in range(40)],
            "error": None,
        }
        trimmed = mcp_server.trim_gig_record(gig, include_reviews=3)
        for field in mcp_server.GIG_HEAVY_FIELDS:
            self.assertNotIn(field, trimmed)
        self.assertTrue(trimmed["about_text"].endswith("[truncated]"))
        self.assertEqual(len(trimmed["media_urls"]), mcp_server.MEDIA_URL_CAP)
        self.assertEqual(len(trimmed["visible_reviews"]), 3)
        full = mcp_server.trim_gig_record(gig, include_raw=True)
        self.assertIn("raw_visible_text", full)


class McpSearchToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_returns_ranked_cards(self):
        with mock.patch.object(FiverrNicheFetcher, "_get_text", fake_get_text):
            result = await mcp_server._fiverr_search("Looker Studio", limit=5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["available_results"], 567)
        first, second = result["results"]
        self.assertEqual(first["global_position"], 1)
        self.assertEqual(first["card_seller_name"], "Alpha Seller")
        self.assertNotIn("raw_card_text", first)
        self.assertTrue(second["is_sponsored"])
        self.assertEqual(second["sponsored_position"], 1)

    async def test_search_include_raw(self):
        with mock.patch.object(FiverrNicheFetcher, "_get_text", fake_get_text):
            result = await mcp_server._fiverr_search("Looker Studio", limit=2, include_raw=True)
        self.assertTrue(result["ok"])
        self.assertIn("raw_card_text", result["results"][0])

    async def test_search_rejects_blank_niche_without_network(self):
        result = await mcp_server._fiverr_search("   ", limit=5)
        self.assertFalse(result["ok"])
        self.assertIn("2 characters", result["error"])

    async def test_search_surfaces_fetch_errors(self):
        async def boom(self, client, url):
            raise ConnectionError("network down")

        with mock.patch.object(FiverrNicheFetcher, "_get_text", boom):
            result = await mcp_server._fiverr_search("logo design", limit=3)
        self.assertFalse(result["ok"])
        self.assertIn("network down", result["error"])


class McpGigToolTests(unittest.IsolatedAsyncioTestCase):
    GIG_URL = "https://www.fiverr.com/alpha/create-looker-dashboard"

    async def test_gig_returns_detail_record(self):
        with mock.patch.object(FiverrNicheFetcher, "_get_text", fake_get_text):
            result = await mcp_server._fiverr_gig(self.GIG_URL)
        self.assertTrue(result["ok"])
        gig = result["gig"]
        self.assertEqual(gig["seller_username"], "alpha")
        self.assertTrue(gig["title"].lower().startswith("i will create a looker studio"))
        self.assertEqual(gig["rating"], 4.9)
        self.assertEqual(gig["review_count"], 169)
        self.assertEqual(gig["starting_price_usd"], 30.0)
        self.assertEqual(len(gig["packages"]), 3)
        self.assertEqual(len(gig["faqs"]), 2)
        self.assertEqual(gig["review_summary"]["total_reviews"], 169)
        self.assertIn("Data Visualization", gig["category_path"])
        self.assertNotIn("raw_visible_text", gig)
        self.assertNotIn("json_ld", gig)

    async def test_gig_review_cap_is_respected(self):
        with mock.patch.object(FiverrNicheFetcher, "_get_text", fake_get_text):
            none_result = await mcp_server._fiverr_gig(self.GIG_URL, include_reviews=0)
            one_result = await mcp_server._fiverr_gig(self.GIG_URL, include_reviews=1)
        self.assertEqual(none_result["gig"]["visible_reviews"], [])
        reviews = one_result["gig"]["visible_reviews"]
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["username"], "buyer1")
        self.assertEqual(reviews[0]["country_code"], "US")

    async def test_gig_rejects_non_gig_urls_without_network(self):
        for bad in (
            "not-a-url",
            "https://example.com/alpha/gig",
            "https://www.fiverr.com/support/article",
        ):
            result = await mcp_server._fiverr_gig(bad)
            self.assertFalse(result["ok"], bad)
            self.assertIn("public Fiverr gig URL", result["error"])

    async def test_listing_quality_scores_the_gig(self):
        with mock.patch.object(FiverrNicheFetcher, "_get_text", fake_get_text):
            result = await mcp_server._fiverr_listing_quality(self.GIG_URL)
        self.assertTrue(result["ok"])
        quality = result["quality"]
        self.assertGreaterEqual(quality["score"], 50.0)
        self.assertTrue(quality["checks"]["has_rating"])
        self.assertTrue(quality["checks"]["three_packages"])
        self.assertIn("Success Score", result["explanation"])


class McpCrawlToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_crawl_combines_search_and_detail(self):
        with mock.patch.object(FiverrNicheFetcher, "_get_text", fake_get_text):
            result = await mcp_server._fiverr_crawl("Looker Studio", limit=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["discovered_count"], 2)
        self.assertEqual(result["success_count"], 2)
        results = result["results"]
        self.assertEqual(len(results), 2)
        first = results[0]
        self.assertEqual(first["search"]["global_position"], 1)
        self.assertEqual(first["search"]["card_seller_name"], "Alpha Seller")
        self.assertEqual(first["seller_username"], "alpha")
        self.assertEqual(len(first["packages"]), 3)
        self.assertNotIn("raw_visible_text", first)
        self.assertNotIn("raw_card_text", first["search"])
        sponsored = results[1]
        self.assertTrue(sponsored["search"]["is_sponsored"])

    async def test_crawl_rejects_blank_niche_without_network(self):
        result = await mcp_server._fiverr_crawl("", limit=2)
        self.assertFalse(result["ok"])


class McpStaticToolTests(unittest.TestCase):
    def test_field_limits(self):
        result = mcp_server._fiverr_field_limits()
        self.assertTrue(result["ok"])
        self.assertEqual(result["field_limits"]["tag_count"], 5)
        self.assertIn("relevance_metadata", result["public_rank_signals"])
        self.assertIn("not observable", result["disclaimer"])

    def test_tools_registered(self):
        if mcp_server.mcp is None:
            self.skipTest("mcp package not installed")
        manager = getattr(mcp_server.mcp, "_tool_manager", None)
        if manager is None:
            self.skipTest("tool manager not introspectable in this mcp version")
        registered = {tool.name for tool in manager.list_tools()}
        self.assertEqual(registered, set(mcp_server.TOOL_NAMES))


if __name__ == "__main__":
    unittest.main()
