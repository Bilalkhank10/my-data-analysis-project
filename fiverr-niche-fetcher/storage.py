"""SQLite persistence for Phase 1 background crawls and rank snapshots."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    """Small synchronous SQLite repository.

    A connection is opened per operation. WAL mode plus a process lock keeps writes
    deterministic while background asyncio tasks report progress concurrently.
    """

    JOB_FIELDS = {
        "status",
        "stage",
        "progress_percent",
        "pages_scanned",
        "available_results",
        "discovered_count",
        "processed_count",
        "success_count",
        "failed_count",
        "discovery_source",
        "warnings_json",
        "error",
        "cancel_requested",
        "started_at",
        "finished_at",
        "json_path",
        "csv_path",
    }
    AI_RUN_FIELDS = {
        "status",
        "stage",
        "selected_gigs",
        "processed_gigs",
        "progress_percent",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "actual_cost_usd",
        "error",
        "started_at",
        "finished_at",
        "result_json",
    }
    GENERATION_RUN_FIELDS = {
        "status",
        "stage",
        "progress_percent",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "actual_cost_usd",
        "error",
        "approval_status",
        "started_at",
        "finished_at",
        "result_json",
    }
    WORKFLOW_FIELDS = {
        "status",
        "stage",
        "message",
        "progress_percent",
        "job_id",
        "ai_run_id",
        "generation_run_id",
        "warnings_json",
        "error",
        "started_at",
        "finished_at",
    }

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def init_schema(self) -> None:
        schema = """
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            niche TEXT NOT NULL,
            requested_limit INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            progress_percent REAL NOT NULL DEFAULT 0,
            pages_scanned INTEGER NOT NULL DEFAULT 0,
            available_results INTEGER,
            discovered_count INTEGER NOT NULL DEFAULT 0,
            processed_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            discovery_source TEXT,
            warnings_json TEXT NOT NULL DEFAULT '[]',
            error TEXT,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            json_path TEXT,
            csv_path TEXT
        );

        CREATE TABLE IF NOT EXISTS search_results (
            job_id TEXT NOT NULL,
            url TEXT NOT NULL,
            niche TEXT NOT NULL,
            page_number INTEGER,
            page_position INTEGER,
            global_position INTEGER,
            organic_position INTEGER,
            sponsored_position INTEGER,
            is_sponsored INTEGER NOT NULL DEFAULT 0,
            seller_online INTEGER NOT NULL DEFAULT 0,
            card_title TEXT,
            card_seller_name TEXT,
            card_seller_username TEXT,
            card_seller_level TEXT,
            card_rating REAL,
            card_review_count INTEGER,
            card_price REAL,
            currency TEXT,
            thumbnail_url TEXT,
            badges_json TEXT NOT NULL DEFAULT '[]',
            raw_card_text TEXT,
            discovered_at TEXT NOT NULL,
            PRIMARY KEY (job_id, url),
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_search_job_rank
            ON search_results(job_id, global_position);
        CREATE INDEX IF NOT EXISTS idx_search_url
            ON search_results(url);

        CREATE TABLE IF NOT EXISTS gig_snapshots (
            job_id TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            fetch_method TEXT,
            title TEXT,
            seller_username TEXT,
            seller_name TEXT,
            seller_level TEXT,
            rating REAL,
            review_count INTEGER,
            starting_price_usd REAL,
            error TEXT,
            result_json TEXT NOT NULL,
            PRIMARY KEY (job_id, url),
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_job
            ON gig_snapshots(job_id);

        CREATE TABLE IF NOT EXISTS gigs (
            url TEXT PRIMARY KEY,
            title TEXT,
            seller_username TEXT,
            seller_name TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            latest_result_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analysis_snapshots (
            job_id TEXT NOT NULL,
            version TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            PRIMARY KEY (job_id, version),
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ai_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            mode TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'openrouter',
            primary_model TEXT,
            embedding_model TEXT,
            deep_model TEXT,
            max_gigs INTEGER NOT NULL,
            selected_gigs INTEGER NOT NULL DEFAULT 0,
            processed_gigs INTEGER NOT NULL DEFAULT 0,
            progress_percent REAL NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            estimated_cost_usd REAL NOT NULL DEFAULT 0,
            actual_cost_usd REAL NOT NULL DEFAULT 0,
            max_cost_usd REAL NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            result_json TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_ai_runs_job
            ON ai_runs(job_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS ai_cache (
            cache_key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            usage_json TEXT NOT NULL DEFAULT '{}',
            cost_usd REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS embedding_cache (
            cache_key TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            vector_json TEXT NOT NULL,
            usage_json TEXT NOT NULL DEFAULT '{}',
            cost_usd REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generation_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            ai_run_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            mode TEXT NOT NULL,
            target_gig_url TEXT,
            preferences_json TEXT NOT NULL DEFAULT '{}',
            primary_model TEXT,
            deep_model TEXT,
            progress_percent REAL NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            estimated_cost_usd REAL NOT NULL DEFAULT 0,
            actual_cost_usd REAL NOT NULL DEFAULT 0,
            max_cost_usd REAL NOT NULL DEFAULT 0,
            approval_status TEXT NOT NULL DEFAULT 'draft',
            error TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            result_json TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (ai_run_id) REFERENCES ai_runs(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_generation_runs_job
            ON generation_runs(job_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS simple_workflows (
            id TEXT PRIMARY KEY,
            niche TEXT NOT NULL,
            quality TEXT NOT NULL,
            inputs_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            message TEXT,
            progress_percent REAL NOT NULL DEFAULT 0,
            job_id TEXT,
            ai_run_id TEXT,
            generation_run_id TEXT,
            warnings_json TEXT NOT NULL DEFAULT '[]',
            error TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
            FOREIGN KEY (ai_run_id) REFERENCES ai_runs(id) ON DELETE SET NULL,
            FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id) ON DELETE SET NULL
        );
        """
        with self._lock, self._connection() as connection:
            connection.executescript(schema)
            # Migration: add columns that may be absent in older database files.
            # ALTER TABLE ignores columns that already exist (guarded by try/except).
            migrations = [
                "ALTER TABLE ai_runs ADD COLUMN estimated_cost_usd REAL NOT NULL DEFAULT 0",
                "ALTER TABLE generation_runs ADD COLUMN estimated_cost_usd REAL NOT NULL DEFAULT 0",
            ]
            for stmt in migrations:
                try:
                    connection.execute(stmt)
                except Exception:
                    pass  # Column already exists — safe to ignore

    def recover_incomplete_jobs(self) -> int:
        """Mark jobs left running by a previous process as interrupted."""
        now = utc_now()
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='interrupted', stage='interrupted',
                    error=COALESCE(error, 'Server restarted before this job completed.'),
                    finished_at=?, updated_at=?
                WHERE status IN ('queued', 'running', 'cancelling')
                """,
                (now, now),
            )
            ai_cursor = connection.execute(
                """
                UPDATE ai_runs
                SET status='interrupted', stage='interrupted',
                    error=COALESCE(error, 'Server restarted before this AI run completed.'),
                    finished_at=?, updated_at=?
                WHERE status IN ('queued', 'running')
                """,
                (now, now),
            )
            generation_cursor = connection.execute(
                """
                UPDATE generation_runs
                SET status='interrupted', stage='interrupted',
                    error=COALESCE(error, 'Server restarted before this generation completed.'),
                    finished_at=?, updated_at=?
                WHERE status IN ('queued', 'running')
                """,
                (now, now),
            )
            workflow_cursor = connection.execute(
                """
                UPDATE simple_workflows
                SET status='interrupted', stage='interrupted',
                    error=COALESCE(error, 'Server restarted before this workflow completed.'),
                    finished_at=?, updated_at=?
                WHERE status IN ('queued', 'running')
                """,
                (now, now),
            )
            return (
                cursor.rowcount
                + ai_cursor.rowcount
                + generation_cursor.rowcount
                + workflow_cursor.rowcount
            )

    def create_job(self, job_id: str, niche: str, requested_limit: int) -> dict[str, Any]:
        now = utc_now()
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, niche, requested_limit, status, stage,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'queued', 'queued', ?, ?)
                """,
                (job_id, niche, requested_limit, now, now),
            )
        job = self.get_job(job_id)
        if job is None:  # pragma: no cover - defensive
            raise RuntimeError("Created job could not be reloaded")
        return job

    def update_job(self, job_id: str, **fields: Any) -> None:
        clean: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in self.JOB_FIELDS:
                raise ValueError(f"Unsupported job field: {key}")
            if key == "warnings_json" and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            if key == "cancel_requested":
                value = int(bool(value))
            clean[key] = value
        if not clean:
            return
        clean["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in clean)
        values = list(clean.values()) + [job_id]
        with self._lock, self._connection() as connection:
            connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id=?",  # fields are allow-listed
                values,
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job_row(row) if row else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._job_row(row) for row in rows]

    @staticmethod
    def _job_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["warnings"] = json.loads(data.pop("warnings_json") or "[]")
        except json.JSONDecodeError:
            data["warnings"] = []
            data.pop("warnings_json", None)
        data["cancel_requested"] = bool(data.get("cancel_requested"))
        return data

    def request_cancel(self, job_id: str) -> bool:
        now = utc_now()
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET cancel_requested=1,
                    status=CASE WHEN status IN ('queued','running') THEN 'cancelling' ELSE status END,
                    stage=CASE WHEN status IN ('queued','running') THEN 'cancelling' ELSE stage END,
                    updated_at=?
                WHERE id=? AND status IN ('queued','running','cancelling')
                """,
                (now, job_id),
            )
            return cursor.rowcount > 0

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        return bool(row and row[0])

    def save_search_results(self, job_id: str, records: Iterable[dict[str, Any]]) -> int:
        rows = list(records)
        if not rows:
            return 0
        now = utc_now()
        sql = """
        INSERT INTO search_results (
            job_id, url, niche, page_number, page_position, global_position,
            organic_position, sponsored_position, is_sponsored, seller_online,
            card_title, card_seller_name, card_seller_username, card_seller_level,
            card_rating, card_review_count, card_price, currency, thumbnail_url,
            badges_json, raw_card_text, discovered_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(job_id, url) DO UPDATE SET
            page_number=excluded.page_number,
            page_position=excluded.page_position,
            global_position=excluded.global_position,
            organic_position=excluded.organic_position,
            sponsored_position=excluded.sponsored_position,
            is_sponsored=excluded.is_sponsored,
            seller_online=excluded.seller_online,
            card_title=COALESCE(excluded.card_title, search_results.card_title),
            card_seller_name=COALESCE(excluded.card_seller_name, search_results.card_seller_name),
            card_seller_username=COALESCE(excluded.card_seller_username, search_results.card_seller_username),
            card_seller_level=COALESCE(excluded.card_seller_level, search_results.card_seller_level),
            card_rating=COALESCE(excluded.card_rating, search_results.card_rating),
            card_review_count=COALESCE(excluded.card_review_count, search_results.card_review_count),
            card_price=COALESCE(excluded.card_price, search_results.card_price),
            thumbnail_url=COALESCE(excluded.thumbnail_url, search_results.thumbnail_url),
            badges_json=excluded.badges_json,
            raw_card_text=excluded.raw_card_text
        """
        values = []
        for record in rows:
            values.append(
                (
                    job_id,
                    record["url"],
                    record.get("niche", ""),
                    record.get("page_number"),
                    record.get("page_position"),
                    record.get("global_position"),
                    record.get("organic_position"),
                    record.get("sponsored_position"),
                    int(bool(record.get("is_sponsored"))),
                    int(bool(record.get("seller_online"))),
                    record.get("card_title"),
                    record.get("card_seller_name"),
                    record.get("card_seller_username"),
                    record.get("card_seller_level"),
                    record.get("card_rating"),
                    record.get("card_review_count"),
                    record.get("card_price"),
                    record.get("currency"),
                    record.get("thumbnail_url"),
                    json.dumps(record.get("badges") or [], ensure_ascii=False),
                    record.get("raw_card_text"),
                    record.get("discovered_at") or now,
                )
            )
        with self._lock, self._connection() as connection:
            connection.executemany(sql, values)
        return len(values)

    def save_gig_result(self, job_id: str, result: dict[str, Any]) -> None:
        now = utc_now()
        status = "failed" if result.get("error") else "success"
        result_json = json.dumps(result, ensure_ascii=False)
        url = str(result["url"])
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO gig_snapshots (
                    job_id, url, status, fetched_at, fetch_method, title,
                    seller_username, seller_name, seller_level, rating,
                    review_count, starting_price_usd, error, result_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id, url) DO UPDATE SET
                    status=excluded.status,
                    fetched_at=excluded.fetched_at,
                    fetch_method=excluded.fetch_method,
                    title=excluded.title,
                    seller_username=excluded.seller_username,
                    seller_name=excluded.seller_name,
                    seller_level=excluded.seller_level,
                    rating=excluded.rating,
                    review_count=excluded.review_count,
                    starting_price_usd=excluded.starting_price_usd,
                    error=excluded.error,
                    result_json=excluded.result_json
                """,
                (
                    job_id,
                    url,
                    status,
                    result.get("fetched_at") or now,
                    result.get("fetch_method"),
                    result.get("title"),
                    result.get("seller_username"),
                    result.get("seller_name"),
                    result.get("seller_level"),
                    result.get("rating"),
                    result.get("review_count"),
                    result.get("starting_price_usd"),
                    result.get("error"),
                    result_json,
                ),
            )
            connection.execute(
                """
                INSERT INTO gigs (
                    url, title, seller_username, seller_name,
                    first_seen_at, last_seen_at, latest_result_json
                ) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(url) DO UPDATE SET
                    title=COALESCE(excluded.title, gigs.title),
                    seller_username=COALESCE(excluded.seller_username, gigs.seller_username),
                    seller_name=COALESCE(excluded.seller_name, gigs.seller_name),
                    last_seen_at=excluded.last_seen_at,
                    latest_result_json=excluded.latest_result_json
                """,
                (
                    url,
                    result.get("title"),
                    result.get("seller_username"),
                    result.get("seller_name"),
                    now,
                    now,
                    result_json,
                ),
            )

    def get_job_results(
        self, job_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        offset = max(0, int(offset))
        limit = max(1, min(200, int(limit)))
        with self._lock, self._connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM gig_snapshots WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT gs.result_json
                FROM gig_snapshots gs
                LEFT JOIN search_results sr
                  ON sr.job_id=gs.job_id AND sr.url=gs.url
                WHERE gs.job_id=?
                ORDER BY COALESCE(sr.global_position, 999999), gs.url
                LIMIT ? OFFSET ?
                """,
                (job_id, limit, offset),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(json.loads(row["result_json"]))
            except json.JSONDecodeError:
                continue
        return results, int(total)

    def get_all_job_results(self, job_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        offset = 0
        page_size = 200
        while True:
            batch, total = self.get_job_results(job_id, offset=offset, limit=page_size)
            results.extend(batch)
            offset += page_size
            if offset >= total:
                break
        return results

    def get_all_search_results(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM search_results
                WHERE job_id=?
                ORDER BY COALESCE(global_position, 999999), url
                """,
                (job_id,),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["is_sponsored"] = bool(item.get("is_sponsored"))
            item["seller_online"] = bool(item.get("seller_online"))
            try:
                item["badges"] = json.loads(item.pop("badges_json") or "[]")
            except json.JSONDecodeError:
                item["badges"] = []
                item.pop("badges_json", None)
            results.append(item)
        return results

    def get_previous_completed_job(
        self, job_id: str, niche: str
    ) -> dict[str, Any] | None:
        current = self.get_job(job_id)
        if current is None:
            return None
        with self._lock, self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE niche=? AND id<>? AND status='completed' AND created_at < ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (niche, job_id, current["created_at"]),
            ).fetchone()
        return self._job_row(row) if row else None

    def save_analysis(
        self, job_id: str, analysis: dict[str, Any], version: str = "phase2-v2"
    ) -> None:
        generated_at = str(analysis.get("generated_at") or utc_now())
        payload = json.dumps(analysis, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO analysis_snapshots (
                    job_id, version, generated_at, analysis_json
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id, version) DO UPDATE SET
                    generated_at=excluded.generated_at,
                    analysis_json=excluded.analysis_json
                """,
                (job_id, version, generated_at, payload),
            )

    def get_analysis(
        self, job_id: str, version: str | None = None
    ) -> dict[str, Any] | None:
        # Backward compatible: try v2 first, then v1
        versions_to_try = []
        if version:
            versions_to_try = [version]
        else:
            versions_to_try = ["phase2-v2", "phase2-v1"]
        with self._lock, self._connection() as connection:
            for ver in versions_to_try:
                row = connection.execute(
                    """
                    SELECT analysis_json FROM analysis_snapshots
                    WHERE job_id=? AND version=?
                    """,
                    (job_id, ver),
                ).fetchone()
                if row:
                    try:
                        return json.loads(row["analysis_json"])
                    except json.JSONDecodeError:
                        continue
        return None

    def create_ai_run(
        self,
        run_id: str,
        job_id: str,
        *,
        mode: str,
        primary_model: str,
        embedding_model: str,
        deep_model: str,
        max_gigs: int,
        max_cost_usd: float,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO ai_runs (
                    id, job_id, status, stage, mode, provider,
                    primary_model, embedding_model, deep_model,
                    max_gigs, max_cost_usd, created_at, updated_at
                ) VALUES (?, ?, 'queued', 'queued', ?, 'openrouter', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_id,
                    mode,
                    primary_model,
                    embedding_model,
                    deep_model,
                    max_gigs,
                    max_cost_usd,
                    now,
                    now,
                ),
            )
        run = self.get_ai_run(run_id)
        if run is None:
            raise RuntimeError("Created AI run could not be reloaded")
        return run

    def update_ai_run(self, run_id: str, **fields: Any) -> None:
        clean: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in self.AI_RUN_FIELDS:
                raise ValueError(f"Unsupported AI run field: {key}")
            if key == "result_json" and value is not None and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            clean[key] = value
        if not clean:
            return
        clean["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in clean)
        with self._lock, self._connection() as connection:
            connection.execute(
                f"UPDATE ai_runs SET {assignments} WHERE id=?",
                list(clean.values()) + [run_id],
            )

    @staticmethod
    def _ai_run_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        raw = data.pop("result_json", None)
        if raw:
            try:
                data["result"] = json.loads(raw)
            except json.JSONDecodeError:
                data["result"] = None
        else:
            data["result"] = None
        return data

    def get_ai_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM ai_runs WHERE id=?", (run_id,)
            ).fetchone()
        return self._ai_run_row(row) if row else None

    def list_ai_runs(self, job_id: str, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ai_runs WHERE job_id=?
                ORDER BY created_at DESC LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
        return [self._ai_run_row(row) for row in rows]

    def get_ai_cache(self, cache_key: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM ai_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["response"] = json.loads(data.pop("response_json"))
            data["usage"] = json.loads(data.pop("usage_json") or "{}")
        except json.JSONDecodeError:
            return None
        return data

    def save_ai_cache(
        self,
        *,
        cache_key: str,
        kind: str,
        model: str,
        prompt_version: str,
        input_hash: str,
        response: dict[str, Any],
        usage: dict[str, Any],
        cost_usd: float,
    ) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO ai_cache (
                    cache_key, kind, model, prompt_version, input_hash,
                    response_json, usage_json, cost_usd, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json=excluded.response_json,
                    usage_json=excluded.usage_json,
                    cost_usd=excluded.cost_usd,
                    created_at=excluded.created_at
                """,
                (
                    cache_key,
                    kind,
                    model,
                    prompt_version,
                    input_hash,
                    json.dumps(response, ensure_ascii=False),
                    json.dumps(usage, ensure_ascii=False),
                    float(cost_usd),
                    utc_now(),
                ),
            )

    def get_embedding_cache(self, cache_key: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM embedding_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["vector"] = json.loads(data.pop("vector_json"))
            data["usage"] = json.loads(data.pop("usage_json") or "{}")
        except json.JSONDecodeError:
            return None
        return data

    def save_embedding_cache(
        self,
        *,
        cache_key: str,
        model: str,
        input_hash: str,
        vector: list[float],
        usage: dict[str, Any],
        cost_usd: float,
    ) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO embedding_cache (
                    cache_key, model, input_hash, vector_json,
                    usage_json, cost_usd, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    vector_json=excluded.vector_json,
                    usage_json=excluded.usage_json,
                    cost_usd=excluded.cost_usd,
                    created_at=excluded.created_at
                """,
                (
                    cache_key,
                    model,
                    input_hash,
                    json.dumps(vector),
                    json.dumps(usage, ensure_ascii=False),
                    float(cost_usd),
                    utc_now(),
                ),
            )

    def create_generation_run(
        self,
        run_id: str,
        job_id: str,
        *,
        ai_run_id: str | None,
        mode: str,
        target_gig_url: str | None,
        preferences: dict[str, Any],
        primary_model: str,
        deep_model: str,
        max_cost_usd: float,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO generation_runs (
                    id, job_id, ai_run_id, status, stage, mode,
                    target_gig_url, preferences_json, primary_model,
                    deep_model, max_cost_usd, created_at, updated_at
                ) VALUES (?, ?, ?, 'queued', 'queued', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_id,
                    ai_run_id,
                    mode,
                    target_gig_url,
                    json.dumps(preferences, ensure_ascii=False),
                    primary_model,
                    deep_model,
                    float(max_cost_usd),
                    now,
                    now,
                ),
            )
        run = self.get_generation_run(run_id)
        if run is None:
            raise RuntimeError("Created generation run could not be reloaded")
        return run

    def update_generation_run(self, run_id: str, **fields: Any) -> None:
        clean: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in self.GENERATION_RUN_FIELDS:
                raise ValueError(f"Unsupported generation field: {key}")
            if key == "result_json" and value is not None and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            clean[key] = value
        if not clean:
            return
        clean["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in clean)
        with self._lock, self._connection() as connection:
            connection.execute(
                f"UPDATE generation_runs SET {assignments} WHERE id=?",
                list(clean.values()) + [run_id],
            )

    @staticmethod
    def _generation_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["preferences"] = json.loads(data.pop("preferences_json") or "{}")
        except json.JSONDecodeError:
            data["preferences"] = {}
            data.pop("preferences_json", None)
        raw = data.pop("result_json", None)
        if raw:
            try:
                data["result"] = json.loads(raw)
            except json.JSONDecodeError:
                data["result"] = None
        else:
            data["result"] = None
        return data

    def get_generation_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM generation_runs WHERE id=?", (run_id,)
            ).fetchone()
        return self._generation_row(row) if row else None

    def list_generation_runs(
        self, job_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM generation_runs WHERE job_id=?
                ORDER BY created_at DESC LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
        return [self._generation_row(row) for row in rows]

    def create_simple_workflow(
        self,
        workflow_id: str,
        *,
        niche: str,
        quality: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO simple_workflows (
                    id, niche, quality, inputs_json, status, stage,
                    message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', 'queued', ?, ?, ?)
                """,
                (
                    workflow_id,
                    niche,
                    quality,
                    json.dumps(inputs, ensure_ascii=False),
                    "Waiting to start",
                    now,
                    now,
                ),
            )
        workflow = self.get_simple_workflow(workflow_id)
        if workflow is None:
            raise RuntimeError("Created workflow could not be reloaded")
        return workflow

    def update_simple_workflow(self, workflow_id: str, **fields: Any) -> None:
        clean: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in self.WORKFLOW_FIELDS:
                raise ValueError(f"Unsupported workflow field: {key}")
            if key == "warnings_json" and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            clean[key] = value
        if not clean:
            return
        clean["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in clean)
        with self._lock, self._connection() as connection:
            connection.execute(
                f"UPDATE simple_workflows SET {assignments} WHERE id=?",
                list(clean.values()) + [workflow_id],
            )

    @staticmethod
    def _simple_workflow_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["inputs"] = json.loads(data.pop("inputs_json") or "{}")
        except json.JSONDecodeError:
            data["inputs"] = {}
            data.pop("inputs_json", None)
        try:
            data["warnings"] = json.loads(data.pop("warnings_json") or "[]")
        except json.JSONDecodeError:
            data["warnings"] = []
            data.pop("warnings_json", None)
        return data

    def get_simple_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM simple_workflows WHERE id=?", (workflow_id,)
            ).fetchone()
        return self._simple_workflow_row(row) if row else None

    def count_search_results(self, job_id: str) -> int:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM search_results WHERE job_id=?", (job_id,)
            ).fetchone()
        return int(row[0]) if row else 0
