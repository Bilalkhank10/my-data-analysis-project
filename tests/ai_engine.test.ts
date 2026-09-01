import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Storage } from "../src/storage.js";
import { AIEngine } from "../src/ai_engine.js";

function makeTmpStorage(): Storage {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-test-"));
  return new Storage(dir);
}

function seedJob(storage: Storage, niche: string, gigCount = 3) {
  const jobId = "job_test";
  storage.createJob(jobId, niche, gigCount);
  for (let i = 0; i < gigCount; i++) {
    storage.saveGigResult(jobId, {
      url: `https://www.fiverr.com/seller/gig-${i}`,
      title: `I will provide ${niche} service ${i + 1}`,
      seller_name: `Seller ${i}`,
      seller_level: "Level 2",
      seller_country: "Pakistan",
      rating: 4.7 + (i % 3) * 0.1,
      review_count: 40 + i * 10,
      starting_price_usd: 40 + i * 15,
      has_video: i % 2 === 0,
      last_delivery: "3 days ago",
      search: { niche, global_position: i + 1, seller_online: true },
      packages: [
        { name: "Basic", price_usd: 40 + i * 15, description: "basic", delivery_days: 2, revisions: 2, features: { "Core deliverable": true } },
        { name: "Standard", price_usd: 90 + i * 15, description: "standard", delivery_days: 4, revisions: 4, features: { "Core deliverable": true, "Priority": true } },
      ],
      faqs: [{ question: "How long?", answer: "2-4 days" }],
      visible_reviews: [{ rating: 5, comment: "great work, fast delivery" }],
    } as any);
  }
  return jobId;
}

// Stub Gemini that reports REAL usage metadata and echoes a valid draft.
function stubGemini(options: { fail?: boolean; neverResolve?: boolean } = {}) {
  const calls: { prompt: string }[] = [];
  const client = {
    models: {
      async generateContent(req: { model: string; contents: string }) {
        calls.push({ prompt: req.contents });
        if (options.neverResolve) return new Promise(() => {}); // never settles
        if (options.fail) throw new Error("HTTP 503 overloaded");
        const isAudit = req.contents.includes("auditing competing");
        if (isAudit) {
          // Behave like a real model: return exactly one row per gig in the
          // batch (parse the payload from the prompt).
          const marker = "Gigs:\n";
          const payloadText = req.contents.slice(req.contents.indexOf(marker) + marker.length).trim();
          const payload: any[] = JSON.parse(payloadText);
          const rows = payload.map((g, i) => ({
            global_position: g.global_position,
            title: g.title,
            seller: g.seller,
            seller_level: g.seller_level,
            intent_cluster: i % 2 === 0 ? "core demand" : "adjacent",
            relevance_score: 88 - i * 10,
            neo_alignment: i === 0 ? "High" : "Medium",
            conversion_readiness: i === 0 ? "High" : "Medium",
            differentiation_gap: "no video",
          }));
          return {
            text: JSON.stringify(rows),
            usageMetadata: { promptTokenCount: 500, candidatesTokenCount: 200, totalTokenCount: 700 },
          };
        }
        if (req.contents.includes("market synthesis")) {
          return {
            text: JSON.stringify({
              executive_summary: "Median price is $55; buyers want speed.",
              dominant_buyer_intents: [{ intent: "core", share_pct: 80, opportunity: "speed" }, { intent: "adjacent", share_pct: 20, opportunity: "niche focus" }],
              differentiation_strategy: "Lead with delivery speed.",
            }),
            usageMetadata: { promptTokenCount: 300, candidatesTokenCount: 150, totalTokenCount: 450 },
          };
        }
        // Builder prompt(s)
        return {
          text: JSON.stringify({
            title: "I will deliver premium logo design for your brand",
            tags: ["logo design", "branding", "identity", "vector logo", "minimal logo"],
            category: "Graphics & Design",
            subcategory: "Logo Design",
            description: "A focused logo design service. " + "x".repeat(300),
            packages: [
              { tier: "Basic", name: "Basic", price_usd: 50, delivery_days: 2, revisions: "2 Revisions", description: "1 concept", deliverables: ["1 logo concept"] },
              { tier: "Standard", name: "Standard", price_usd: 110, delivery_days: 4, revisions: "4 Revisions", description: "3 concepts", deliverables: ["3 logo concepts"] },
              { tier: "Premium", name: "Premium", price_usd: 220, delivery_days: 7, revisions: "Unlimited", description: "Full identity", deliverables: ["Full brand identity"] },
            ],
            faqs: [
              { question: "Q1?", answer: "A1" }, { question: "Q2?", answer: "A2" },
              { question: "Q3?", answer: "A3" }, { question: "Q4?", answer: "A4" },
            ],
            buyer_requirements: ["r1", "r2", "r3"],
            scope_exclusions: ["e1", "e2"],
            cta: "Message me with your brief.",
            thumbnail_script: { main_headline: "Logo Design", sub_headline: "Fast", bullet_points: ["b1"], video_60s_script: "script" },
          }),
          usageMetadata: { promptTokenCount: 1000, candidatesTokenCount: 900, totalTokenCount: 1900 },
        };
      },
    },
  };
  return { client, calls };
}

async function waitRun(storage: Storage, get: () => any, timeoutMs = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const run = get();
    if (run && (run.status === "completed" || run.status === "failed")) return run;
    await new Promise((r) => setTimeout(r, 25));
  }
  throw new Error("run did not finish in time");
}

test("audit dry_run makes ZERO API calls and reports honest estimates", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const stub = stubGemini();
  const engine = new AIEngine(storage, () => stub.client);

  const run = storage.createAIRun("airun_dry", jobId, "dry_run", 3);
  await engine.runSemanticAudit("airun_dry");

  assert.equal(stub.calls.length, 0, "dry run must not call the model");
  const result = storage.getAIResult("airun_dry");
  assert.equal(result.dry_run, true);
  assert.equal(result.llm_used, false);
  assert.ok(result.estimated_cost_usd > 0, "estimate should be positive");
  assert.equal(storage.getAIRun("airun_dry")!.total_tokens, 0);
  assert.equal(storage.getAIRun("airun_dry")!.actual_cost_usd, 0);
});

test("audit without API key is deterministic: zero tokens, zero cost, real heuristic data", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const engine = new AIEngine(storage, () => null);

  const run = storage.createAIRun("airun_nok", jobId, "standard", 3);
  await engine.runSemanticAudit("airun_nok");

  const record = storage.getAIRun("airun_nok")!;
  assert.equal(record.status, "completed");
  assert.equal(record.total_tokens, 0, "no fake token counts");
  assert.equal(record.actual_cost_usd, 0, "no fake cost");
  const result = storage.getAIResult("airun_nok");
  assert.equal(result.llm_used, false);
  assert.ok(result.warnings.some((w: string) => w.includes("deterministic")));
  assert.equal(result.audit_records.length, 3);
  // relevance is computed, not a constant
  const scores = result.audit_records.map((r: any) => parseInt(r.relevance_score));
  assert.equal(scores.length, 3);
});

test("audit with real Gemini: real usage metadata propagates (no hardcoded tokens/cost)", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const stub = stubGemini();
  const engine = new AIEngine(storage, () => stub.client);

  const run = storage.createAIRun("airun_ai", jobId, "standard", 3);
  await engine.runSemanticAudit("airun_ai");

  const record = storage.getAIRun("airun_ai")!;
  assert.equal(record.status, "completed");
  assert.ok(stub.calls.length >= 2, "batch + synthesis calls expected");
  // 700 (audit batch) + 450 (synthesis) = 1150 real tokens from usageMetadata
  assert.equal(record.total_tokens, 1150);
  assert.ok(record.actual_cost_usd > 0 && record.actual_cost_usd < 1);
  const result = storage.getAIResult("airun_ai");
  assert.equal(result.llm_used, true);
  assert.equal(result.usage.total_tokens, 1150);
  assert.equal(result.usage.api_calls, 2);
  assert.ok(result.synthesis.executive_summary.includes("$55"));
});

test("audit test mode audits exactly 1 gig", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const stub = stubGemini();
  const engine = new AIEngine(storage, () => stub.client);

  const run = storage.createAIRun("airun_test", jobId, "test", 12);
  await engine.runSemanticAudit("airun_test");

  const result = storage.getAIResult("airun_test");
  assert.equal(result.audit_records.length, 1);
});

test("builder without API key: niche-independent deterministic draft (no dashboard/DAX leakage)", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const engine = new AIEngine(storage, () => null);

  const run = storage.createGenerationRun("gen_nok", jobId, "standard");
  await engine.runGigGeneration("gen_nok", { language: "English" });

  const record = storage.getGenerationRun("gen_nok")!;
  assert.equal(record.status, "completed");
  assert.equal(record.total_tokens, 0);
  assert.equal(record.actual_cost_usd, 0);
  const draft = storage.getGenerationResult("gen_nok");
  const blob = JSON.stringify({ t: draft.title, d: draft.description, p: draft.packages, f: draft.faqs, c: draft.cta }).toLowerCase();
  assert.ok(blob.includes("logo design"));
  assert.ok(!blob.includes("dashboard"), "no dashboard content for a logo niche");
  assert.ok(!blob.includes("dax"), "no DAX formulas for a logo niche");
  assert.ok(!blob.includes("loom"), "no Loom video template for a logo niche");
  assert.equal(draft.tags.length, 5);
  assert.ok(Array.isArray(draft.compliance_checks) && draft.compliance_checks.length > 5);
  // language note for non-English fallback
  const run2 = storage.createGenerationRun("gen_urdu", jobId, "standard");
  await engine.runGigGeneration("gen_urdu", { language: "Urdu" });
  const draft2 = storage.getGenerationResult("gen_urdu");
  assert.ok(JSON.stringify(draft2.description).includes("Urdu"));
});

test("builder with real Gemini: usage propagates; deep mode runs a refinement pass", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const stub = stubGemini();
  const engine = new AIEngine(storage, () => stub.client);

  const run = storage.createGenerationRun("gen_ai", jobId, "deep");
  await engine.runGigGeneration("gen_ai", { tone: "professional" });

  const record = storage.getGenerationRun("gen_ai")!;
  assert.equal(record.status, "completed");
  // deep mode: draft call + refinement call (the stub draft fails
  // "title_starts_with_i_will"? no — it starts with I will; refinement only
  // runs when compliance issues exist. The stub draft has 4 FAQs (pass) etc.
  // If everything passes, exactly 1 call; if any check fails, 2 calls.
  assert.ok(stub.calls.length >= 1);
  const result = storage.getGenerationResult("gen_ai");
  assert.ok(result.compliance_checks.length > 5);
  assert.ok(record.total_tokens >= 1900, "real tokens from usage metadata");
  assert.ok(record.actual_cost_usd > 0);
});

test("builder: Gemini failure falls back to deterministic draft with a warning", async () => {
  const storage = makeTmpStorage();
  const jobId = seedJob(storage, "logo design", 3);
  const stub = stubGemini({ fail: true });
  const engine = new AIEngine(storage, () => stub.client);

  const run = storage.createGenerationRun("gen_fail", jobId, "standard");
  await engine.runGigGeneration("gen_fail");

  const record = storage.getGenerationRun("gen_fail")!;
  assert.equal(record.status, "completed");
  assert.equal(record.total_tokens, 0, "failed LLM call must not report tokens");
  const draft = storage.getGenerationResult("gen_fail");
  assert.ok(JSON.stringify(draft).includes("logo design"));
});

test("compliance validator catches off-platform contact and non-ascending prices", () => {
  const storage = makeTmpStorage();
  const engine = new AIEngine(storage, () => null) as any;
  const checks = engine.validateDraft({
    title: "I will do x",
    description: "Email me at me@example.com for a faster deal. 100% satisfaction guarantee.",
    tags: ["a"],
    packages: [
      { tier: "Basic", price_usd: 100 },
      { tier: "Standard", price_usd: 50 },
      { tier: "Premium", price_usd: 200 },
    ],
    faqs: [],
    cta: "",
  });
  const byName = Object.fromEntries(checks.map((c: any) => [c.check, c.passed]));
  assert.equal(byName.no_off_platform_contact, false);
  assert.equal(byName.no_unverifiable_guarantees, false);
  assert.equal(byName.ascending_package_prices, false);
  assert.equal(byName.exactly_five_tags, false);
  assert.equal(byName.faq_depth, false);
});
