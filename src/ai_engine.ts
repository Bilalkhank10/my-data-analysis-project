import { GoogleGenAI } from "@google/genai";
import { Storage, utcNow, storage } from "./storage.js";

// ---------------------------------------------------------------------------
// Gemini client + pricing (used for honest, clearly-labelled cost estimates)
// ---------------------------------------------------------------------------

export interface GeminiLikeClient {
  models: {
    generateContent(req: { model: string; contents: string; config?: any }): Promise<any>;
  };
}

export type GeminiProvider = () => GeminiLikeClient | null;

const GEMINI_MODEL = "gemini-2.5-flash";
// gemini-2.5-flash list pricing (per 1M tokens, ≤200k context, non-thinking).
// Used ONLY for estimates; the actual token counts come from usageMetadata.
const PRICE_PER_M_INPUT_USD = 0.3;
const PRICE_PER_M_OUTPUT_USD = 2.5;

const GEMINI_TIMEOUT_MS = 90_000;
const GEMINI_MAX_ATTEMPTS = 2;

let cachedGemini: GoogleGenAI | null = null;

function defaultGeminiProvider(): GeminiLikeClient | null {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return null;
  if (!cachedGemini) {
    cachedGemini = new GoogleGenAI({ apiKey: key });
  }
  return cachedGemini as unknown as GeminiLikeClient;
}

function usageOf(response: any): { promptTokens: number; completionTokens: number; totalTokens: number; available: boolean } {
  const u = response?.usageMetadata;
  if (!u) return { promptTokens: 0, completionTokens: 0, totalTokens: 0, available: false };
  return {
    promptTokens: u.promptTokenCount || 0,
    completionTokens: u.candidatesTokenCount || u.totalTokenCount || 0,
    totalTokens: u.totalTokenCount || u.promptTokenCount + (u.candidatesTokenCount || 0),
    available: true,
  };
}

function estimateCost(promptTokens: number, completionTokens: number): number {
  return Math.round(((promptTokens * PRICE_PER_M_INPUT_USD + completionTokens * PRICE_PER_M_OUTPUT_USD) / 1_000_000) * 1e6) / 1e6;
}

/**
 * Call Gemini with a hard timeout and one retry. Returns { text, usage } or
 * throws the last error.
 */
async function callGemini(
  client: GeminiLikeClient,
  prompt: string,
  config: Record<string, any> = {}
): Promise<{ text: string | null; usage: ReturnType<typeof usageOf> }> {
  let lastError: any = null;
  for (let attempt = 0; attempt < GEMINI_MAX_ATTEMPTS; attempt++) {
    try {
      const response = await Promise.race([
        client.models.generateContent({ model: GEMINI_MODEL, contents: prompt, config }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error(`Gemini request timed out after ${GEMINI_TIMEOUT_MS / 1000}s`)), GEMINI_TIMEOUT_MS)
        ),
      ]);
      return { text: response?.text ?? null, usage: usageOf(response) };
    } catch (err: any) {
      lastError = err;
      const retryable = /timeout|network|fetch|429|5\d\d|overloaded|quota/i.test(String(err?.message || err));
      if (!retryable) break;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

function parseJsonFromText(text: string): any {
  const cleaned = text.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  return JSON.parse(cleaned);
}

// ---------------------------------------------------------------------------
// Deterministic (no-LLM) helpers — computed from REAL crawled data only.
// ---------------------------------------------------------------------------

function titleWords(title: string): Set<string> {
  const stop = new Set(["i", "will", "for", "your", "you", "the", "and", "with", "our", "a", "an", "of", "to", "in"]);
  return new Set(
    (title || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2 && !stop.has(w))
  );
}

/** Heuristic relevance of a gig to the niche (real data, labelled heuristic). */
function deterministicRelevance(gig: any, topKeywords: string[]): number {
  const words = titleWords(gig.title || "");
  const nicheWords = titleWords(gig.search?.niche || "");
  let overlap = 0;
  for (const w of nicheWords) if (words.has(w)) overlap++;
  let keywordHits = 0;
  for (const kw of topKeywords) if (words.has(kw)) keywordHits++;
  let score = 50 + overlap * 8 + Math.min(20, keywordHits * 4);
  if (gig.packages?.length) score += 5;
  if (gig.faqs?.length) score += 3;
  if (gig.has_video) score += 2;
  if ((gig.review_count || 0) > 100) score += 3;
  return Math.min(98, score);
}

// ---------------------------------------------------------------------------
// AI engine
// ---------------------------------------------------------------------------

export class AIEngine {
  constructor(
    private store: Storage,
    private geminiProvider: GeminiProvider = defaultGeminiProvider,
  ) {}

  // -------------------------------------------------------------------------
  // 1. Semantic audit
  // -------------------------------------------------------------------------

  async runSemanticAudit(runId: string): Promise<void> {
    const run = this.store.getAIRun(runId);
    if (!run) return;

    const job = this.store.getJob(run.job_id);
    const gigs = this.store.getAllJobResults(run.job_id);
    const niche = job?.niche || "general";
    const analysis = this.store.getAnalysis(run.job_id);
    const topKeywords = (analysis?.keywords?.bigrams || []).slice(0, 10).map((k: any) => k.phrase);
    const unigrams = (analysis?.keywords?.unigrams || []).slice(0, 10).map((k: any) => k.phrase);

    const isDry = run.mode === "dry_run";
    const gemini = this.geminiProvider();
    const willUseAI = !isDry && Boolean(gemini);

    try {
      // ---- dry_run: zero API calls, honest projection -----------------
      if (isDry) {
        const sampleSize = Math.min(gigs.length, run.selected_gigs || 12);
        this.store.updateAIRun(runId, { status: "running", stage: "planning", progress_percent: 50 });
        const estimatedInputTokens = sampleSize * 900 + 1200;
        const estimatedOutputTokens = sampleSize * 120 + 600;
        this.store.saveAIResult(runId, {
          dry_run: true,
          run_id: runId,
          job_id: run.job_id,
          mode: run.mode,
          llm_used: false,
          selected_gigs: sampleSize,
          selected: gigs.slice(0, sampleSize).map((g, i) => ({
            rank: g.search?.global_position || i + 1,
            title: g.title,
            url: g.url,
          })),
          estimated_input_tokens: estimatedInputTokens,
          estimated_output_tokens: estimatedOutputTokens,
          estimated_cost_usd: estimateCost(estimatedInputTokens, estimatedOutputTokens),
          note: "Dry run: no API calls were made. Estimates use typical prompt sizes for the selected sample.",
        });
        this.store.updateAIRun(runId, {
          status: "completed", stage: "done", progress_percent: 100,
          processed_gigs: 0, total_tokens: 0, actual_cost_usd: 0,
          estimated_cost_usd: estimateCost(estimatedInputTokens, estimatedOutputTokens),
          finished_at: utcNow(),
        });
        return;
      }

      // ---- mode-based sample size (real meaning for each mode) --------
      const sampleSize = run.mode === "test"
        ? Math.min(1, gigs.length)
        : Math.min(gigs.length, run.selected_gigs || 12);
      const targetGigs = gigs.slice(0, sampleSize);
      const warnings: string[] = [];

      if (!gemini) {
        warnings.push("GEMINI_API_KEY is not set — running the deterministic local audit (no LLM, no cost).");
      }

      this.store.updateAIRun(runId, {
        status: "running",
        stage: gemini ? "auditing_semantic_clusters" : "auditing_deterministic",
        progress_percent: 10,
      });

      let auditResults: any[] = [];
      let synthesis: any = null;
      let promptTokens = 0;
      let completionTokens = 0;
      let usageAvailable = false;
      let apiCalls = 0;

      if (gemini) {
        // Batch of 5 gigs per call (fewer calls, same data).
        const BATCH = 5;
        for (let start = 0; start < targetGigs.length; start += BATCH) {
          const batch = targetGigs.slice(start, start + BATCH);
          const payload = batch.map((g, i) => ({
            global_position: g.search?.global_position || start + i + 1,
            title: g.title,
            seller: g.seller_name || g.seller_username,
            seller_level: g.seller_level,
            rating: g.rating,
            review_count: g.review_count,
            starting_price_usd: g.starting_price_usd,
            packages: (g.packages || []).map((p: any) => ({ name: p.name, price_usd: p.price_usd, description: String(p.description || "").slice(0, 200) })),
            faqs: (g.faqs || []).slice(0, 4).map((f: any) => ({ q: String(f.question || "").slice(0, 160), a: String(f.answer || "").slice(0, 240) })),
            top_reviews: (g.visible_reviews || []).slice(0, 3).map((r: any) => String(r.comment || "").slice(0, 240)),
          }));
          const prompt = [
            `You are a senior marketplace analyst auditing competing Fiverr gig listings in the niche: "${niche}".`,
            `Top market phrases observed in the sample: ${[...new Set([...topKeywords, ...unigrams])].slice(0, 12).join("; ") || "n/a"}.`,
            "For EACH gig below return a JSON array with exactly these fields:",
            '{"global_position": number, "title": string, "seller": string, "seller_level": string, "intent_cluster": string (short buyer-intent label), "relevance_score": integer 0-100 (how well the gig matches what buyers of this niche want), "neo_alignment": "High"|"Medium"|"Low", "conversion_readiness": "High"|"Medium"|"Low", "differentiation_gap": string (one concrete weakness vs. the market)}',
            "Ground every judgment in the provided fields only. Do not invent facts.",
            "Gigs:",
            JSON.stringify(payload, null, 1),
          ].join("\n\n");
          try {
            const { text, usage } = await callGemini(gemini, prompt, { responseMimeType: "application/json" });
            apiCalls++;
            promptTokens += usage.promptTokens;
            completionTokens += usage.completionTokens;
            usageAvailable = usageAvailable || usage.available;
            const parsed = parseJsonFromText(text || "[]");
            const rows = Array.isArray(parsed) ? parsed : parsed.records || [];
            for (const row of rows) {
              auditResults.push({
                global_position: row.global_position,
                title: row.title,
                seller: row.seller,
                seller_level: row.seller_level,
                intent_cluster: row.intent_cluster,
                relevance_score: `${Math.max(0, Math.min(100, Math.round(Number(row.relevance_score) || 0)))}%`,
                neo_alignment: row.neo_alignment,
                conversion_readiness: row.conversion_readiness,
                differentiation_gap: row.differentiation_gap,
              });
            }
          } catch (err: any) {
            warnings.push(`AI batch ${Math.floor(start / BATCH) + 1} failed: ${err?.message || err}. Those gigs use the deterministic heuristic.`);
            for (const g of batch) {
              auditResults.push(this.deterministicAuditRow(g, topKeywords));
            }
          }
          this.store.updateAIRun(runId, {
            progress_percent: 10 + Math.round(80 * Math.min(1, (start + batch.length) / targetGigs.length)),
            processed_gigs: Math.min(targetGigs.length, start + batch.length),
          });
        }

        // Synthesis call (executive summary grounded in the real stats).
        try {
          const stats = {
            niche,
            sampled_gigs: analysis?.overview?.sampled_gigs,
            median_price: analysis?.pricing?.overall?.median,
            top_keywords: (analysis?.keywords?.bigrams || []).slice(0, 8).map((k: any) => k.phrase),
            clusters: (analysis?.keyword_clusters || []).slice(0, 5).map((c: any) => c.cluster),
            gaps: (analysis?.market_gaps?.keyword_opportunities || []).slice(0, 5).map((o: any) => o.phrase),
          };
          const prompt = [
            `You are a senior marketplace strategist. Using ONLY the data below, write a concise market synthesis for the niche "${niche}".`,
            "Data:",
            JSON.stringify(stats, null, 1),
            "Audited gigs:",
            JSON.stringify(auditResults, null, 1),
            'Return JSON: {"executive_summary": string (2-3 sentences, cite the real median price if provided), "dominant_buyer_intents": [{"intent": string, "share_pct": integer (your estimate of demand share, must sum ~100), "opportunity": string}], "differentiation_strategy": string (one concrete, actionable strategy)}',
          ].join("\n\n");
          const { text, usage } = await callGemini(gemini, prompt, { responseMimeType: "application/json" });
          apiCalls++;
          promptTokens += usage.promptTokens;
          completionTokens += usage.completionTokens;
          usageAvailable = usageAvailable || usage.available;
          synthesis = parseJsonFromText(text || "{}");
        } catch (err: any) {
          warnings.push(`Synthesis call failed: ${err?.message || err}. Using a data-only summary.`);
          synthesis = {
            executive_summary: `Sampled ${analysis?.overview?.sampled_gigs ?? targetGigs.length} listings in "${niche}"; median starting price ${analysis?.pricing?.overall?.median != null ? `$${analysis.pricing.overall.median}` : "n/a"}. See per-gig records for details.`,
            dominant_buyer_intents: (analysis?.keyword_clusters || []).slice(0, 3).map((c: any) => ({
              intent: c.cluster,
              share_pct: Math.round(c.share_pct || 0),
              opportunity: `${c.gig_count} sampled gigs compete in this cluster.`,
            })),
            differentiation_strategy: "Target the under-represented phrases from market_gaps with explicit package positioning.",
          };
        }
      } else {
        // Deterministic local audit — computed from real data, clearly labelled.
        auditResults = targetGigs.map((g) => this.deterministicAuditRow(g, topKeywords));
        synthesis = {
          executive_summary: `Deterministic (no-LLM) audit of ${auditResults.length} sampled listings in "${niche}". Median starting price ${analysis?.pricing?.overall?.median != null ? `$${analysis.pricing.overall.median}` : "unknown"}.`,
          dominant_buyer_intents: (analysis?.keyword_clusters || []).slice(0, 3).map((c: any) => ({
            intent: c.cluster,
            share_pct: Math.round(c.share_pct || 0),
            opportunity: `${c.gig_count} sampled gigs share this cluster (real Jaccard clustering).`,
          })),
          differentiation_strategy: "Focus on the highest-opportunity phrases from market_gaps that are under-represented in gig titles.",
        };
      }

      const totalTokens = promptTokens + completionTokens;
      const actualCost = usageAvailable ? estimateCost(promptTokens, completionTokens) : 0;

      this.store.saveAIResult(runId, {
        run_id: runId,
        job_id: run.job_id,
        mode: run.mode,
        llm_used: willUseAI && apiCalls > 0,
        completed_at: utcNow(),
        gigs_audited: auditResults.length,
        audit_records: auditResults,
        synthesis,
        usage: {
          api_calls: apiCalls,
          prompt_tokens: promptTokens,
          completion_tokens: completionTokens,
          total_tokens: totalTokens,
          estimated_cost_usd: actualCost,
          usage_available: usageAvailable,
        },
        warnings,
      });

      this.store.updateAIRun(runId, {
        status: "completed",
        stage: "done",
        progress_percent: 100,
        processed_gigs: auditResults.length,
        total_tokens: totalTokens,
        actual_cost_usd: actualCost,
        finished_at: utcNow(),
      });
    } catch (err: any) {
      console.error("Semantic audit failed:", err);
      this.store.updateAIRun(runId, {
        status: "failed",
        stage: "error",
        error: err?.message || "Semantic audit failed",
        finished_at: utcNow(),
      });
    }
  }

  private deterministicAuditRow(g: any, topKeywords: string[]): Record<string, any> {
    const score = deterministicRelevance(g, topKeywords);
    return {
      global_position: g.search?.global_position,
      title: g.title,
      seller: g.seller_name || g.seller_username,
      seller_level: g.seller_level,
      intent_cluster: topKeywords[0] ? `Around "${topKeywords[0]}"` : "General niche demand",
      relevance_score: `${score}%`,
      neo_alignment: score >= 80 ? "High" : score >= 65 ? "Medium" : "Low",
      conversion_readiness: (g.packages?.length >= 3 ? 1 : 0) + (g.faqs?.length >= 3 ? 1 : 0) + (g.has_video ? 1 : 0) >= 2 ? "High" : "Medium",
      differentiation_gap: g.packages?.length >= 3
        ? (g.has_video ? "Competitive listing — differentiate on delivery speed or niche focus" : "No video walkthrough in sample data")
        : "Fewer than 3 visible packages in parsed data",
      method: "deterministic-heuristic",
    };
  }

  // -------------------------------------------------------------------------
  // 2. Gig builder
  // -------------------------------------------------------------------------

  async runGigGeneration(
    runId: string,
    customInputs?: { custom_angle?: string; target_price?: string; experience_level?: string; language?: string; tone?: string }
  ): Promise<void> {
    const run = this.store.getGenerationRun(runId);
    if (!run) return;

    const job = this.store.getJob(run.job_id);
    const niche = job?.niche || "general";
    const analysis = this.store.getAnalysis(run.job_id);
    const warnings: string[] = [];

    const isDry = run.mode === "dry_run";
    const gemini = this.geminiProvider();
    const willUseAI = !isDry && Boolean(gemini);

    try {
      // ---- dry_run: honest plan, zero API calls ------------------------
      if (isDry) {
        const evidenceItems = this.evidenceSummary(analysis);
        const estimatedInputTokens = 2200 + evidenceItems.length * 60;
        const estimatedOutputTokens = 1600;
        this.store.updateGenerationRun(runId, { status: "running", stage: "planning", progress_percent: 50 });
        this.store.saveGenerationResult(runId, {
          dry_run: true,
          run_id: runId,
          job_id: run.job_id,
          mode: run.mode,
          llm_used: false,
          niche,
          evidence: evidenceItems,
          estimated_input_tokens: estimatedInputTokens,
          estimated_output_tokens: estimatedOutputTokens,
          estimated_cost_usd: estimateCost(estimatedInputTokens, estimatedOutputTokens),
          planned_outputs: ["title", "5 tags", "description", "Basic/Standard/Premium packages", "FAQs", "buyer requirements", "scope exclusions", "CTA", "thumbnail script", "compliance checks"],
          note: "Dry run: no API calls were made and no draft was generated.",
        }, this.formatMarkdown({ title: "(dry run — no draft generated)", tags: [], description: "", packages: [], faqs: [], buyer_requirements: [], scope_exclusions: [], cta: "", thumbnail_script: {} }, niche));
        this.store.updateGenerationRun(runId, {
          status: "completed", stage: "done", progress_percent: 100,
          total_tokens: 0, actual_cost_usd: 0,
          estimated_cost_usd: estimateCost(estimatedInputTokens, estimatedOutputTokens),
          finished_at: utcNow(),
        });
        return;
      }

      this.store.updateGenerationRun(runId, {
        status: "running",
        stage: "generating_gig_copy",
        progress_percent: 20,
      });

      const language = (customInputs?.language && customInputs.language.trim()) || "English";
      const tone = customInputs?.tone || "professional";
      const evidence = this.evidenceSummary(analysis);

      let generatedDraft: any = null;
      let promptTokens = 0;
      let completionTokens = 0;
      let usageAvailable = false;
      let apiCalls = 0;

      if (gemini) {
        const prompt = this.buildBuilderPrompt(niche, evidence, customInputs, language, tone);
        try {
          this.store.updateGenerationRun(runId, { stage: "calling_model", progress_percent: 45 });
          const { text, usage } = await callGemini(gemini, prompt, { responseMimeType: "application/json" });
          apiCalls++;
          promptTokens += usage.promptTokens;
          completionTokens += usage.completionTokens;
          usageAvailable = usageAvailable || usage.available;
          if (text) generatedDraft = parseJsonFromText(text);
        } catch (err: any) {
          warnings.push(`Gemini generation failed: ${err?.message || err}. Falling back to the deterministic evidence-based draft.`);
        }

        // deep mode: one refinement pass fed with real compliance issues
        if (generatedDraft && run.mode === "deep") {
          const checks = this.validateDraft(generatedDraft);
          const issues = checks.filter((c: any) => !c.passed);
          if (issues.length) {
            try {
              this.store.updateGenerationRun(runId, { stage: "refining_draft", progress_percent: 75 });
              const refinePrompt = [
                `Refine the Fiverr gig draft for the niche "${niche}" so it fixes ONLY the listed compliance issues while keeping the rest intact.`,
                `Output language: ${language}. Tone: ${tone}.`,
                "Issues to fix:",
                JSON.stringify(issues, null, 1),
                "Current draft:",
                JSON.stringify(generatedDraft, null, 1),
                "Return the COMPLETE updated draft as JSON with the same schema.",
              ].join("\n\n");
              const { text, usage } = await callGemini(gemini, refinePrompt, { responseMimeType: "application/json" });
              apiCalls++;
              promptTokens += usage.promptTokens;
              completionTokens += usage.completionTokens;
              usageAvailable = usageAvailable || usage.available;
              if (text) generatedDraft = parseJsonFromText(text);
            } catch (err: any) {
              warnings.push(`Deep refinement failed: ${err?.message || err}. Keeping the first draft.`);
            }
          }
        }
      } else {
        warnings.push("GEMINI_API_KEY is not set — generating the deterministic evidence-based draft (no LLM, no cost).");
      }

      if (!generatedDraft) {
        generatedDraft = this.buildDeterministicDraft(niche, analysis, customInputs, language);
      }

      const compliance = this.validateDraft(generatedDraft);
      generatedDraft.compliance_checks = compliance;

      const markdownContent = this.formatMarkdown(generatedDraft, niche);
      this.store.saveGenerationResult(runId, generatedDraft, markdownContent);

      const totalTokens = promptTokens + completionTokens;
      const actualCost = usageAvailable ? estimateCost(promptTokens, completionTokens) : 0;

      this.store.updateGenerationRun(runId, {
        status: "completed",
        stage: "done",
        progress_percent: 100,
        total_tokens: totalTokens,
        actual_cost_usd: actualCost,
        llm_used: apiCalls > 0,
        finished_at: utcNow(),
      });
    } catch (err: any) {
      console.error("Gig generation failed:", err);
      this.store.updateGenerationRun(runId, {
        status: "failed",
        stage: "error",
        error: err?.message || "Gig generation failed",
        finished_at: utcNow(),
      });
    }
  }

  /** Compact, REAL market evidence injected into the builder prompt. */
  private evidenceSummary(analysis: any): string[] {
    const items: string[] = [];
    if (!analysis) return items;
    const bigrams = (analysis.keywords?.bigrams || []).slice(0, 10).map((k: any) => `${k.phrase} (${k.gig_count} gigs, avg rank ${k.average_rank})`);
    if (bigrams.length) items.push(`Top title phrases: ${bigrams.join("; ")}`);
    const tags = (analysis.keywords?.related_tags || []).slice(0, 8).map((t: any) => `${t.phrase} (${t.gig_count})`);
    if (tags.length) items.push(`Most common buyer tags: ${tags.join("; ")}`);
    const p = analysis.pricing?.overall;
    if (p?.median != null) items.push(`Pricing (starting, USD): median $${Math.round(p.median)}, mean $${Math.round(p.mean ?? 0)}, p90 $${Math.round(p.p90 ?? 0)}`);
    const tiers = analysis.pricing?.package_tiers;
    if (tiers && Object.keys(tiers).length) {
      items.push(`Observed package tier medians (USD): ${Object.entries(tiers).map(([t, s]: any) => `${t} $${Math.round(s.median ?? 0)}`).join(", ")}`);
    }
    const starts = (analysis.keywords?.title_starts || []).slice(0, 5).map((s: any) => `"${s.phrase}"`);
    if (starts.length) items.push(`Common title openings: ${starts.join(", ")}`);
    const gaps = (analysis.market_gaps?.keyword_opportunities || []).slice(0, 5).map((g: any) => g.phrase);
    if (gaps.length) items.push(`Under-served phrases from the sample: ${gaps.join("; ")}`);
    const features = (analysis.packages?.feature_matrix || []).slice(0, 6).map((f: any) => `${f.feature} (${f.overall_coverage_pct}% of gigs)`);
    if (features.length) items.push(`Common package features: ${features.join("; ")}`);
    return items;
  }

  private buildBuilderPrompt(niche: string, evidence: string[], inputs?: any, language = "English", tone = "professional"): string {
    return [
      `You are a top Fiverr copywriter. Write a high-converting, policy-compliant gig for the niche: "${niche}".`,
      "",
      "Market evidence from the crawled competitor sample (use it to position the gig — do not copy any competitor's wording):",
      ...(evidence.length ? evidence.map((e) => `- ${e}`) : ["- (no sample data available; rely on the niche itself)"]),
      "",
      `Target price: ${inputs?.target_price || "align with the median above"}.`,
      `Angle: ${inputs?.custom_angle || "clear value, professional delivery"}.`,
      `Seller tone: ${tone}.`,
      `IMPORTANT: Write the ENTIRE gig copy (title, description, packages, FAQs, CTA) in ${language}.`,
      "IMPORTANT: Every sentence must be specifically about the niche. Do not mention unrelated industries, tools or deliverables that the niche does not imply.",
      "IMPORTANT: No off-platform contact (no email/WhatsApp/Telegram/PayPal mentions), no guarantees like '100% satisfied or refund'." ,
      "",
      "Return ONLY a JSON object with exactly these fields:",
      `{
  "title": "starts with 'I will', 35-80 chars, keyword-first for the niche",
  "tags": ["exactly 5 unique tags, each <= 20 chars, all niche-relevant"],
  "category": "the best-fitting Fiverr top category for this niche",
  "subcategory": "the best-fitting subcategory",
  "description": "300-1200 chars, structured: hook, problem, solution, what you get, why you, how it works",
  "packages": [
    {"tier": "Basic", "name": string, "price_usd": number, "delivery_days": number, "revisions": string, "description": string, "deliverables": [string]},
    {"tier": "Standard", "name": string, "price_usd": number, "delivery_days": number, "revisions": string, "description": string, "deliverables": [string]},
    {"tier": "Premium", "name": string, "price_usd": number, "delivery_days": number, "revisions": string, "description": string, "deliverables": [string]}
  ],
  "faqs": [{"question": string, "answer": string} (4-6 items)],
  "buyer_requirements": [string (3 items)],
  "scope_exclusions": [string (2 items)],
  "cta": string,
  "thumbnail_script": {"main_headline": string, "sub_headline": string, "bullet_points": [string], "video_60s_script": string}
}`,
    ].join("\n");
  }

  /**
   * Deterministic fallback draft — fully niche-independent, grounded in the
   * real market evidence (median price, top phrases) with neutral wording.
   */
  private buildDeterministicDraft(niche: string, analysis: any, inputs?: any, language = "English"): any {
    const cleanNiche = (niche || "service").trim();
    const medianPrice = analysis?.pricing?.overall?.median;
    const base = typeof medianPrice === "number" && medianPrice > 0 ? Math.round(medianPrice) : 40;
    const topStart = analysis?.keywords?.title_starts?.[0]?.phrase;
    const topPhrases = (analysis?.keywords?.bigrams || []).slice(0, 3).map((k: any) => k.phrase);
    const tags = [
      cleanNiche.toLowerCase().slice(0, 20),
      ...(topPhrases.length ? [topPhrases[0].slice(0, 20)] : ["professional service"]),
      "custom work",
      "fast delivery",
      "dedicated support",
    ].slice(0, 5);

    const title = topStart
      ? `I will ${topStart} ${cleanNiche}`.slice(0, 80)
      : `I will deliver professional ${cleanNiche} services for you`.slice(0, 80);

    const evidenceLine = topPhrases.length
      ? `Buyers in this market commonly search for: ${topPhrases.join(", ")}.`
      : "";

    return {
      title,
      tags: Array.from(new Set(tags)),
      category: "Professional Services",
      subcategory: cleanNiche.charAt(0).toUpperCase() + cleanNiche.slice(1),
      description: [
        `### What You Get`,
        `A focused, professional ${cleanNiche} service built around your specific requirements. ${evidenceLine}`,
        ``,
        `### Why Choose This Service`,
        `- Clear scope agreed before work starts`,
        `- Structured process with checkpoints so you always know the status`,
        `- Revisions included in every package`,
        ``,
        `### How It Works`,
        `1. Share your requirements (see buyer requirements below).`,
        `2. I confirm scope and timeline.`,
        `3. You receive the first deliverable for review.`,
        `4. Revisions until it matches what we agreed.`,
        ``,
        language !== "English"
          ? `Note: this deterministic fallback draft is written in English. Set GEMINI_API_KEY to generate the draft directly in ${language}.`
          : "",
      ].filter(Boolean).join("\n"),
      packages: [
        {
          tier: "Basic",
          name: "Essential",
          price_usd: Math.max(15, Math.round(base * 0.9)),
          delivery_days: 2,
          revisions: "2 Revisions",
          description: `Single scope item for ${cleanNiche} with core deliverables.`,
          deliverables: ["1 core deliverable", "1 revision round included", "Written handover notes"],
        },
        {
          tier: "Standard",
          name: "Complete",
          price_usd: Math.max(40, Math.round(base * 2.2)),
          delivery_days: 4,
          revisions: "4 Revisions",
          description: `Extended scope for ${cleanNiche} with multiple deliverables and priority handling.`,
          deliverables: ["Up to 3 deliverables", "Priority turnaround", "Custom adjustments", "Source files"],
        },
        {
          tier: "Premium",
          name: "Premium Suite",
          price_usd: Math.max(90, Math.round(base * 4.5)),
          delivery_days: 7,
          revisions: "Unlimited",
          description: `Full-scope ${cleanNiche} package with dedicated support and rapid response.`,
          deliverables: ["Unlimited deliverables within scope", "Unlimited revisions", "Dedicated communication", "Post-delivery support (14 days)"],
        },
      ],
      faqs: [
        { question: "What do I need to provide before starting?", answer: `Simply share your requirements and any files relevant to ${cleanNiche}; I will confirm the scope before work begins.` },
        { question: "How do revisions work?", answer: "Every package includes revisions. Share feedback on the first deliverable and I will adjust until it matches the agreed scope." },
        { question: "Can you handle confidential material?", answer: "Yes. I am happy to sign an NDA and can work with anonymized samples where appropriate." },
        { question: "What happens after delivery?", answer: "You receive all agreed deliverables plus written handover notes. The Premium package includes 14 days of post-delivery support." },
      ],
      buyer_requirements: [
        "A short description of your goals for this project",
        `Any files, links or samples related to ${cleanNiche}`,
        "Your preferred timeline (if any)",
      ],
      scope_exclusions: [
        "Work outside the agreed scope (available as an add-on)",
        "Rush work inside 24 hours (contact me first to check availability)",
      ],
      cta: "Send me a message with your project details and I will confirm scope and timeline right away.",
      thumbnail_script: {
        main_headline: cleanNiche.charAt(0).toUpperCase() + cleanNiche.slice(0, 40),
        sub_headline: "Professional · Clear Scope · Revisions Included",
        bullet_points: ["Fast Delivery", "Custom Work", "Dedicated Support"],
        video_60s_script: `Hook: Struggling to find someone who delivers exactly what you need for ${cleanNiche}?\nProblem: Most generic listings hide extra costs and vague scope.\nSolution: I define the scope with you upfront and deliver a professional result within the agreed timeline.\nCTA: Choose a package below or message me with your project details.`,
      },
    };
  }

  /**
   * Deterministic compliance checks (ported from the Python gig builder's
   * validator). These assist human review — they are not a policy guarantee.
   */
  private validateDraft(draft: any): Array<Record<string, any>> {
    const checks: Array<Record<string, any>> = [];
    const check = (name: string, passed: boolean, note: string) =>
      checks.push({ check: name, passed, note });

    const title = String(draft.title || "");
    check("title_present", title.length >= 15, "Title should be 15-80 characters.");
    check("title_starts_with_i_will", /^i will/i.test(title.trim()), "Fiverr titles start with 'I will'.");

    const description = String(draft.description || "");
    check("description_length", description.length >= 200 && description.length <= 1600, "Description should be ~300-1200 characters.");

    const tags: string[] = Array.isArray(draft.tags) ? draft.tags.map((t: any) => String(t).trim()) : [];
    check("exactly_five_tags", tags.length === 5, "Fiverr allows exactly 5 tags.");
    check("unique_tags", new Set(tags.map((t) => t.toLowerCase())).size === tags.length, "Tags must be unique.");

    const packages = Array.isArray(draft.packages) ? draft.packages : [];
    check("three_packages", packages.length === 3, "Expected Basic/Standard/Premium packages.");
    const prices = packages.map((p: any) => Number(p?.price_usd)).filter((n: number) => isFinite(n));
    check(
      "ascending_package_prices",
      prices.length === 3 && prices[0] < prices[1] && prices[1] < prices[2],
      "Package prices must ascend Basic < Standard < Premium.",
    );

    const faqs = Array.isArray(draft.faqs) ? draft.faqs : [];
    check("faq_depth", faqs.length >= 3, "At least 3 FAQs recommended.");

    const allText = JSON.stringify([title, description, packages, faqs, draft.cta]).toLowerCase();
    const offPlatform = /\b(email me|whatsapp|telegram|paypal|out.?of.?platform|add me on|dm me on)\b/.test(allText);
    check("no_off_platform_contact", !offPlatform, "No off-platform contact or payment methods allowed on Fiverr.");
    const guarantee = /\b(100% (satisfaction )?guarantee|money.?back guarantee|refund guarantee)\b/.test(allText);
    check("no_unverifiable_guarantees", !guarantee, "Avoid absolute guarantees like '100% satisfaction guarantee'.");

    return checks;
  }

  private formatMarkdown(draft: any, niche: string): string {
    const p = draft.packages || [];
    return `# 🎯 Fiverr Gig Specification — ${niche}

**Title:** ${draft.title}
**Category:** ${draft.category || ""} > ${draft.subcategory || ""}
**Search Tags:** ${(draft.tags || []).join(", ")}

---

## 📝 Gig Description

${draft.description}

---

## 📦 Package Tiers

${p
      .map(
        (pkg: any) => `### 🏷️ ${pkg.tier || pkg.name}: ${pkg.name} — $${pkg.price_usd}
* **Delivery Time:** ${pkg.delivery_days} Day${pkg.delivery_days > 1 ? "s" : ""}
* **Revisions:** ${pkg.revisions}
* **Description:** ${pkg.description}
* **Deliverables:**
${(pkg.deliverables || []).map((d: string) => `  - ${d}`).join("\n")}`
      )
      .join("\n")}

---

## ❓ Frequently Asked Questions (FAQs)

${(draft.faqs || [])
      .map(
        (f: any) => `**Q: ${f.question}**
A: ${f.answer}
`
      )
      .join("\n")}

---

## 📋 Buyer Requirements

${(draft.buyer_requirements || []).map((r: string) => `- ${r}`).join("\n")}

---

## ⚠️ Scope Exclusions

${(draft.scope_exclusions || []).map((e: string) => `- ${e}`).join("\n")}

---

## 📢 Call to Action (CTA)

${draft.cta || ""}

---

## 🎨 Visual System & Thumbnail Assets

* **Main Thumbnail Headline:** ${draft.thumbnail_script?.main_headline}
* **Sub-Headline:** ${draft.thumbnail_script?.sub_headline}
* **Feature Badges:** ${(draft.thumbnail_script?.bullet_points || []).join(" | ")}

### 🎬 60-Second Video Script:
\`\`\`
${draft.thumbnail_script?.video_60s_script}
\`\`\`
`;
  }
}

const engineInstance = new AIEngine(storage);

const VALID_MODES = new Set(["dry_run", "test", "standard", "deep"]);

function normalizeMode(mode: any): "dry_run" | "test" | "standard" | "deep" {
  return VALID_MODES.has(mode) ? mode : "standard";
}

export const aiEngine = {
  startAudit(jobId: string, mode: any = "standard", maxGigs: number = 10) {
    const id = `airun_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const safeGigs = Math.min(50, Math.max(1, Math.round(Number(maxGigs) || 10)));
    const run = storage.createAIRun(id, jobId, normalizeMode(mode), safeGigs);
    setTimeout(() => {
      engineInstance.runSemanticAudit(id).catch((e) => console.error("Audit error:", e));
    }, 50);
    return run;
  },

  listAuditRuns(jobId: string) {
    return storage.listAIRuns(jobId);
  },

  getAuditRun(runId: string) {
    return storage.getAIRun(runId);
  },

  getAuditResult(runId: string) {
    return storage.getAIResult(runId);
  },

  startBuilderRun(jobId: string, params: any = {}) {
    const id = `genrun_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const mode = normalizeMode(params.mode || "standard");
    const run = storage.createGenerationRun(id, jobId, mode);
    setTimeout(() => {
      engineInstance
        .runGigGeneration(id, {
          custom_angle: params.positioning_goal || params.target_buyer,
          target_price: params.pricing_preference,
          // tone is a WRITING style; experience level defaults (no more
          // feeding a UI "tone/language" value into "Experience level:").
          experience_level: "experienced professional",
          language: params.output_language || params.language,
          tone: params.tone,
        })
        .catch((e) => console.error("Builder error:", e));
    }, 50);
    return run;
  },

  listBuilderRuns(jobId: string) {
    return storage.listGenerationRuns(jobId);
  },

  getBuilderRun(runId: string) {
    return storage.getGenerationRun(runId);
  },

  getBuilderResult(runId: string) {
    return storage.getGenerationResult(runId);
  },

  rawEngine: engineInstance,
};
