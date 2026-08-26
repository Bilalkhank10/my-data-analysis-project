"""Backend orchestration for the non-technical one-click frontend."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ai_manager import AIJobManager
from generation_manager import GenerationManager
from job_manager import JobManager
from storage import Storage, utc_now


class SimpleWorkflowManager:
    QUALITY = {
        "fast": {
            "crawl_limit": 10,
            "run_ai": False,
            "ai_mode": "standard",
            "ai_gigs": 0,
            "generation_mode": "standard",
        },
        "recommended": {
            "crawl_limit": 25,
            "run_ai": True,
            "ai_mode": "standard",
            "ai_gigs": 5,
            "generation_mode": "standard",
        },
        "best": {
            "crawl_limit": 50,
            "run_ai": True,
            "ai_mode": "standard",
            "ai_gigs": 10,
            "generation_mode": "deep",
        },
    }

    def __init__(
        self,
        storage: Storage,
        jobs: JobManager,
        ai: AIJobManager,
        generation: GenerationManager,
    ) -> None:
        self.storage = storage
        self.jobs = jobs
        self.ai = ai
        self.generation = generation
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._gate = asyncio.Semaphore(1)

    def start(
        self,
        *,
        niche: str,
        quality: str,
        buyer: str,
        language: str,
        existing_url: str | None,
    ) -> dict[str, Any]:
        if quality not in self.QUALITY:
            raise ValueError("Choose Quick, Recommended, or Best quality")
        if not self.generation.config.configured:
            raise ValueError(
                "AI is not connected. Add a new OpenRouter key to the local .env file and restart."
            )
        niche = " ".join(niche.split()).strip()
        if len(niche) < 2:
            raise ValueError("Enter the service you want to sell")
        inputs = {
            "niche": niche,
            "quality": quality,
            "buyer": " ".join(buyer.split()).strip(),
            "language": language.strip() or "English",
            "existing_url": existing_url.strip() if existing_url else None,
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        workflow_id = f"flow-{stamp}-{uuid.uuid4().hex[:8]}"
        workflow = self.storage.create_simple_workflow(
            workflow_id, niche=niche, quality=quality, inputs=inputs
        )
        task = asyncio.create_task(self._run(workflow_id, inputs))
        self._tasks[workflow_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(workflow_id, None))
        return self.public(workflow)

    async def _wait(
        self,
        getter: Callable[[str], dict[str, Any] | None],
        item_id: str,
        *,
        workflow_id: str,
        progress_start: float,
        progress_span: float,
        stage: str,
        message: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        started = asyncio.get_running_loop().time()
        while True:
            item = getter(item_id)
            if item is None:
                raise RuntimeError(f"{stage} job disappeared")
            child_progress = float(item.get("progress_percent") or 0)
            self.storage.update_simple_workflow(
                workflow_id,
                stage=stage,
                message=message,
                progress_percent=min(99.0, progress_start + child_progress * progress_span / 100),
            )
            if item.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
                return item
            if asyncio.get_running_loop().time() - started > timeout_seconds:
                raise TimeoutError(f"{stage} took too long")
            await asyncio.sleep(1.2)

    async def _run(self, workflow_id: str, inputs: dict[str, Any]) -> None:
        async with self._gate:
            config = self.QUALITY[inputs["quality"]]
            warnings: list[str] = []
            self.storage.update_simple_workflow(
                workflow_id,
                status="running",
                stage="research",
                message="Researching competitors, pricing, and buyer language",
                progress_percent=2,
                started_at=utc_now(),
            )
            try:
                crawl = self.jobs.start_job(inputs["niche"], config["crawl_limit"])
                job_id = crawl["id"]
                self.storage.update_simple_workflow(workflow_id, job_id=job_id)
                crawl = await self._wait(
                    self.jobs.get_job,
                    job_id,
                    workflow_id=workflow_id,
                    progress_start=3,
                    progress_span=52,
                    stage="research",
                    message="Researching competitors, prices, packages, and reviews",
                    timeout_seconds=90 * 60,
                )
                if crawl["status"] not in {"completed", "cancelled"}:
                    raise RuntimeError(crawl.get("error") or "Market research did not complete")

                ai_run_id = None
                if config["run_ai"]:
                    self.storage.update_simple_workflow(
                        workflow_id,
                        stage="understand",
                        message="Understanding buyer intent and positioning gaps",
                        progress_percent=56,
                    )
                    ai_run = self.ai.start_run(
                        job_id,
                        mode=config["ai_mode"],
                        max_gigs=config["ai_gigs"],
                        own_gig_url=inputs.get("existing_url"),
                    )
                    ai_run_id = ai_run["id"]
                    self.storage.update_simple_workflow(
                        workflow_id, ai_run_id=ai_run_id
                    )
                    ai_run = await self._wait(
                        self.ai.get_run,
                        ai_run_id,
                        workflow_id=workflow_id,
                        progress_start=56,
                        progress_span=22,
                        stage="understand",
                        message="Understanding what buyers want",
                        timeout_seconds=40 * 60,
                    )
                    if ai_run["status"] != "completed":
                        warnings.append(
                            "Buyer-intent audit did not finish; the draft used deterministic market research instead."
                        )

                self.storage.update_simple_workflow(
                    workflow_id,
                    stage="build",
                    message="Writing your copy-ready Fiverr gig",
                    progress_percent=79,
                    warnings_json=warnings,
                )
                generation = self.generation.start_run(
                    job_id,
                    mode=config["generation_mode"],
                    target_gig_url=inputs.get("existing_url"),
                    preferences={
                        "target_buyer": inputs.get("buyer") or "Infer from market evidence",
                        "positioning_goal": f"Create a differentiated, conversion-focused {inputs['niche']} offer",
                        "tone": "professional",
                        "output_language": inputs.get("language") or "English",
                        "pricing_preference": "market_aligned",
                    },
                )
                generation_run_id = generation["id"]
                self.storage.update_simple_workflow(
                    workflow_id, generation_run_id=generation_run_id
                )
                generation = await self._wait(
                    self.generation.get_run,
                    generation_run_id,
                    workflow_id=workflow_id,
                    progress_start=79,
                    progress_span=20,
                    stage="build",
                    message="Building title, tags, description, packages, FAQs, and visuals",
                    timeout_seconds=40 * 60,
                )
                if generation["status"] != "completed":
                    raise RuntimeError(
                        generation.get("error") or "Gig generation did not complete"
                    )

                self.storage.update_simple_workflow(
                    workflow_id,
                    status="completed",
                    stage="ready",
                    message="Your copy-ready Fiverr gig is complete",
                    progress_percent=100,
                    warnings_json=warnings,
                    finished_at=utc_now(),
                )
            except Exception as exc:
                self.storage.update_simple_workflow(
                    workflow_id,
                    status="failed",
                    stage="failed",
                    message="The workflow was interrupted",
                    error=f"{type(exc).__name__}: {exc}",
                    warnings_json=warnings,
                    finished_at=utc_now(),
                )

    @staticmethod
    def public(workflow: dict[str, Any]) -> dict[str, Any]:
        data = dict(workflow)
        data["status_url"] = f"/api/simple-workflows/{workflow['id']}"
        if workflow.get("generation_run_id"):
            data["result_url"] = (
                f"/api/generation-runs/{workflow['generation_run_id']}/result"
            )
            data["markdown_url"] = (
                f"/api/generation-runs/{workflow['generation_run_id']}/export.md"
            )
        return data

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        workflow = self.storage.get_simple_workflow(workflow_id)
        return self.public(workflow) if workflow else None

    def result(self, workflow_id: str) -> dict[str, Any] | None:
        workflow = self.storage.get_simple_workflow(workflow_id)
        if not workflow or not workflow.get("generation_run_id"):
            return None
        return self.generation.get_result(workflow["generation_run_id"])

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
