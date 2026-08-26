"""Background Phase 3 AI-run management."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ai_analyzer import Phase3Analyzer
from openrouter_client import OpenRouterClient, OpenRouterConfig
from storage import Storage, utc_now


class AIJobManager:
    MODES = {"dry_run", "test", "standard", "deep"}

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.config = OpenRouterConfig.from_env()
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._gate = asyncio.Semaphore(1)

    def public_config(self) -> dict[str, Any]:
        data = self.config.public_dict()
        data.update(
            {
                "provider": "openrouter",
                "supported_modes": ["dry_run", "test", "standard", "deep"],
                "security": "API key is read from environment only and never returned or persisted.",
                "recommended_test_mode": "dry_run",
            }
        )
        return data

    async def validate_key(self) -> dict[str, Any]:
        return await OpenRouterClient(self.config).key_status()

    def start_run(
        self,
        job_id: str,
        *,
        mode: str,
        max_gigs: int,
        own_gig_url: str | None = None,
    ) -> dict[str, Any]:
        if mode not in self.MODES:
            raise ValueError("Unsupported AI mode")
        job = self.storage.get_job(job_id)
        if job is None:
            raise ValueError("Crawl job not found")
        if job["status"] not in {"completed", "cancelled"}:
            raise ValueError("Complete the crawl before starting Phase 3")
        if mode != "dry_run" and not self.config.configured:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. Rotate the exposed key and set a new environment secret."
            )
        max_gigs = max(1, min(self.config.max_gigs, int(max_gigs)))
        if mode == "test":
            max_gigs = 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_id = f"ai-{stamp}-{uuid.uuid4().hex[:8]}"
        run = self.storage.create_ai_run(
            run_id,
            job_id,
            mode=mode,
            primary_model=self.config.primary_model,
            embedding_model=self.config.embedding_model,
            deep_model=self.config.deep_model,
            max_gigs=max_gigs,
            max_cost_usd=self.config.max_cost_usd,
        )
        task = asyncio.create_task(
            self._execute(run_id, job_id, mode, max_gigs, own_gig_url)
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))
        return self.public_run(run)

    async def _execute(
        self,
        run_id: str,
        job_id: str,
        mode: str,
        max_gigs: int,
        own_gig_url: str | None,
    ) -> None:
        async with self._gate:
            self.storage.update_ai_run(
                run_id,
                status="running",
                stage="selecting gigs",
                progress_percent=2,
                started_at=utc_now(),
            )
            analyzer = Phase3Analyzer(self.storage, config=self.config)

            async def progress(event: dict[str, Any]) -> None:
                allowed = {
                    "stage",
                    "progress_percent",
                    "selected_gigs",
                    "processed_gigs",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "actual_cost_usd",
                }
                fields = {key: event[key] for key in allowed if key in event}
                if fields:
                    self.storage.update_ai_run(run_id, **fields)

            try:
                if mode == "dry_run":
                    result = analyzer.dry_run_plan(
                        job_id,
                        max_gigs=max_gigs,
                        mode="standard",
                        own_gig_url=own_gig_url,
                    )
                else:
                    result = await analyzer.analyze(
                        run_id,
                        job_id,
                        max_gigs=max_gigs,
                        mode=mode,
                        own_gig_url=own_gig_url,
                        progress=progress,
                    )
                usage = result.get("usage") or {}
                self.storage.update_ai_run(
                    run_id,
                    status="completed",
                    stage="completed",
                    progress_percent=100,
                    selected_gigs=(result.get("selection") or {}).get(
                        "selected_gigs", result.get("selected_gigs", 0)
                    ),
                    processed_gigs=len(result.get("gig_analyses") or []),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    estimated_cost_usd=result.get("estimated_cost_usd", 0),
                    actual_cost_usd=usage.get("actual_cost_usd", 0),
                    result_json=result,
                    finished_at=utc_now(),
                )
            except Exception as exc:
                # Exception messages are designed upstream not to contain credentials.
                self.storage.update_ai_run(
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
        data["status_url"] = f"/api/ai-runs/{run['id']}"
        data["result_url"] = f"/api/ai-runs/{run['id']}/result"
        return data

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.storage.get_ai_run(run_id)
        return self.public_run(run) if run else None

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        run = self.storage.get_ai_run(run_id)
        if run is None:
            return None
        return run.get("result")

    def list_runs(self, job_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [self.public_run(run) for run in self.storage.list_ai_runs(job_id, limit)]

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
