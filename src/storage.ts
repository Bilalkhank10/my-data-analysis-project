import fs from "fs";
import path from "path";
import { DatabaseSync } from "node:sqlite";
import {
  JobRecord,
  GigResult,
  AIRunRecord,
  GenerationRunRecord,
  SimpleWorkflowRecord,
} from "./types.js";
import { csvCell } from "./csv.js";

export function utcNow(): string {
  return new Date().toISOString();
}

/** Fields stripped from on-disk JSON exports (large, session-only payloads). */
const EXPORT_STRIP_FIELDS = ["raw_visible_text", "reviews_text", "faq_text", "packages_text", "json_ld"];

/**
 * Remove bulky session-only fields (full page text etc.) from a gig record.
 * Shared by exports, the results API and dynamic downloads so none of them
 * ship multi-MB text blobs to clients.
 */
export function stripBulkyFields(gig: GigResult): Record<string, any> {
  if (typeof gig !== "object" || gig === null) return gig as any;
  const out: Record<string, any> = { ...(gig as any) };
  for (const f of EXPORT_STRIP_FIELDS) delete out[f];
  return out;
}

function stripForExport(gig: GigResult): Record<string, any> {
  return stripBulkyFields(gig);
}

/**
 * Storage layer: in-memory caches + SQLite write-through persistence.
 *
 * - Jobs/results/analyses/AI runs/generation runs/workflows survive restarts.
 * - Per-niche rank snapshots power real rank-movement comparisons.
 * - A small reader cache avoids re-hitting Jina for the same URL within TTL.
 * - Bounded job count prevents unbounded in-memory growth.
 */
export class Storage {
  private db: DatabaseSync;
  private jobs: Map<string, JobRecord> = new Map();
  private jobResults: Map<string, GigResult[]> = new Map();
  private jobAnalyses: Map<string, any> = new Map();
  private aiRuns: Map<string, AIRunRecord> = new Map();
  private aiResults: Map<string, any> = new Map();
  private generationRuns: Map<string, GenerationRunRecord> = new Map();
  private generationResults: Map<string, any> = new Map();
  private generationMarkdowns: Map<string, string> = new Map();
  private simpleWorkflows: Map<string, SimpleWorkflowRecord> = new Map();
  private dataDir: string;
  private exportsDir: string;
  private maxJobs: number;

  constructor(baseDataDir?: string) {
    this.dataDir = baseDataDir || process.env.DATA_DIR || path.join(process.cwd(), "data");
    this.exportsDir = path.join(this.dataDir, "exports");
    try {
      fs.mkdirSync(this.exportsDir, { recursive: true });
    } catch {
      // ignore
    }
    this.maxJobs = Math.max(5, Number(process.env.MAX_JOBS) || 50);

    this.db = new DatabaseSync(path.join(this.dataDir, "gigcraft.db"));
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS job_results (
        job_id TEXT NOT NULL, seq INTEGER NOT NULL, url TEXT,
        data TEXT NOT NULL, PRIMARY KEY (job_id, seq)
      );
      CREATE TABLE IF NOT EXISTS job_analyses (job_id TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS ai_runs (id TEXT PRIMARY KEY, job_id TEXT, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS ai_results (id TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS generation_runs (id TEXT PRIMARY KEY, job_id TEXT, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS generation_results (id TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS generation_markdowns (id TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS simple_workflows (id TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS rank_snapshots (
        niche TEXT NOT NULL, job_id TEXT NOT NULL, captured_at TEXT NOT NULL,
        data TEXT NOT NULL, PRIMARY KEY (niche, job_id)
      );
      CREATE TABLE IF NOT EXISTS reader_cache (
        url TEXT PRIMARY KEY, markdown TEXT NOT NULL, fetched_at TEXT NOT NULL
      );
    `);
    this.hydrate();
  }

  // -------------------------------------------------------------------------
  // Hydration (load persisted state into memory on boot)
  // -------------------------------------------------------------------------

  private hydrate(): void {
    const all = <T>(rows: any[], key: string): T[] =>
      rows.map((r) => JSON.parse(r.data)) as T[];

    for (const job of all<JobRecord>(this.db.prepare("SELECT data FROM jobs").all(), "data")) {
      this.jobs.set(job.id, job);
      this.jobResults.set(job.id, []);
    }
    const resultRows = this.db
      .prepare("SELECT job_id, data FROM job_results ORDER BY job_id, seq")
      .all();
    for (const r of resultRows as any[]) {
      const list = this.jobResults.get(r.job_id) || [];
      list.push(JSON.parse(r.data));
      this.jobResults.set(r.job_id, list);
    }
    for (const row of this.db.prepare("SELECT job_id, data FROM job_analyses").all() as any[]) {
      this.jobAnalyses.set(row.job_id, JSON.parse(row.data));
    }
    for (const row of this.db.prepare("SELECT data FROM ai_runs").all() as any[]) {
      const run = JSON.parse(row.data) as AIRunRecord;
      this.aiRuns.set(run.id, run);
    }
    for (const row of this.db.prepare("SELECT id, data FROM ai_results").all() as any[]) {
      this.aiResults.set(row.id, JSON.parse(row.data));
    }
    for (const row of this.db.prepare("SELECT data FROM generation_runs").all() as any[]) {
      const run = JSON.parse(row.data) as GenerationRunRecord;
      this.generationRuns.set(run.id, run);
    }
    for (const row of this.db.prepare("SELECT id, data FROM generation_results").all() as any[]) {
      this.generationResults.set(row.id, JSON.parse(row.data));
    }
    for (const row of this.db.prepare("SELECT id, data FROM generation_markdowns").all() as any[]) {
      this.generationMarkdowns.set(row.id, row.data);
    }
    for (const row of this.db.prepare("SELECT data FROM simple_workflows").all() as any[]) {
      const flow = JSON.parse(row.data) as SimpleWorkflowRecord;
      this.simpleWorkflows.set(flow.id, flow);
    }
  }

  private persistRow(table: string, id: string | undefined, data: any): void {
    if (id === undefined) return;
    this.db.prepare(`INSERT OR REPLACE INTO ${table} (id, data) VALUES (?, ?)`).run(id, JSON.stringify(data));
  }

  getExportsDir(): string {
    return this.exportsDir;
  }

  // -------------------------------------------------------------------------
  // Job management
  // -------------------------------------------------------------------------

  createJob(id: string, niche: string, limit: number): JobRecord {
    const job: JobRecord = {
      id,
      niche,
      limit,
      status: "queued",
      stage: "queued",
      progress_percent: 0,
      pages_scanned: 0,
      available_results: 0,
      discovered_count: 0,
      processed_count: 0,
      success_count: 0,
      failed_count: 0,
      discovery_source: "Initializing...",
      started_at: utcNow(),
      warnings: [],
      downloads: {
        json: `/download/${id}-gigs.json`,
        csv: `/download/${id}-gigs.csv`,
      },
    };
    this.jobs.set(id, job);
    this.jobResults.set(id, []);
    this.persistRow("jobs", id, job);
    this.evictOldestFinishedJobs();
    return job;
  }

  getJob(id: string): JobRecord | undefined {
    return this.jobs.get(id);
  }

  listJobs(limit: number = 20): JobRecord[] {
    const all = Array.from(this.jobs.values()).sort((a, b) =>
      (b.started_at || "").localeCompare(a.started_at || "")
    );
    return all.slice(0, limit);
  }

  updateJob(id: string, updates: Partial<JobRecord>): JobRecord | undefined {
    const job = this.jobs.get(id);
    if (!job) return undefined;
    Object.assign(job, updates);
    this.jobs.set(id, job);
    this.persistRow("jobs", id, job);
    return job;
  }

  private evictOldestFinishedJobs(): void {
    if (this.jobs.size < this.maxJobs) return;
    const finished = Array.from(this.jobs.values())
      .filter((j) => j.status === "completed" || j.status === "failed" || j.status === "cancelled")
      .sort((a, b) => (a.started_at || "").localeCompare(b.started_at || ""));
    for (const job of finished) {
      if (this.jobs.size < this.maxJobs) break;
      this.deleteJob(job.id);
    }
  }

  deleteJob(id: string): void {
    this.jobs.delete(id);
    this.jobResults.delete(id);
    this.jobAnalyses.delete(id);
    this.db.prepare("DELETE FROM jobs WHERE id = ?").run(id);
    this.db.prepare("DELETE FROM job_results WHERE job_id = ?").run(id);
    this.db.prepare("DELETE FROM job_analyses WHERE job_id = ?").run(id);
    // Runs belong to the job; drop them too (bounded memory).
    for (const run of Array.from(this.aiRuns.values())) {
      if (run.job_id === id) {
        this.aiRuns.delete(run.id);
        this.aiResults.delete(run.id);
        this.db.prepare("DELETE FROM ai_runs WHERE id = ?").run(run.id);
        this.db.prepare("DELETE FROM ai_results WHERE id = ?").run(run.id);
      }
    }
    for (const run of Array.from(this.generationRuns.values())) {
      if (run.job_id === id) {
        this.generationRuns.delete(run.id);
        this.generationResults.delete(run.id);
        this.generationMarkdowns.delete(run.id);
        this.db.prepare("DELETE FROM generation_runs WHERE id = ?").run(run.id);
        this.db.prepare("DELETE FROM generation_results WHERE id = ?").run(run.id);
        this.db.prepare("DELETE FROM generation_markdowns WHERE id = ?").run(run.id);
      }
    }
  }

  saveGigResult(jobId: string, result: GigResult): void {
    const list = this.jobResults.get(jobId) || [];
    list.push(result);
    this.jobResults.set(jobId, list);
    this.db
      .prepare("INSERT INTO job_results (job_id, seq, url, data) VALUES (?, ?, ?, ?)")
      .run(jobId, list.length - 1, result.url || "", JSON.stringify(result));
  }

  getJobResults(
    jobId: string,
    offset: number = 0,
    limit: number = 20
  ): { results: GigResult[]; total: number } {
    const list = this.jobResults.get(jobId) || [];
    return {
      results: list.slice(offset, offset + limit),
      total: list.length,
    };
  }

  getAllJobResults(jobId: string): GigResult[] {
    return this.jobResults.get(jobId) || [];
  }

  saveAnalysis(jobId: string, analysis: any): void {
    this.jobAnalyses.set(jobId, analysis);
    this.db.prepare("INSERT OR REPLACE INTO job_analyses (job_id, data) VALUES (?, ?)").run(
      jobId,
      JSON.stringify(analysis)
    );
  }

  getAnalysis(jobId: string): any | undefined {
    return this.jobAnalyses.get(jobId);
  }

  // -------------------------------------------------------------------------
  // AI Runs
  // -------------------------------------------------------------------------

  createAIRun(
    id: string,
    jobId: string,
    mode: "dry_run" | "test" | "standard" | "deep",
    selectedGigs: number
  ): AIRunRecord {
    const run: AIRunRecord = {
      id,
      job_id: jobId,
      mode,
      status: "queued",
      stage: "queued",
      progress_percent: 0,
      selected_gigs: selectedGigs,
      processed_gigs: 0,
      total_tokens: 0,
      actual_cost_usd: 0,
      started_at: utcNow(),
      result_url: `/api/ai-runs/${id}/result`,
    };
    this.aiRuns.set(id, run);
    this.db.prepare("INSERT OR REPLACE INTO ai_runs (id, job_id, data) VALUES (?, ?, ?)").run(
      id,
      jobId,
      JSON.stringify(run)
    );
    return run;
  }

  getAIRun(id: string): AIRunRecord | undefined {
    return this.aiRuns.get(id);
  }

  listAIRuns(jobId: string, limit: number = 20): AIRunRecord[] {
    return Array.from(this.aiRuns.values())
      .filter((r) => r.job_id === jobId)
      .sort((a, b) => (b.started_at || "").localeCompare(a.started_at || ""))
      .slice(0, limit);
  }

  updateAIRun(id: string, updates: Partial<AIRunRecord>): AIRunRecord | undefined {
    const run = this.aiRuns.get(id);
    if (!run) return undefined;
    Object.assign(run, updates);
    this.aiRuns.set(id, run);
    this.db.prepare("UPDATE ai_runs SET data = ? WHERE id = ?").run(JSON.stringify(run), id);
    return run;
  }

  saveAIResult(id: string, result: any): void {
    result.run_id = id;
    this.aiResults.set(id, result);
    this.db.prepare("INSERT OR REPLACE INTO ai_results (id, data) VALUES (?, ?)").run(id, JSON.stringify(result));
  }

  getAIResult(id: string): any | undefined {
    return this.aiResults.get(id);
  }

  // -------------------------------------------------------------------------
  // Generation runs
  // -------------------------------------------------------------------------

  createGenerationRun(
    id: string,
    jobId: string,
    mode: "dry_run" | "test" | "standard" | "deep"
  ): GenerationRunRecord {
    const run: GenerationRunRecord = {
      id,
      job_id: jobId,
      mode,
      status: "queued",
      stage: "queued",
      progress_percent: 0,
      approval_status: "draft",
      total_tokens: 0,
      actual_cost_usd: 0,
      started_at: utcNow(),
      result_url: `/api/generation-runs/${id}/result`,
      markdown_url: `/api/generation-runs/${id}/export.md`,
    };
    this.generationRuns.set(id, run);
    this.db.prepare("INSERT OR REPLACE INTO generation_runs (id, job_id, data) VALUES (?, ?, ?)").run(
      id,
      jobId,
      JSON.stringify(run)
    );
    return run;
  }

  getGenerationRun(id: string): GenerationRunRecord | undefined {
    return this.generationRuns.get(id);
  }

  listGenerationRuns(jobId: string, limit: number = 20): GenerationRunRecord[] {
    return Array.from(this.generationRuns.values())
      .filter((r) => r.job_id === jobId)
      .sort((a, b) => (b.started_at || "").localeCompare(a.started_at || ""))
      .slice(0, limit);
  }

  updateGenerationRun(
    id: string,
    updates: Partial<GenerationRunRecord>
  ): GenerationRunRecord | undefined {
    const run = this.generationRuns.get(id);
    if (!run) return undefined;
    Object.assign(run, updates);
    this.generationRuns.set(id, run);
    this.db.prepare("UPDATE generation_runs SET data = ? WHERE id = ?").run(JSON.stringify(run), id);
    return run;
  }

  saveGenerationResult(id: string, result: any, markdownContent?: string): void {
    result.run_id = id;
    this.generationResults.set(id, result);
    this.db.prepare("INSERT OR REPLACE INTO generation_results (id, data) VALUES (?, ?)").run(
      id,
      JSON.stringify(result)
    );
    if (markdownContent) {
      this.generationMarkdowns.set(id, markdownContent);
      this.db.prepare("INSERT OR REPLACE INTO generation_markdowns (id, data) VALUES (?, ?)").run(
        id,
        markdownContent
      );
    }
  }

  getGenerationResult(id: string): any | undefined {
    return this.generationResults.get(id);
  }

  getGenerationMarkdown(id: string): string | undefined {
    return this.generationMarkdowns.get(id);
  }

  // -------------------------------------------------------------------------
  // Simple Workflows
  // -------------------------------------------------------------------------

  createSimpleWorkflow(
    id: string,
    niche: string,
    quality: "fast" | "recommended" | "best",
    inputs: Record<string, any>
  ): SimpleWorkflowRecord {
    const flow: SimpleWorkflowRecord = {
      id,
      niche,
      quality,
      status: "queued",
      stage: "research",
      message: "Preparing research workflow...",
      progress_percent: 1,
      inputs,
      warnings: [],
      started_at: utcNow(),
    };
    this.simpleWorkflows.set(id, flow);
    this.persistRow("simple_workflows", id, flow);
    return flow;
  }

  getSimpleWorkflow(id: string): SimpleWorkflowRecord | undefined {
    return this.simpleWorkflows.get(id);
  }

  updateSimpleWorkflow(
    id: string,
    updates: Partial<SimpleWorkflowRecord>
  ): SimpleWorkflowRecord | undefined {
    const flow = this.simpleWorkflows.get(id);
    if (!flow) return undefined;
    Object.assign(flow, updates);
    this.simpleWorkflows.set(id, flow);
    this.persistRow("simple_workflows", id, flow);
    return flow;
  }

  // -------------------------------------------------------------------------
  // Rank snapshots (real rank-movement history per niche)
  // -------------------------------------------------------------------------

  saveRankSnapshot(niche: string, jobId: string, gigs: GigResult[]): void {
    const ranks = gigs
      .filter((g) => !g.error && g.url && g.search?.global_position)
      .map((g) => ({ url: g.url, rank: g.search!.global_position! }));
    if (!ranks.length) return;
    this.db
      .prepare("INSERT OR REPLACE INTO rank_snapshots (niche, job_id, captured_at, data) VALUES (?, ?, ?, ?)")
      .run(niche, jobId, utcNow(), JSON.stringify(ranks));
    // Keep only the 5 most recent snapshots per niche.
    const rows = this.db
      .prepare("SELECT job_id FROM rank_snapshots WHERE niche = ? ORDER BY captured_at DESC, job_id DESC LIMIT -1 OFFSET 5")
      .all(niche) as any[];
    for (const row of rows) {
      this.db.prepare("DELETE FROM rank_snapshots WHERE niche = ? AND job_id = ?").run(niche, row.job_id);
    }
  }

  /** Most recent snapshot for a niche that is NOT the current job. */
  getPreviousSnapshot(niche: string, excludeJobId: string): { url: string; rank: number; captured_at: string }[] | null {
    const rows = this.db
      .prepare(
        "SELECT data, captured_at FROM rank_snapshots WHERE niche = ? AND job_id != ? ORDER BY captured_at DESC, job_id DESC LIMIT 1"
      )
      .all(niche, excludeJobId) as any[];
    if (!rows.length) return null;
    const ranks = JSON.parse(rows[0].data);
    return ranks.map((r: any) => ({ ...r, captured_at: rows[0].captured_at }));
  }

  // -------------------------------------------------------------------------
  // Reader cache (avoid re-hitting Jina for URLs crawled recently)
  // -------------------------------------------------------------------------

  getReaderCache(url: string, ttlMs: number): string | null {
    if (ttlMs <= 0) return null; // non-positive TTL = cache disabled
    const row = this.db.prepare("SELECT markdown, fetched_at FROM reader_cache WHERE url = ?").get(url) as
      | { markdown: string; fetched_at: string }
      | undefined;
    if (!row) return null;
    const age = Date.now() - new Date(row.fetched_at).getTime();
    if (!Number.isFinite(age) || age > ttlMs) return null;
    return row.markdown;
  }

  setReaderCache(url: string, markdown: string): void {
    this.db
      .prepare("INSERT OR REPLACE INTO reader_cache (url, markdown, fetched_at) VALUES (?, ?, ?)")
      .run(url, markdown, utcNow());
    // Bound the cache: drop the oldest entries beyond 500.
    const row = this.db.prepare("SELECT COUNT(*) AS n FROM reader_cache").get() as any;
    if (row && row.n > 500) {
      this.db
        .prepare("DELETE FROM reader_cache WHERE url IN (SELECT url FROM reader_cache ORDER BY fetched_at ASC LIMIT -1 OFFSET 400)")
        .run();
    }
  }

  // -------------------------------------------------------------------------
  // Export writers (CSV sanitized, bulky fields stripped from JSON)
  // -------------------------------------------------------------------------

  writeJobExports(jobId: string, niche: string, gigs: GigResult[]): void {
    try {
      const safeGigs = gigs.map(stripForExport);
      const jsonPath = path.join(this.exportsDir, `${jobId}-gigs.json`);
      fs.writeFileSync(jsonPath, JSON.stringify({ niche, exported_at: utcNow(), gigs: safeGigs }, null, 2), "utf8");

      const headers = [
        "rank",
        "title",
        "seller",
        "seller_level",
        "seller_country",
        "price_usd",
        "rating",
        "reviews",
        "online",
        "video",
        "tags",
        "url",
      ];
      const rows = safeGigs.map((g: any) => [
        g.search?.global_position || "",
        g.title || "",
        g.seller_name || g.seller_username || "",
        g.seller_level || "",
        g.seller_country || "",
        g.starting_price_usd ?? "",
        g.rating ?? "",
        g.review_count ?? "",
        g.search?.seller_online ? "Yes" : "No",
        g.has_video ? "Yes" : "No",
        (g.related_tags || []).join(", "),
        g.url || "",
      ]);
      const csvContent = [headers, ...rows].map((r) => r.map(csvCell).join(",")).join("\n");
      fs.writeFileSync(path.join(this.exportsDir, `${jobId}-gigs.csv`), csvContent, "utf8");
    } catch (err) {
      console.error("Failed to write job exports:", err);
    }
  }
}

export const storage = new Storage();
