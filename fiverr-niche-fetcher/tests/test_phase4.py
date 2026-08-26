import asyncio
import tempfile
import unittest
from pathlib import Path

from generation_manager import GenerationManager
from gig_builder import GigBuilder, generation_markdown, validate_generated_gig
from market_analyzer import MarketAnalyzer
from openrouter_client import NoCompatibleEndpoint, OpenRouterConfig, OpenRouterError, Usage
from storage import Storage


def valid_generation():
    description = (
        "Turn scattered marketing data into a clear interactive dashboard for faster decisions. "
        "I connect your approved data sources, organize the key metrics, build useful filters, "
        "and deliver a documented Looker Studio report designed around your business questions. "
        "Before ordering, share your goals, data sources, required KPIs, brand references, and deadline. "
        "Custom tracking fixes, paid connectors, and major source cleanup are quoted separately. "
        "Message me with your project context so we can confirm the right scope before work begins."
    )
    packages = []
    for name, price, days in [("Basic", 50, 2), ("Standard", 120, 4), ("Premium", 250, 7)]:
        packages.append(
            {
                "name": name,
                "price_usd": price,
                "description": f"{name} dashboard outcome",
                "delivery_days": days,
                "revisions": "2",
                "ideal_for": "Marketing teams",
                "deliverables": ["Interactive dashboard", "Filters"],
                "features": ["Data connection", "QA"],
            }
        )
    return {
        "strategy_summary": "Position around reliable marketing reporting.",
        "positioning_options": [
            {
                "name": f"Option {index}",
                "target_buyer": "Marketing teams",
                "value_proposition": "Clear reporting",
                "differentiator": "Documented QA",
            }
            for index in range(1, 4)
        ],
        "recommended_gig": {
            "title": "I will build a Looker Studio marketing dashboard",
            "tags": ["looker studio", "marketing dashboard", "ga4 report", "data visualization", "google sheets"],
            "category": "Data",
            "subcategory": "Data Visualization",
            "service_type": "Data Dashboards",
            "description": description,
            "packages": packages,
            "faqs": [
                {"question": f"Question {index}?", "answer": "A clear scoped answer."}
                for index in range(1, 6)
            ],
            "buyer_requirements": ["Data access", "KPI list"],
            "scope_exclusions": ["Paid connector fees", "Unapproved tracking changes"],
            "cta": "Message me with your goals and data sources before ordering.",
        },
        "visual_system": {
            "thumbnail_headline": "Clear Marketing Dashboard",
            "thumbnail_subheadline": "Looker Studio reporting",
            "gallery_briefs": [
                {
                    "image_number": index,
                    "purpose": "Proof",
                    "headline": f"Image {index}",
                    "content": "Show a clear dashboard output.",
                    "visual_direction": "High contrast and readable.",
                }
                for index in range(1, 4)
            ],
            "video_script": {
                "hook": "Stop manual reporting.",
                "problem": "Your data is scattered.",
                "solution": "Use one clear dashboard.",
                "proof": "Show relevant work samples.",
                "cta": "Message me with your requirements.",
            },
        },
        "evidence_basis": {
            "keywords_used": ["looker studio", "marketing dashboard"],
            "buyer_needs_used": ["clear reporting"],
            "pricing_basis": "Market median and package percentiles",
            "market_gaps_used": ["Documented QA"],
            "differentiation_reason": "Outcome and QA positioning",
        },
        "model_compliance_check": {
            "risk_level": "low",
            "flags": [],
            "notes": ["Human review required"],
        },
    }


class FakeGenerationClient:
    def __init__(self):
        self.calls = 0

    async def chat_json(self, **kwargs):
        self.calls += 1
        return valid_generation(), Usage(
            prompt_tokens=120,
            completion_tokens=100,
            total_tokens=220,
            cost=0.003,
        ), f"gen-{self.calls}"


class FakeDeepFallbackClient(FakeGenerationClient):
    def __init__(self, deep_model):
        super().__init__()
        self.deep_model = deep_model
        self.models = []

    async def chat_json(self, **kwargs):
        model = kwargs.get("model")
        self.models.append(model)
        if model == self.deep_model:
            raise NoCompatibleEndpoint("No endpoints found")
        return await super().chat_json(**kwargs)


class Phase4Tests(unittest.TestCase):
    def _fixture(self, directory):
        storage = Storage(Path(directory) / "phase4.db")
        job_id = "job-phase4"
        url = "https://www.fiverr.com/a/marketing-dashboard"
        storage.create_job(job_id, "Looker Studio", 1)
        storage.save_search_results(
            job_id,
            [
                {
                    "url": url,
                    "niche": "Looker Studio",
                    "page_number": 1,
                    "page_position": 1,
                    "global_position": 1,
                    "organic_position": 1,
                    "sponsored_position": None,
                    "is_sponsored": False,
                    "seller_online": True,
                    "card_title": "I will build looker studio marketing dashboard",
                    "card_seller_name": "Seller",
                    "card_seller_username": "a",
                    "card_seller_level": "Level 2",
                    "card_rating": 5,
                    "card_review_count": 50,
                    "card_price": 50,
                    "currency": "USD",
                    "badges": ["Level 2"],
                }
            ],
        )
        storage.save_gig_result(
            job_id,
            {
                "url": url,
                "fetched_at": "2026-08-21T00:00:00+00:00",
                "fetch_method": "reader",
                "title": "I will build looker studio marketing dashboard",
                "seller_username": "a",
                "seller_name": "Seller",
                "seller_level": "Level 2",
                "seller_country": "Pakistan",
                "rating": 5,
                "review_count": 50,
                "starting_price_usd": 50,
                "about_text": "I create an interactive dashboard for marketing reporting.",
                "packages": [
                    {
                        "name": "Basic",
                        "price": 50,
                        "description": "One dashboard",
                        "delivery_time": "2 days",
                        "revisions": "2",
                        "features": {"Filters": "Yes"},
                    }
                ],
                "faqs": [],
                "visible_reviews": [{"text": "Excellent clear dashboard", "rating": 5}],
                "related_tags": ["looker studio"],
                "gallery_count": 2,
                "has_video": False,
                "error": None,
                "search": {"global_position": 1},
            },
        )
        storage.update_job(
            job_id,
            status="completed",
            stage="completed",
            available_results=100,
            discovered_count=1,
            processed_count=1,
            success_count=1,
            progress_percent=100,
        )
        phase2 = MarketAnalyzer(storage).analyze(job_id)
        storage.save_analysis(job_id, phase2)
        return storage, job_id, url

    def test_deterministic_validation_and_markdown(self):
        result = valid_generation()
        validation = validate_generated_gig(result)
        self.assertTrue(validation["passed"])
        result["recommended_gig"]["description"] += " Contact me on WhatsApp +1 555 555 5555"
        unsafe = validate_generated_gig(result)
        self.assertFalse(unsafe["passed"])
        wrapper = {"final": valid_generation(), "validation": validation}
        markdown = generation_markdown(wrapper)
        self.assertIn("# Fiverr Gig Draft", markdown)
        self.assertIn("## Packages", markdown)
        self.assertIn("Human approval required", markdown)

    def test_dry_run_no_key(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, url = self._fixture(directory)
            builder = GigBuilder(storage, config=OpenRouterConfig(api_key="", max_cost_usd=1))
            plan = builder.dry_run_plan(
                job_id,
                mode="standard",
                target_gig_url=url,
                preferences={"target_buyer": "Marketing teams"},
            )
            self.assertTrue(plan["dry_run"])
            self.assertTrue(plan["target_found"])
            self.assertIn("No OpenRouter request", plan["note"])

    def test_mocked_generation_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, url = self._fixture(directory)
            config = OpenRouterConfig(
                api_key="sk-or-test-placeholder",
                max_cost_usd=1,
                max_output_tokens=1800,
            )
            fake = FakeGenerationClient()
            builder = GigBuilder(storage, config=config, client=fake)

            async def run(run_id):
                return await builder.generate(
                    run_id,
                    job_id,
                    mode="standard",
                    target_gig_url=url,
                    preferences={
                        "target_buyer": "Marketing teams",
                        "positioning_goal": "Reliable reporting specialist",
                        "tone": "professional",
                        "output_language": "English",
                        "pricing_preference": "market_aligned",
                    },
                )

            first = asyncio.run(run("gen-1"))
            self.assertTrue(first["validation"]["passed"])
            self.assertEqual(len(first["final"]["recommended_gig"]["tags"]), 5)
            self.assertEqual(fake.calls, 1)
            second = asyncio.run(run("gen-2"))
            self.assertEqual(fake.calls, 1)
            self.assertGreaterEqual(second["usage"]["cache_hits"], 1)

    def test_deep_model_endpoint_falls_back_to_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, url = self._fixture(directory)
            config = OpenRouterConfig(
                api_key="sk-or-test-placeholder",
                primary_model="google/gemini-3.7-flash",
                deep_model="anthropic/unavailable-deep-model",
                max_cost_usd=1,
                max_output_tokens=1800,
            )
            fake = FakeDeepFallbackClient(config.deep_model)
            builder = GigBuilder(storage, config=config, client=fake)

            async def run():
                return await builder.generate(
                    "deep-fallback",
                    job_id,
                    mode="deep",
                    target_gig_url=url,
                    preferences={"target_buyer": "Marketing teams"},
                )

            result = asyncio.run(run())
            self.assertEqual(result["models"]["actual_refinement"], config.primary_model)
            self.assertTrue(result["warnings"])
            self.assertIn(config.deep_model, fake.models)
            self.assertGreaterEqual(fake.models.count(config.primary_model), 2)

    def test_draft_falls_back_when_primary_has_no_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, url = self._fixture(directory)
            config = OpenRouterConfig(
                api_key="sk-or-test-placeholder",
                primary_model="google/unavailable-primary",
                deep_model="anthropic/claude-sonnet-5",
                max_cost_usd=1,
                max_output_tokens=1800,
            )
            fake = FakeDeepFallbackClient(config.primary_model)
            builder = GigBuilder(storage, config=config, client=fake)

            async def run():
                return await builder.generate(
                    "draft-fallback",
                    job_id,
                    mode="standard",
                    target_gig_url=url,
                    preferences={"target_buyer": "Marketing teams"},
                )

            result = asyncio.run(run())
            self.assertTrue(result["validation"]["passed"])
            self.assertEqual(result["models"]["draft"], config.deep_model)
            self.assertTrue(result["warnings"])
            self.assertIn(config.primary_model, fake.models)

    def test_generic_openrouter_endpoint_error_still_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, url = self._fixture(directory)
            config = OpenRouterConfig(
                api_key="sk-or-test-placeholder",
                primary_model="google/gemini-3.7-flash",
                deep_model="anthropic/unavailable-deep-model",
                max_cost_usd=1,
                max_output_tokens=1800,
            )

            class GenericErrorClient(FakeGenerationClient):
                def __init__(self, deep_model):
                    super().__init__()
                    self.deep_model = deep_model
                    self.models = []

                async def chat_json(self, **kwargs):
                    model = kwargs.get("model")
                    self.models.append(model)
                    if model == self.deep_model:
                        raise OpenRouterError(
                            "No endpoints found that can handle the requested parameters. "
                            "To learn more about provider routing, visit: "
                            "https://openrouter.ai/docs/guides/routing/provider-selection (HTTP 404)"
                        )
                    return await super().chat_json(**kwargs)

            fake = GenericErrorClient(config.deep_model)
            builder = GigBuilder(storage, config=config, client=fake)

            async def run():
                return await builder.generate(
                    "generic-fallback",
                    job_id,
                    mode="deep",
                    target_gig_url=url,
                    preferences={"target_buyer": "Marketing teams"},
                )

            result = asyncio.run(run())
            self.assertEqual(result["models"]["actual_refinement"], config.primary_model)
            self.assertTrue(result["warnings"])
            self.assertIn(config.deep_model, fake.models)

    def test_generation_manager_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            storage, job_id, url = self._fixture(directory)
            manager = GenerationManager(storage)

            async def run_manager():
                started = manager.start_run(
                    job_id,
                    mode="dry_run",
                    target_gig_url=url,
                    preferences={"target_buyer": "Marketing teams"},
                )
                for _ in range(40):
                    state = manager.get_run(started["id"])
                    if state["status"] in {"completed", "failed"}:
                        break
                    await asyncio.sleep(0.02)
                result = manager.get_result(started["id"])
                await manager.shutdown()
                return state, result

            state, result = asyncio.run(run_manager())
            self.assertEqual(state["status"], "completed")
            self.assertTrue(result["dry_run"])
            self.assertEqual(state["total_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
