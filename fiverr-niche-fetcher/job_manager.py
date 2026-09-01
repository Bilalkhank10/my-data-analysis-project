"""Background job orchestration, progress persistence, and exports."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import auth
from fiverr_fetcher import CrawlCancelled, FetcherError, FiverrNicheFetcher
from market_analyzer import ANALYSIS_VERSION, MarketAnalyzer
from storage import Storage, utc_now


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:36] or "search"


class JobManager:
    def __init__(self, storage: Storage, output_dir: str | Path) -> None:
        self.storage = storage
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        max_jobs = max(1, min(3, int(os.getenv("MAX_ACTIVE_JOBS", "1"))))
        self._gate = asyncio.Semaphore(max_jobs)
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self.storage.recover_incomplete_jobs()

    def start_job(self, niche: str, limit: int) -> dict[str, Any]:
        niche = " ".join(niche.split()).strip()
        limit = max(1, min(500, int(limit)))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_id = f"{stamp}-{_slug(niche)}-{uuid.uuid4().hex[:8]}"
        job = self.storage.create_job(job_id, niche, limit)
        cancel_event = asyncio.Event()
        self._cancel_events[job_id] = cancel_event
        task = asyncio.create_task(self._run_job(job_id, niche, limit, cancel_event))
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._task_finished(job_id))
        return self.public_job(job)

    def _task_finished(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)
        self._cancel_events.pop(job_id, None)

    async def _run_job(
        self, job_id: str, niche: str, limit: int, cancel_event: asyncio.Event
    ) -> None:
        async with self._gate:
            if cancel_event.is_set() or self.storage.is_cancel_requested(job_id):
                self.storage.update_job(
                    job_id,
                    status="cancelled",
                    stage="cancelled",
                    finished_at=utc_now(),
                    progress_percent=0,
                )
                return

            self.storage.update_job(
                job_id,
                status="running",
                stage="discovering",
                started_at=utc_now(),
                progress_percent=1.0,
            )
            fetcher = FiverrNicheFetcher()

            async def on_progress(event: dict[str, Any]) -> None:
                fields: dict[str, Any] = {}
                for key in (
                    "stage",
                    "progress_percent",
                    "pages_scanned",
                    "available_results",
                    "discovered_count",
                    "processed_count",
                    "success_count",
                    "failed_count",
                    "discovery_source",
                ):
                    if key in event and event[key] is not None:
                        fields[key] = event[key]
                if "warnings" in event:
                    fields["warnings_json"] = event["warnings"]
                if fields:
                    self.storage.update_job(job_id, **fields)

            async def on_search_records(records: list[dict[str, Any]]) -> None:
                self.storage.save_search_results(job_id, records)

            async def on_result(result: dict[str, Any]) -> None:
                self.storage.save_gig_result(job_id, result)

            try:
                payload = await fetcher.crawl(
                    niche,
                    limit,
                    on_progress=on_progress,
                    on_search_records=on_search_records,
                    on_result=on_result,
                    cancel_check=cancel_event.is_set,
                    collect_results=False,
                )
                was_cancelled = bool(payload.get("cancelled") or cancel_event.is_set())
                self.storage.update_job(
                    job_id,
                    stage="analyzing" if not was_cancelled else "analyzing partial data",
                    progress_percent=99.7 if not was_cancelled else min(
                        99.0,
                        float((self.storage.get_job(job_id) or {}).get("progress_percent", 0)),
                    ),
                )
                try:
                    self.analyze_job(job_id, force=True)
                except Exception as analysis_error:
                    warnings = list(payload.get("warnings") or [])
                    warnings.append(
                        f"Phase 2 analysis failed but crawl data was preserved: {analysis_error}"
                    )
                    payload["warnings"] = warnings
                    self.storage.update_job(job_id, warnings_json=warnings)
                json_path, csv_path = self._write_exports(job_id)
                if was_cancelled:
                    self.storage.update_job(
                        job_id,
                        status="cancelled",
                        stage="cancelled",
                        progress_percent=min(
                            99.0,
                            float((self.storage.get_job(job_id) or {}).get("progress_percent", 0)),
                        ),
                        finished_at=utc_now(),
                        json_path=str(json_path),
                        csv_path=str(csv_path),
                    )
                else:
                    self.storage.update_job(
                        job_id,
                        status="completed",
                        stage="completed",
                        progress_percent=100.0,
                        pages_scanned=payload.get("pages_scanned", 0),
                        available_results=payload.get("available_results"),
                        discovered_count=payload.get("discovered_count", 0),
                        processed_count=payload.get("processed_count", 0),
                        success_count=payload.get("success_count", 0),
                        failed_count=payload.get("failed_count", 0),
                        discovery_source=payload.get("discovery_source"),
                        warnings_json=payload.get("warnings", []),
                        finished_at=payload.get("finished_at") or utc_now(),
                        json_path=str(json_path),
                        csv_path=str(csv_path),
                    )
            except CrawlCancelled:
                if self.storage.count_search_results(job_id):
                    try:
                        self.analyze_job(job_id, force=True)
                    except Exception:
                        pass
                json_path, csv_path = self._write_exports(job_id)
                self.storage.update_job(
                    job_id,
                    status="cancelled",
                    stage="cancelled",
                    finished_at=utc_now(),
                    json_path=str(json_path),
                    csv_path=str(csv_path),
                )
            except Exception as exc:
                self.storage.update_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    finished_at=utc_now(),
                )

    def analyze_job(
        self, job_id: str, *, force: bool = False
    ) -> dict[str, Any] | None:
        job = self.storage.get_job(job_id)
        if job is None:
            return None
        if not force:
            existing = self.storage.get_analysis(job_id, ANALYSIS_VERSION)
            if existing is not None:
                return existing
        analysis = MarketAnalyzer(self.storage).analyze(job_id)
        self.storage.save_analysis(job_id, analysis, ANALYSIS_VERSION)
        return analysis

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.storage.get_job(job_id)
        if job is None:
            return None
        event = self._cancel_events.get(job_id)
        if event:
            event.set()
        self.storage.request_cancel(job_id)
        return self.public_job(self.storage.get_job(job_id) or job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.storage.get_job(job_id)
        return self.public_job(job) if job else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        return [self.public_job(job) for job in self.storage.list_jobs(limit)]

    @staticmethod
    def public_job(job: dict[str, Any]) -> dict[str, Any]:
        result = dict(job)
        job_id = result["id"]
        if result.get("json_path"):
            # Signed, time-limited URL (no session token in the query string).
            result.setdefault("downloads", {})["json"] = auth.sign_download_url(f"{job_id}.json")
        if result.get("csv_path"):
            result.setdefault("downloads", {})["csv"] = auth.sign_download_url(f"{job_id}.csv")
        result["results_url"] = f"/api/jobs/{job_id}/results"
        result["analysis_url"] = f"/api/jobs/{job_id}/analysis"
        result["cancel_url"] = f"/api/jobs/{job_id}/cancel"
        return result

    def _write_exports(self, job_id: str) -> tuple[Path, Path]:
        job = self.storage.get_job(job_id)
        if job is None:
            raise FetcherError("Cannot export an unknown job")
        results = self.storage.get_all_job_results(job_id)
        search_results = self.storage.get_all_search_results(job_id)
        analysis = self.storage.get_analysis(job_id, ANALYSIS_VERSION)
        json_path = self.output_dir / f"{job_id}.json"
        csv_path = self.output_dir / f"{job_id}.csv"
        json_payload = {
            "job": self.public_job(job),
            "exported_at": utc_now(),
            "search_results": search_results,
            "results": results,
            "analysis": analysis,
        }
        json_path.write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        columns = [
            "detail_status",
            "global_position",
            "organic_position",
            "sponsored_position",
            "page_number",
            "page_position",
            "is_sponsored",
            "seller_online",
            "card_title",
            "card_seller_name",
            "card_seller_level",
            "card_rating",
            "card_review_count",
            "card_price",
            "thumbnail_url",
            "badges",
            "url",
            "title",
            "seller_username",
            "seller_name",
            "seller_level",
            "seller_country",
            "member_since",
            "average_response_time",
            "last_delivery",
            "rating",
            "review_count",
            "starting_price_usd",
            "currency",
            "hourly_rate_usd",
            "category_path",
            "meta_description",
            "about_text",
            "packages",
            "faqs",
            "review_summary",
            "visible_reviews",
            "related_tags",
            "media_urls",
            "gallery_count",
            "has_video",
            "fetch_method",
            "fetched_at",
            "error",
        ]
        detail_by_url = {str(result.get("url")): result for result in results}
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for search in search_results:
                result = detail_by_url.get(str(search.get("url"))) or {}
                row = dict(result)
                row["detail_status"] = (
                    "failed" if result.get("error") else "success" if result else "not_fetched"
                )
                row["url"] = result.get("url") or search.get("url")
                row["title"] = result.get("title") or search.get("card_title")
                row["seller_name"] = result.get("seller_name") or search.get("card_seller_name")
                row["seller_username"] = result.get("seller_username") or search.get("card_seller_username")
                row["seller_level"] = result.get("seller_level") or search.get("card_seller_level")
                for key in (
                    "global_position",
                    "organic_position",
                    "sponsored_position",
                    "page_number",
                    "page_position",
                    "is_sponsored",
                    "seller_online",
                    "card_title",
                    "card_seller_name",
                    "card_seller_level",
                    "card_rating",
                    "card_review_count",
                    "card_price",
                    "thumbnail_url",
                ):
                    row[key] = search.get(key)
                row["badges"] = json.dumps(search.get("badges") or [], ensure_ascii=False)
                for key in (
                    "category_path",
                    "packages",
                    "faqs",
                    "review_summary",
                    "visible_reviews",
                    "related_tags",
                    "media_urls",
                ):
                    row[key] = json.dumps(row.get(key) or [], ensure_ascii=False)
                writer.writerow(row)
        return json_path, csv_path

    async def shutdown(self) -> None:
        events = list(self._cancel_events.values())
        for event in events:
            event.set()
        tasks = list(self._tasks.values())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
