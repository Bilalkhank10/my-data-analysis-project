import { Storage, utcNow, storage } from "./storage.js";
import { FiverrCrawler, crawler } from "./crawler.js";
import { AIEngine, aiEngine } from "./ai_engine.js";

export class SimpleWorkflowRunner {
  private storage: Storage;
  private crawler: FiverrCrawler;
  private aiEngine: AIEngine;

  constructor(storage: Storage, crawler: FiverrCrawler, aiEngine: AIEngine) {
    this.storage = storage;
    this.crawler = crawler;
    this.aiEngine = aiEngine;
  }

  async runWorkflow(workflowId: string): Promise<void> {
    const flow = this.storage.getSimpleWorkflow(workflowId);
    if (!flow) return;

    try {
      this.storage.updateSimpleWorkflow(workflowId, {
        status: "running",
        stage: "research",
        message: "Researching market opportunities and active Fiverr listings...",
        progress_percent: 15,
      });

      // 1. Stage 1: Market Research (Crawl)
      const jobId = `job_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      const gigLimit = flow.quality === "fast" ? 12 : flow.quality === "recommended" ? 24 : 36;
      this.storage.createJob(jobId, flow.niche, gigLimit);
      this.storage.updateSimpleWorkflow(workflowId, { job_id: jobId });

      await this.crawler.runJob(jobId);

      // Propagate the crawl job's data-source warnings (e.g. the labelled
      // sample fallback) into the workflow record so the UI can display a
      // prominent banner instead of showing sample data silently.
      const crawlJob = this.storage.getJob(jobId);
      if (crawlJob?.warnings?.length) {
        const currentFlow = this.storage.getSimpleWorkflow(workflowId);
        this.storage.updateSimpleWorkflow(workflowId, {
          warnings: Array.from(new Set([...(currentFlow?.warnings || []), ...crawlJob.warnings])),
        });
      }

      this.storage.updateSimpleWorkflow(workflowId, {
        stage: "understand",
        message: "Auditing keyword clusters, buyer intent, and competitor weaknesses...",
        progress_percent: 55,
      });

      // 2. Stage 2: Understand / Semantic Audit
      const aiRunId = `ai_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      this.storage.createAIRun(aiRunId, jobId, "dry_run", 12);
      this.storage.updateSimpleWorkflow(workflowId, { ai_run_id: aiRunId });

      await this.aiEngine.runSemanticAudit(aiRunId);

      this.storage.updateSimpleWorkflow(workflowId, {
        stage: "build",
        message: "Drafting high-converting title, 3-tier packages, FAQs, and visual script...",
        progress_percent: 85,
      });

      // 3. Stage 3: Build Gig
      const genRunId = `gen_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      this.storage.createGenerationRun(genRunId, jobId, "standard");
      this.storage.updateSimpleWorkflow(workflowId, {
        generation_run_id: genRunId,
        markdown_url: `/api/generation-runs/${genRunId}/export.md`,
      });

      // language is the OUTPUT language of the gig copy (previously it was
      // mis-fed into "experience level" in the prompt).
      await this.aiEngine.runGigGeneration(genRunId, {
        custom_angle: flow.inputs?.buyer,
        target_price: "market_aligned",
        experience_level: "experienced professional",
        language: flow.inputs?.language,
      });

      this.storage.updateSimpleWorkflow(workflowId, {
        status: "completed",
        stage: "ready",
        message: "Your optimized gig draft is complete and ready to publish!",
        progress_percent: 100,
        finished_at: utcNow(),
      });
    } catch (err: any) {
      console.error("Simple workflow failed:", err);
      this.storage.updateSimpleWorkflow(workflowId, {
        status: "failed",
        error: err?.message || "Workflow execution failed",
        finished_at: utcNow(),
      });
    }
  }
}

export const simpleWorkflowRunner = new SimpleWorkflowRunner(storage, crawler, aiEngine.rawEngine);

export const simpleWorkflowManager = {
  startWorkflow(params: {
    niche: string;
    quality?: string;
    buyer?: string;
    language?: string;
    existing_url?: string | null;
  }) {
    const id = `wf_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const quality = (["fast", "recommended", "best"].includes(params.quality || "")
      ? params.quality
      : "recommended") as "fast" | "recommended" | "best";
    const flow = storage.createSimpleWorkflow(id, params.niche, quality, params);
    setTimeout(() => {
      simpleWorkflowRunner.runWorkflow(id).catch((e) => console.error("Workflow error:", e));
    }, 50);
    return flow;
  },

  getWorkflow(id: string) {
    return storage.getSimpleWorkflow(id);
  },

  getWorkflowResult(id: string) {
    const flow = storage.getSimpleWorkflow(id);
    if (!flow || !flow.generation_run_id) return undefined;
    return storage.getGenerationResult(flow.generation_run_id);
  },
};

