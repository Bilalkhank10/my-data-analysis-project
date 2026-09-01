"""Background Phase 4 generation orchestration."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from gig_builder import GigBuilder, generation_markdown
from openrouter_client import OpenRouterConfig
from storage import Storage, utc_now


class GenerationManager:
    MODES = {"dry_run", "test", "standard", "deep"}

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.config = OpenRouterConfig.from_env()
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._gate = asyncio.Semaphore(1)

    def public_config(self) -> dict[str, Any]:
        config = self.config.public_dict()
        config.update(
            {
                "phase": 4,
                "provider": "openrouter",
                "supported_modes": ["dry_run", "test", "standard", "deep"],
                "auto_publish": False,
                "human_approval_required": True,
                "outputs": [
                    "positioning options", "title", "five tags", "description",
                    "packages", "FAQs", "requirements", "scope exclusions", "CTA",
                    "thumbnail copy", "gallery briefs", "video script",
                    "compliance validation", "before/after comparison",
                ],
            }
        )
        return config

    def start_run(
        self,
        job_id: str,
        *,
        mode: str,
        target_gig_url: str | None,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        if mode not in self.MODES:
            raise ValueError("Unsupported generation mode")
        job = self.storage.get_job(job_id)
        if job is None:
            raise ValueError("Crawl job not found")
        if job["status"] not in {"completed", "cancelled"}:
            raise ValueError("Complete Phase 1/2 before building a gig")
        if self.storage.get_analysis(job_id) is None:
            raise ValueError("Phase 2 analysis is required")
        if mode != "dry_run" and not self.config.configured:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. Revoke the exposed key and set a new environment secret."
            )
        ai_run_id = None
        for run in self.storage.list_ai_runs(job_id, 20):
            if run.get("status") == "completed" and run.get("result") and not run["result"].get("dry_run"):
                ai_run_id = run["id"]
                break
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_id = f"gen-{stamp}-{uuid.uuid4().hex[:8]}"
        run = self.storage.create_generation_run(
            run_id,
            job_id,
            ai_run_id=ai_run_id,
            mode=mode,
            target_gig_url=target_gig_url,
            preferences=preferences,
            primary_model=preferences.get("draft_model") or self.config.primary_model,
            deep_model=preferences.get("refinement_model") or self.config.deep_model,
            max_cost_usd=self.config.max_cost_usd,
        )
        task = asyncio.create_task(
            self._execute(
                run_id,
                job_id,
                mode=mode,
                target_gig_url=target_gig_url,
                preferences=preferences,
            )
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))
        return self.public_run(run)

    async def _execute(
        self,
        run_id: str,
        job_id: str,
        *,
        mode: str,
        target_gig_url: str | None,
        preferences: dict[str, Any],
    ) -> None:
        async with self._gate:
            self.storage.update_generation_run(
                run_id,
                status="running",
                stage="preparing market evidence",
                progress_percent=3,
                started_at=utc_now(),
            )
            builder = GigBuilder(self.storage, config=self.config)

            async def progress(event: dict[str, Any]) -> None:
                fields = {
                    key: event[key]
                    for key in (
                        "stage", "progress_percent", "prompt_tokens",
                        "completion_tokens", "total_tokens", "actual_cost_usd",
                    )
                    if key in event
                }
                if fields:
                    self.storage.update_generation_run(run_id, **fields)

            try:
                if mode == "dry_run":
                    result = builder.dry_run_plan(
                        job_id,
                        mode="standard",
                        target_gig_url=target_gig_url,
                        preferences=preferences,
                    )
                else:
                    result = await builder.generate(
                        run_id,
                        job_id,
                        mode=mode,
                        target_gig_url=target_gig_url,
                        preferences=preferences,
                        progress=progress,
                    )
                usage = result.get("usage") or {}
                self.storage.update_generation_run(
                    run_id,
                    status="completed",
                    stage="completed",
                    progress_percent=100,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    estimated_cost_usd=result.get("estimated_cost_usd", 0),
                    actual_cost_usd=usage.get("actual_cost_usd", 0),
                    approval_status="draft",
                    result_json=result,
                    finished_at=utc_now(),
                )
            except Exception as exc:
                self.storage.update_generation_run(
                    run_id,
                    status="failed",
                    stage="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    finished_at=utc_now(),
                )

    @staticmethod
    def public_run(run: dict[str, Any]) -> dict[str, Any]:
        data = dict(run)
        data.pop("result", None)
        run_id = run["id"]
        data["status_url"] = f"/api/generation-runs/{run_id}"
        data["result_url"] = f"/api/generation-runs/{run_id}/result"
        data["markdown_url"] = f"/api/generation-runs/{run_id}/export.md"
        data["approval_url"] = f"/api/generation-runs/{run_id}/approval"
        return data

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.storage.get_generation_run(run_id)
        return self.public_run(run) if run else None

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        run = self.storage.get_generation_run(run_id)
        return run.get("result") if run else None

    def list_runs(self, job_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [self.public_run(run) for run in self.storage.list_generation_runs(job_id, limit)]

    def set_approval(self, run_id: str, status: str) -> dict[str, Any] | None:
        if status not in {"draft", "approved", "rejected"}:
            raise ValueError("Approval must be draft, approved, or rejected")
        run = self.storage.get_generation_run(run_id)
        if run is None:
            return None
        if run["status"] != "completed":
            raise ValueError("Only completed drafts can be reviewed")
        if status == "approved" and (run.get("result") or {}).get("dry_run"):
            raise ValueError("A dry-run plan cannot be approved as a generated gig")
        self.storage.update_generation_run(run_id, approval_status=status)
        updated = self.storage.get_generation_run(run_id)
        return self.public_run(updated) if updated else None

    def markdown(self, run_id: str) -> str | None:
        result = self.get_result(run_id)
        return generation_markdown(result) if result else None

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
