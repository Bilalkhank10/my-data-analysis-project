import asyncio
import tempfile
import unittest
from pathlib import Path

from ai_analyzer import Phase3Analyzer
from market_analyzer import MarketAnalyzer
from openrouter_client import OpenRouterConfig, Usage
from storage import Storage


class FakeOpenRouterClient:
    def __init__(self):
        self.embedding_calls = 0
        self.chat_calls = 0

    async def embeddings(self, inputs, model=None):
        self.embedding_calls += 1
        vectors = [[1.0, index * 0.1 + 0.01] for index, _ in enumerate(inputs)]
        return vectors, Usage(prompt_tokens=20, total_tokens=20, cost=0.001), "emb-test"

    async def chat_json(
        self, *, messages, schema_name, schema, model=None, max_tokens=None, temperature=0
    ):
        self.chat_calls += 1
        if schema_name == "fiverr_gig_analysis":
            content = messages[-1]["content"]
            urls = []
            for candidate in (
                "https://www.fiverr.com/a/marketing-dashboard",
                "https://www.fiverr.com/b/sales-dashboard",
            ):
                if candidate in content:
                    urls.append(candidate)
            analyses = []
            for index, url in enumerate(urls):
                analyses.append(
                    {
                        "url": url,
                        "title": "Marketing dashboard" if index == 0 else "Sales dashboard",
                        "intent": {
                            "service": "Looker Studio dashboard",
                            "buyer_problem": "Fragmented reporting",
                            "desired_outcome": "Automated visibility",
                            "target_buyer": "Marketing teams",
                            "industry": "Digital marketing",
                            "project_type": "Dashboard implementation",
                            "deliverables": ["Dashboard", "Filters"],
                            "tools": ["Looker Studio", "GA4"],
                        },
                        "scores": {
                            "neo_readiness": 80,
                            "intent_clarity": 82,
                            "conversion_readiness": 75,
                            "trust_proof": 70,
                            "package_consistency": 77,
                            "semantic_differentiation": 60,
                            "high_ticket_readiness": 68,
                            "compliance_risk": 5,
                        },
                        "positioning_archetype": "Technical specialist",
                        "strengths": ["Clear deliverable"],
                        "weaknesses": ["Target industry could be narrower"],
                        "recommendations": ["Add stronger proof"],
                        "evidence": [
                            {
                                "section": "about",
                                "quote": "interactive dashboard",
                                "reason": "Clear service evidence",
                            }
                        ],
                        "confidence": "high",
                    }
                )
            response = {"gig_analyses": analyses}
        else:
            response = {
                "market_summary": "The market is competitive and dashboard-focused.",
                "dominant_intents": ["Automated reporting"],
                "positioning_archetypes": [
                    {
                        "name": "Technical specialist",
                        "gig_count": 2,
                        "description": "Implementation-led positioning",
                    }
                ],
                "semantic_gaps": [
                    {
                        "name": "Retention reporting",
                        "evidence": "Limited dedicated positioning",
                        "opportunity": "Specialized recurring dashboard",
                    }
                ],
                "high_ticket_opportunities": ["Add strategy and QA"],
                "own_gig_audit": {
                    "included": True,
                    "url": "https://www.fiverr.com/a/marketing-dashboard",
                    "strengths": ["Clear service"],
                    "gaps": ["Weak proof"],
                    "priority_actions": ["Add portfolio evidence"],
                },
                "caveats": ["Public data only"],
            }
        return response, Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
        ), "gen-test"


class Phase3Tests(unittest.TestCase):
    def _fixture(self, directory):
        storage = Storage(Path(directory) / "phase3.db")
        job_id = "job-phase3"
        storage.create_job(job_id, "Looker Studio", 2)
        urls = [
            "https://www.fiverr.com/a/marketing-dashboard",
            "https://www.fiverr.com/b/sales-dashboard",
        ]
        cards = []
        for index, url in enumerate(urls, 1):
            cards.append(
                {
                    "url": url,
                    "niche": "Looker Studio",
                    "page_number": 1,
                    "page_position": index,
                    "global_position": index,
                    "organic_position": index,
                    "sponsored_position": None,
                    "is_sponsored": False,
                    "seller_online": True,
                    "card_title": "I will build looker studio marketing dashboard",
                    "card_seller_name": f"Seller {index}",
                    "card_seller_username": "a" if index == 1 else "b",
                    "card_seller_level": "Level 2",
                    "card_rating": 5.0,
                    "card_review_count": 50,
                    "card_price": 50 * index,
                    "currency": "USD",
                    "badges": ["Level 2"],
                }
            )
            storage.save_gig_result(
                job_id,
                {
                    "url": url,
                    "fetched_at": "2026-08-21T00:00:00+00:00",
                    "fetch_method": "reader",
                    "title": "I will build looker studio marketing dashboard",
                    "seller_username": "a" if index == 1 else "b",
                    "seller_name": f"Seller {index}",
                    "seller_level": "Level 2",
                    "seller_country": "Pakistan",
                    "rating": 5.0,
                    "review_count": 50,
                    "starting_price_usd": 50 * index,
                    "about_text": "I create an interactive dashboard for automated reporting.",
                    "packages": [
                        {
                            "name": "Basic",
                            "price": 50 * index,
                            "description": "One dashboard",
                            "delivery_time": "2 days",
                            "revisions": "2",
                            "features": {"Filters": "Yes"},
                        }
                    ],
                    "faqs": [],
                    "visible_reviews": [
                        {
                            "text": "Excellent fast dashboard and communication",
                            "rating": 5,
                            "country": "Canada",
                        }
                    ],
                    "related_tags": ["looker studio"],
                    "gallery_count": 2,
                    "has_video": False,
                    "error": None,
                    "search": {"global_position": index},
                },
            )
        storage.save_search_results(job_id, cards)
        storage.update_job(
            job_id,
            status="completed",
            stage="completed",
            available_results=100,
            discovered_count=2,
            processed_count=2,
            success_count=2,
            progress_percent=100,
        )
        phase2 = MarketAnalyzer(storage).analyze(job_id)
        storage.save_analysis(job_id, phase2)
        return storage, job_id, urls

    def test_dry_run_consumes_no_api(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, urls = self._fixture(directory)
            config = OpenRouterConfig(api_key="", max_gigs=2, max_cost_usd=1)
            analyzer = Phase3Analyzer(storage, config=config)
            plan = analyzer.dry_run_plan(
                job_id, max_gigs=2, mode="standard", own_gig_url=urls[0]
            )
            self.assertTrue(plan["dry_run"])
            self.assertEqual(plan["selected_gigs"], 2)
            self.assertIn("No OpenRouter request", plan["note"])

    def test_mocked_phase3_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, urls = self._fixture(directory)
            config = OpenRouterConfig(
                api_key="sk-or-test-placeholder",
                max_gigs=2,
                max_cost_usd=1,
                max_output_tokens=800,
            )
            fake = FakeOpenRouterClient()
            analyzer = Phase3Analyzer(storage, config=config, client=fake)

            async def run_once(run_id):
                return await analyzer.analyze(
                    run_id,
                    job_id,
                    max_gigs=2,
                    mode="standard",
                    own_gig_url=urls[0],
                )

            first = asyncio.run(run_once("run-1"))
            self.assertTrue(first["methodology"]["llm_used"])
            self.assertTrue(first["methodology"]["embeddings_used"])
            self.assertEqual(len(first["gig_analyses"]), 2)
            self.assertEqual(first["gig_analyses"][0]["scores"]["neo_readiness"], 80)
            self.assertTrue(first["semantic_similarity"]["most_similar_pairs"])
            self.assertEqual(first["market_synthesis"]["own_gig_audit"]["included"], True)
            calls_after_first = (fake.embedding_calls, fake.chat_calls)

            second = asyncio.run(run_once("run-2"))
            self.assertEqual((fake.embedding_calls, fake.chat_calls), calls_after_first)
            self.assertGreaterEqual(second["usage"]["cache_hits"], 3)


if __name__ == "__main__":
    unittest.main()
