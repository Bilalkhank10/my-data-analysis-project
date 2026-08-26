import tempfile
import time
import unittest
from pathlib import Path

from market_analyzer import ANALYSIS_VERSION, MarketAnalyzer
from storage import Storage


class AnalysisTests(unittest.TestCase):
    def _add_job(self, storage, job_id, ranks):
        storage.create_job(job_id, "Looker Studio", len(ranks))
        cards = []
        for index, (url, rank, title, price, sponsored) in enumerate(ranks):
            cards.append(
                {
                    "url": url,
                    "niche": "Looker Studio",
                    "page_number": 1,
                    "page_position": rank,
                    "global_position": rank,
                    "organic_position": None if sponsored else rank,
                    "sponsored_position": 1 if sponsored else None,
                    "is_sponsored": sponsored,
                    "seller_online": index % 2 == 0,
                    "card_title": title,
                    "card_seller_name": f"Seller {index}",
                    "card_seller_username": f"seller{index}",
                    "card_seller_level": "Level 2" if index < 2 else "Level 1",
                    "card_rating": 4.8 + index * 0.05,
                    "card_review_count": 20 + index * 20,
                    "card_price": price,
                    "currency": "USD",
                    "badges": ["Level 2" if index < 2 else "Level 1"],
                }
            )
            result = {
                "url": url,
                "fetched_at": "2026-08-21T00:00:00+00:00",
                "fetch_method": "reader",
                "title": title,
                "seller_username": f"seller{index}",
                "seller_name": f"Seller {index}",
                "seller_level": "Level 2" if index < 2 else "Level 1",
                "seller_country": "Pakistan" if index % 2 == 0 else "United States",
                "rating": 4.8 + index * 0.05,
                "review_count": 20 + index * 20,
                "starting_price_usd": price,
                "category_path": ["Data", "Data Dashboards"],
                "about_text": "Interactive marketing analytics and automated reporting.",
                "packages": [
                    {
                        "name": "Basic",
                        "price": price,
                        "delivery_time": "2 days",
                        "revisions": "Unlimited",
                        "features": {"Dashboards": "1"},
                    },
                    {
                        "name": "Premium",
                        "price": price * 4,
                        "delivery_time": "5 days",
                        "revisions": "5",
                        "features": {"Dashboards": "5", "Web embedding": "Yes"},
                    },
                ],
                "faqs": [{"question": "What do you need?", "answer": "Your data."}],
                "visible_reviews": [
                    {
                        "username": "buyer",
                        "country": "Canada",
                        "rating": 5,
                        "relative_date": "1 month ago",
                        "text": "Excellent fast communication and accurate dashboard",
                        "price": "$50-$100",
                        "duration": "3 days",
                        "ongoing_collaboration": index == 0,
                        "work_sample_url": "https://example.test/sample.jpg" if index == 0 else None,
                        "seller_response": "Thank you",
                    }
                ],
                "related_tags": ["data visualization", "looker studio"],
                "has_video": index % 2 == 0,
                "gallery_count": 3,
                "error": None,
                "search": {"global_position": rank},
            }
            storage.save_gig_result(job_id, result)
        storage.save_search_results(job_id, cards)
        storage.update_job(
            job_id,
            status="completed",
            stage="completed",
            available_results=567,
            discovered_count=len(cards),
            processed_count=len(cards),
            success_count=len(cards),
            progress_percent=100,
        )

    def test_market_analysis_without_llm(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory) / "analysis.db")
            rows = [
                ("https://www.fiverr.com/a/looker-marketing-dashboard", 1, "I will build looker studio marketing dashboard", 50, False),
                ("https://www.fiverr.com/b/looker-sales-dashboard", 2, "I will build looker studio sales dashboard", 75, False),
                ("https://www.fiverr.com/c/google-data-report", 3, "I will create google data studio report", 25, True),
                ("https://www.fiverr.com/d/analytics-dashboard", 4, "I will design interactive analytics dashboard", 100, False),
            ]
            self._add_job(storage, "job-current", rows)
            analyzer = MarketAnalyzer(storage)
            analysis = analyzer.analyze("job-current")
            self.assertFalse(analysis["methodology"]["llm_used"])
            self.assertEqual(analysis["overview"]["sampled_gigs"], 4)
            self.assertEqual(analysis["overview"]["sponsored_count"], 1)
            self.assertEqual(analysis["pricing"]["overall"]["median"], 62.5)
            phrases = {row["phrase"] for row in analysis["keywords"]["bigrams"]}
            self.assertIn("looker studio", phrases)
            self.assertGreaterEqual(analysis["packages"]["gigs_with_packages"], 4)
            self.assertEqual(analysis["reviews"]["visible_reviews_analyzed"], 4)
            self.assertTrue(analysis["market_gaps"]["formula"]["warning"])
            storage.save_analysis("job-current", analysis, ANALYSIS_VERSION)
            loaded = storage.get_analysis("job-current", ANALYSIS_VERSION)
            self.assertEqual(loaded["job_id"], "job-current")
            self.assertTrue(MarketAnalyzer.export_rows(loaded, "keywords"))

    def test_rank_movement_uses_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory) / "movement.db")
            shared = "https://www.fiverr.com/a/looker-dashboard"
            self._add_job(
                storage,
                "job-old",
                [(shared, 5, "I will build looker studio dashboard", 50, False)],
            )
            time.sleep(0.002)
            self._add_job(
                storage,
                "job-new",
                [(shared, 2, "I will build looker studio dashboard", 60, False)],
            )
            movement = MarketAnalyzer(storage).analyze("job-new")["rank_movement"]
            self.assertTrue(movement["available"])
            self.assertEqual(movement["movements"][0]["change"], 3)
            self.assertEqual(movement["movements"][0]["price_change"], 10.0)


if __name__ == "__main__":
    unittest.main()
