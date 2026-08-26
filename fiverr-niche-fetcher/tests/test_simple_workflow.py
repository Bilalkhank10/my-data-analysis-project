import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from simple_workflow import SimpleWorkflowManager
from storage import Storage


class FakeJobs:
    def __init__(self, storage):
        self.storage = storage
        self.counter = 0

    def start_job(self, niche, limit):
        self.counter += 1
        job_id = f"job-{self.counter}"
        self.storage.create_job(job_id, niche, limit)
        self.storage.update_job(
            job_id,
            status="completed",
            stage="completed",
            progress_percent=100,
            discovered_count=limit,
            processed_count=limit,
            success_count=limit,
        )
        return self.storage.get_job(job_id)

    def get_job(self, job_id):
        return self.storage.get_job(job_id)


class FakeAI:
    def __init__(self, storage):
        self.storage = storage
        self.config = SimpleNamespace(configured=True)

    def start_run(self, job_id, mode, max_gigs, own_gig_url=None):
        run_id = "ai-test"
        self.storage.create_ai_run(
            run_id,
            job_id,
            mode=mode,
            primary_model="primary",
            embedding_model="embedding",
            deep_model="deep",
            max_gigs=max_gigs,
            max_cost_usd=1,
        )
        self.storage.update_ai_run(
            run_id,
            status="completed",
            stage="completed",
            progress_percent=100,
            result_json={"version": "test", "gig_analyses": []},
        )
        return self.storage.get_ai_run(run_id)

    def get_run(self, run_id):
        return self.storage.get_ai_run(run_id)


class FakeGeneration:
    def __init__(self, storage):
        self.storage = storage
        self.config = SimpleNamespace(configured=True)

    def start_run(self, job_id, mode, target_gig_url, preferences):
        run_id = "gen-test"
        self.storage.create_generation_run(
            run_id,
            job_id,
            ai_run_id="ai-test" if self.storage.get_ai_run("ai-test") else None,
            mode=mode,
            target_gig_url=target_gig_url,
            preferences=preferences,
            primary_model="primary",
            deep_model="deep",
            max_cost_usd=1,
        )
        self.storage.update_generation_run(
            run_id,
            status="completed",
            stage="completed",
            progress_percent=100,
            result_json={
                "final": {
                    "recommended_gig": {
                        "title": "I will build a dashboard",
                        "tags": ["one", "two", "three", "four", "five"],
                    }
                }
            },
        )
        run = self.storage.get_generation_run(run_id)
        return self.public(run)

    @staticmethod
    def public(run):
        return {**run, "markdown_url": f"/api/generation-runs/{run['id']}/export.md"}

    def get_run(self, run_id):
        run = self.storage.get_generation_run(run_id)
        return self.public(run) if run else None

    def get_result(self, run_id):
        run = self.storage.get_generation_run(run_id)
        return run.get("result") if run else None


class SimpleWorkflowTests(unittest.TestCase):
    def test_recommended_workflow_runs_backend_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory) / "simple.db")
            manager = SimpleWorkflowManager(
                storage,
                FakeJobs(storage),
                FakeAI(storage),
                FakeGeneration(storage),
            )

            async def run():
                started = manager.start(
                    niche="Looker Studio dashboard",
                    quality="recommended",
                    buyer="Ecommerce teams",
                    language="English",
                    existing_url=None,
                )
                for _ in range(50):
                    state = manager.get(started["id"])
                    if state["status"] in {"completed", "failed"}:
                        break
                    await asyncio.sleep(0.02)
                result = manager.result(started["id"])
                await manager.shutdown()
                return state, result

            state, result = asyncio.run(run())
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["stage"], "ready")
            self.assertEqual(state["progress_percent"], 100)
            self.assertTrue(state["job_id"])
            self.assertTrue(state["ai_run_id"])
            self.assertTrue(state["generation_run_id"])
            self.assertEqual(
                result["final"]["recommended_gig"]["title"],
                "I will build a dashboard",
            )


if __name__ == "__main__":
    unittest.main()
