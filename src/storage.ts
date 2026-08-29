import fs from "fs";
import path from "path";
import {
  JobRecord,
  GigResult,
  AIRunRecord,
  GenerationRunRecord,
  SimpleWorkflowRecord,
} from "./types.js";

export function utcNow(): string {
  return new Date().toISOString();
}

export class Storage {
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

  constructor(baseDataDir?: string) {
    this.dataDir = baseDataDir || path.join(process.cwd(), "data");
    this.exportsDir = path.join(this.dataDir, "exports");
    try {
      fs.mkdirSync(this.exportsDir, { recursive: true });
    } catch {
      // ignore
    }
  }

  getExportsDir(): string {
    return this.exportsDir;
  }

  // Job management
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
    return job;
  }

  saveGigResult(jobId: string, result: GigResult): void {
    const list = this.jobResults.get(jobId) || [];
    list.push(result);
    this.jobResults.set(jobId, list);
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
  }

  getAnalysis(jobId: string): any | undefined {
    return this.jobAnalyses.get(jobId);
  }

  // AI Runs
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
    return run;
  }

  saveAIResult(id: string, result: any): void {
    this.aiResults.set(id, result);
  }

  getAIResult(id: string): any | undefined {
    return this.aiResults.get(id);
  }

  // Generation runs
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
    return run;
  }

  saveGenerationResult(id: string, result: any, markdownContent?: string): void {
    this.generationResults.set(id, result);
    if (markdownContent) {
      this.generationMarkdowns.set(id, markdownContent);
    }
  }

  getGenerationResult(id: string): any | undefined {
    return this.generationResults.get(id);
  }

  getGenerationMarkdown(id: string): string | undefined {
    return this.generationMarkdowns.get(id);
  }

  // Simple Workflows
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
    return flow;
  }

  // Export writers
  writeJobExports(jobId: string, niche: string, gigs: GigResult[]): void {
    try {
      const jsonPath = path.join(this.exportsDir, `${jobId}-gigs.json`);
      fs.writeFileSync(jsonPath, JSON.stringify(gigs, null, 2), "utf8");

      // Write CSV
      const csvPath = path.join(this.exportsDir, `${jobId}-gigs.csv`);
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
      const rows = gigs.map((g) => [
        g.search?.global_position || "",
        `"${(g.title || "").replace(/"/g, '""')}"`,
        `"${(g.seller_name || g.seller_username || "").replace(/"/g, '""')}"`,
        `"${(g.seller_level || "").replace(/"/g, '""')}"`,
        `"${(g.seller_country || "").replace(/"/g, '""')}"`,
        g.starting_price_usd ?? "",
        g.rating ?? "",
        g.review_count ?? "",
        g.search?.seller_online ? "Yes" : "No",
        g.has_video ? "Yes" : "No",
        `"${(g.related_tags || []).join(", ").replace(/"/g, '""')}"`,
        `"${(g.url || "").replace(/"/g, '""')}"`,
      ]);

      const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
      fs.writeFileSync(csvPath, csvContent, "utf8");
    } catch {
      // ignore
    }
  }
}

export const storage = new Storage();
