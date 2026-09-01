import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Storage } from "../src/storage.js";
import { SimpleWorkflowRunner } from "../src/simple_workflow.js";

test("workflow propagates crawl sample-fallback warnings to the record (UI banner source)", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-wf-"));
  const storage = new Storage(dir);
  const workflowId = "wf_test";
  storage.createSimpleWorkflow(workflowId, "logo design", "fast", {});

  // Fake crawler: simulates the labelled sample fallback (live fetch failed).
  const fakeCrawler: any = {
    async runJob(jobId: string) {
      storage.saveGigResult(jobId, {
        url: "https://www.fiverr.com/x/y",
        title: "sample gig",
        seller_name: "Sample Seller",
        search: { niche: "logo design", global_position: 1, seller_online: true },
      } as any);
      storage.updateJob(jobId, {
        status: "completed",
        stage: "completed",
        progress_percent: 100,
        discovered_count: 1,
        processed_count: 1,
        success_count: 1,
        failed_count: 0,
        discovery_source: "Illustrative sample (live Fiverr fetch unavailable — showing demo data)",
        warnings: [
          "Live crawl failed: Reader request failed after retries: fetch failed",
          "Live Fiverr data was unavailable (network blocked or reader returned no listings); showing an illustrative simulated sample, not real listings.",
        ],
        finished_at: new Date().toISOString(),
      });
    },
  };

  // Fake AI engine: no-op stages (no LLM involved in this test).
  const fakeAi: any = {
    async runSemanticAudit(runId: string) {
      storage.updateAIRun(runId, { status: "completed", stage: "done", progress_percent: 100 });
    },
    async runGigGeneration(runId: string) {
      storage.saveGenerationResult(runId, { run_id: runId, title: "t", description: "d" });
      storage.updateGenerationRun(runId, { status: "completed", stage: "done", progress_percent: 100 });
    },
  };

  const runner = new SimpleWorkflowRunner(storage, fakeCrawler, fakeAi);
  await runner.runWorkflow(workflowId);

  const flow = storage.getSimpleWorkflow(workflowId)!;
  assert.ok(flow.status === "completed" || flow.status === "ready", `flow status: ${flow.status}`);
  // The crawl's sample-fallback warnings must reach the workflow record so
  // the UI can render the prominent SAMPLE DATA banner.
  assert.ok(flow.warnings.length >= 2, `expected propagated warnings, got: ${JSON.stringify(flow.warnings)}`);
  assert.ok(flow.warnings.some((w) => /illustrative simulated sample/i.test(w)));
});
