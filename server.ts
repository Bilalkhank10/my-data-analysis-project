import "dotenv/config";
import express from "express";
import cors from "cors";
import path from "path";
import fs from "fs";
import crypto from "crypto";
import { storage } from "./src/storage.js";
import { MarketAnalyzer } from "./src/market_analyzer.js";
import { crawlerManager } from "./src/crawler.js";
import { aiEngine } from "./src/ai_engine.js";
import { simpleWorkflowManager } from "./src/simple_workflow.js";
import { SIMPLE_HTML, INDEX_HTML, LOGIN_HTML } from "./src/views.js";

const app = express();
const PORT = 3000;

const APP_PASSWORD = process.env.APP_PASSWORD || "bilalkhan";
const AUTH_SECRET = process.env.AUTH_SECRET || "gigcraft-secure-auth-2026";
const activeSessions = new Set<string>();

function generateToken(): string {
  const timestamp = Date.now();
  const random = crypto.randomBytes(16).toString("hex");
  const payload = `${timestamp}:${random}`;
  const signature = crypto.createHmac("sha256", AUTH_SECRET).update(payload).digest("hex");
  const token = `${payload}:${signature}`;
  activeSessions.add(token);
  return token;
}

function verifyToken(token: string | null): boolean {
  if (!token) return false;
  if (activeSessions.has(token)) return true;
  try {
    const parts = token.split(":");
    if (parts.length !== 3) return false;
    const [tsStr, random, signature] = parts;
    const timestamp = parseInt(tsStr, 10);
    if (isNaN(timestamp)) return false;
    // 30 days valid
    const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
    if (Date.now() - timestamp > thirtyDaysMs) return false;
    const payload = `${timestamp}:${random}`;
    const expectedSig = crypto.createHmac("sha256", AUTH_SECRET).update(payload).digest("hex");
    if (crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSig))) {
      activeSessions.add(token);
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

function getCookie(req: express.Request, name: string): string | null {
  const cookieHeader = req.headers.cookie;
  if (!cookieHeader) return null;
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function isAuthenticated(req: express.Request): boolean {
  const cookieToken = getCookie(req, "auth_token");
  if (cookieToken && verifyToken(cookieToken)) return true;

  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    const bearerToken = authHeader.substring(7).trim();
    if (bearerToken && verifyToken(bearerToken)) return true;
  }

  const customHeader = req.headers["x-auth-token"];
  if (typeof customHeader === "string" && verifyToken(customHeader)) {
    return true;
  }

  if (typeof req.query.token === "string" && verifyToken(req.query.token)) {
    return true;
  }

  return false;
}

app.use(cors());
app.use(express.json());

// Ensure output and static directories exist
const STATIC_DIR = path.join(process.cwd(), "static");
const OUTPUT_DIR = path.join(process.cwd(), "output");
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// Serve static assets (publicly available for stylesheets, icons, fonts)
app.use("/static", express.static(STATIC_DIR));

// Authentication Endpoints
app.post("/api/auth/login", (req, res) => {
  const { password } = req.body || {};
  if (typeof password === "string" && (password.trim() === APP_PASSWORD || password.trim().toLowerCase() === APP_PASSWORD.toLowerCase())) {
    const token = generateToken();
    res.setHeader("Set-Cookie", `auth_token=${token}; Path=/; HttpOnly; SameSite=None; Secure; Max-Age=2592000`);
    res.json({ success: true, token, detail: "Authenticated successfully" });
  } else {
    res.status(401).json({ success: false, detail: "Incorrect password. Please try again." });
  }
});

app.get("/api/auth/status", (req, res) => {
  res.json({
    authenticated: isAuthenticated(req),
    configured: true,
  });
});

app.post("/api/auth/logout", (req, res) => {
  const cookieToken = getCookie(req, "auth_token");
  if (cookieToken) {
    activeSessions.delete(cookieToken);
  }
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    const bearerToken = authHeader.substring(7).trim();
    if (bearerToken) activeSessions.delete(bearerToken);
  }
  res.setHeader("Set-Cookie", "auth_token=; Path=/; HttpOnly; SameSite=None; Secure; Max-Age=0");
  res.json({ success: true });
});

// HTML Login Route
app.get("/login", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(LOGIN_HTML);
});

// HTML Application Routes
app.get("/", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(SIMPLE_HTML);
});

app.get("/advanced", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(INDEX_HTML);
});

// API Authentication Guard
app.use("/api", (req, res, next) => {
  // Whitelist public endpoints
  if (
    req.path === "/health" ||
    req.path === "/auth/login" ||
    req.path === "/auth/status" ||
    req.path === "/auth/logout"
  ) {
    next();
    return;
  }

  if (!isAuthenticated(req)) {
    res.status(401).json({ detail: "Password authentication required", authenticated: false });
    return;
  }
  next();
});

// API Routes

// Health & System Info
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    database: "in-memory-storage",
    gemini_configured: Boolean(process.env.GEMINI_API_KEY),
    password_protected: true,
  });
});

app.get("/api/ai/config", (req, res) => {
  res.json({
    configured: true,
    model: "gemini-2.5-flash",
    max_gigs: 25,
  });
});

app.get("/api/generation/config", (req, res) => {
  res.json({
    configured: true,
    model: "gemini-2.5-flash",
  });
});

// Simple Workflow Endpoints (Studio)
app.post("/api/simple-workflows", (req, res) => {
  try {
    const { niche, quality, buyer, language, existing_url } = req.body;
    if (!niche || typeof niche !== "string" || niche.trim().length < 2) {
      res.status(400).json({ detail: "Niche must be at least 2 characters" });
      return;
    }
    const workflow = simpleWorkflowManager.startWorkflow({
      niche: niche.trim(),
      quality: quality || "recommended",
      buyer: buyer || "",
      language: language || "English",
      existing_url: existing_url || null,
    });
    res.status(202).json(workflow);
  } catch (error: any) {
    res.status(500).json({ detail: error.message || "Failed to start workflow" });
  }
});

app.get("/api/simple-workflows/:id", (req, res) => {
  const workflow = simpleWorkflowManager.getWorkflow(req.params.id);
  if (!workflow) {
    res.status(404).json({ detail: "Workflow not found" });
    return;
  }
  res.json(workflow);
});

app.get("/api/simple-workflows/:id/result", (req, res) => {
  const workflow = simpleWorkflowManager.getWorkflow(req.params.id);
  if (!workflow) {
    res.status(404).json({ detail: "Workflow not found" });
    return;
  }
  if (workflow.status !== "completed") {
    res.status(409).json({ detail: "Workflow is not complete yet" });
    return;
  }
  const result = simpleWorkflowManager.getWorkflowResult(req.params.id);
  if (!result) {
    res.status(404).json({ detail: "Generated result not found" });
    return;
  }
  res.json(result);
});

app.get("/api/simple-workflows/:id/export.md", (req, res) => {
  const workflow = simpleWorkflowManager.getWorkflow(req.params.id);
  if (!workflow) {
    res.status(404).json({ detail: "Workflow not found" });
    return;
  }
  const result = simpleWorkflowManager.getWorkflowResult(req.params.id);
  if (!result) {
    res.status(404).json({ detail: "Result not found" });
    return;
  }
  const gig = result.recommended_gig || result;
  const packagesText = (gig.packages || [])
    .map(
      (p: any) =>
        `### ${p.tier || p.name} — $${p.price_usd}\n${p.description}\nDelivery: ${p.delivery_days} days | Revisions: ${p.revisions}\n` +
        (p.deliverables || []).map((d: string) => `- ${d}`).join("\n")
    )
    .join("\n\n");

  const faqsText = (gig.faqs || [])
    .map((f: any) => `**Q: ${f.question}**\nA: ${f.answer}`)
    .join("\n\n");

  const md = `# ${gig.title}

## Tags
${(gig.tags || []).join(", ")}

## Description
${gig.description}

## Pricing Packages
${packagesText}

## Frequently Asked Questions
${faqsText}

## Buyer Requirements
${(gig.buyer_requirements || []).map((r: string, i: number) => `${i + 1}. ${r}`).join("\n")}

## Scope Exclusions
${(gig.scope_exclusions || []).map((e: string) => `- ${e}`).join("\n")}

## Call to Action
${gig.cta || ""}
`;

  res.setHeader("Content-Type", "text/markdown; charset=utf-8");
  res.setHeader("Content-Disposition", `attachment; filename="gigcraft_${req.params.id}.md"`);
  res.send(md);
});

// Jobs Endpoints (Lab & Crawler)
app.post("/api/jobs", (req, res) => {
  const { niche, limit } = req.body;
  if (!niche || typeof niche !== "string" || niche.trim().length < 2) {
    res.status(400).json({ detail: "Niche must be at least 2 characters" });
    return;
  }
  const job = crawlerManager.startJob(niche.trim(), Number(limit) || 10);
  res.status(202).json(job);
});

app.post("/api/fetch", (req, res) => {
  const { niche, limit } = req.body;
  const job = crawlerManager.startJob(niche?.trim() || "Looker Studio", Number(limit) || 10);
  res.status(202).json(job);
});

app.get("/api/jobs", (req, res) => {
  const limit = Math.min(100, Math.max(1, Number(req.query.limit) || 20));
  const jobs = crawlerManager.listJobs(limit);
  res.json({ jobs, count: jobs.length });
});

app.get("/api/jobs/:job_id", (req, res) => {
  const job = crawlerManager.getJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  res.json(job);
});

app.get("/api/jobs/:job_id/results", (req, res) => {
  const job = crawlerManager.getJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  const offset = Math.max(0, Number(req.query.offset) || 0);
  const limit = Math.min(100, Math.max(1, Number(req.query.limit) || 20));
  const { results, total } = storage.getJobResults(req.params.job_id, offset, limit);
  res.json({
    job_id: req.params.job_id,
    status: job.status,
    offset,
    limit,
    total,
    has_more: offset + results.length < total,
    results,
  });
});

app.get("/api/jobs/:job_id/analysis", (req, res) => {
  const job = crawlerManager.getJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  if (job.status === "queued" || job.status === "running") {
    res.status(409).json({ detail: "Analysis will be available when the crawl finishes" });
    return;
  }
  const analysis = crawlerManager.analyzeJob(req.params.job_id);
  if (!analysis) {
    res.status(404).json({ detail: "Analysis not available" });
    return;
  }
  res.json(analysis);
});

app.post("/api/jobs/:job_id/analysis/rebuild", (req, res) => {
  const job = crawlerManager.getJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  const analysis = crawlerManager.analyzeJob(req.params.job_id, true);
  res.json(analysis);
});

app.get("/api/jobs/:job_id/analysis/:section.csv", (req, res) => {
  const analysis = crawlerManager.analyzeJob(req.params.job_id);
  if (!analysis) {
    res.status(404).json({ detail: "Analysis not available" });
    return;
  }
  const rows = MarketAnalyzer.exportRows(analysis, req.params.section);
  if (!rows || rows.length === 0) {
    res.setHeader("Content-Type", "text/csv");
    res.send("No data\n");
    return;
  }
  const headers = Object.keys(rows[0]);
  const csvLines = [headers.join(",")];
  for (const row of rows) {
    csvLines.push(
      headers
        .map((h) => {
          const val = row[h];
          if (val === null || val === undefined) return "";
          const str = String(val).replace(/"/g, '""');
          return str.includes(",") || str.includes("\n") || str.includes('"') ? `"${str}"` : str;
        })
        .join(",")
    );
  }
  res.setHeader("Content-Type", "text/csv");
  res.setHeader("Content-Disposition", `attachment; filename="${req.params.section}.csv"`);
  res.send(csvLines.join("\n"));
});

app.post("/api/jobs/:job_id/cancel", (req, res) => {
  const job = crawlerManager.cancelJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  res.json(job);
});

// AI Semantic Audit Endpoints
app.post("/api/jobs/:job_id/ai-runs", async (req, res) => {
  const job = crawlerManager.getJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  const { mode, max_gigs } = req.body;
  const run = aiEngine.startAudit(req.params.job_id, mode || "standard", Number(max_gigs) || 10);
  res.status(202).json(run);
});

app.get("/api/jobs/:job_id/ai-runs", (req, res) => {
  const runs = aiEngine.listAuditRuns(req.params.job_id);
  res.json({ runs });
});

app.get("/api/ai-runs/:run_id", (req, res) => {
  const run = aiEngine.getAuditRun(req.params.run_id);
  if (!run) {
    res.status(404).json({ detail: "Audit run not found" });
    return;
  }
  res.json(run);
});

app.get("/api/ai-runs/:run_id/result", (req, res) => {
  const result = aiEngine.getAuditResult(req.params.run_id);
  if (!result) {
    res.status(404).json({ detail: "Audit result not found" });
    return;
  }
  res.json(result);
});

// Gig Builder Endpoints
app.post("/api/jobs/:job_id/generation-runs", async (req, res) => {
  const job = crawlerManager.getJob(req.params.job_id);
  if (!job) {
    res.status(404).json({ detail: "Job not found" });
    return;
  }
  const run = aiEngine.startBuilderRun(req.params.job_id, req.body || {});
  res.status(202).json(run);
});

app.get("/api/jobs/:job_id/generation-runs", (req, res) => {
  const runs = aiEngine.listBuilderRuns(req.params.job_id);
  res.json({ runs });
});

app.get("/api/generation-runs/:run_id", (req, res) => {
  const run = aiEngine.getBuilderRun(req.params.run_id);
  if (!run) {
    res.status(404).json({ detail: "Builder run not found" });
    return;
  }
  res.json(run);
});

app.get("/api/generation-runs/:run_id/result", (req, res) => {
  const result = aiEngine.getBuilderResult(req.params.run_id);
  if (!result) {
    res.status(404).json({ detail: "Builder result not found" });
    return;
  }
  res.json(result);
});

app.post("/api/generation-runs/:run_id/approval", (req, res) => {
  const run = aiEngine.getBuilderRun(req.params.run_id);
  if (!run) {
    res.status(404).json({ detail: "Builder run not found" });
    return;
  }
  run.approval_status = "approved";
  res.json(run);
});

app.get("/api/generation-runs/:run_id/export.md", (req, res) => {
  const result = aiEngine.getBuilderResult(req.params.run_id);
  if (!result) {
    res.status(404).json({ detail: "Builder result not found" });
    return;
  }
  const gig = result.recommended_gig || result;
  const visual = result.thumbnail_script || {};
  const packagesText = (gig.packages || [])
    .map(
      (p: any) =>
        `### ${p.tier || p.name} — $${p.price_usd}\n${p.description}\nDelivery: ${p.delivery_days} days | Revisions: ${p.revisions}\n` +
        (p.deliverables || []).map((d: string) => `- ${d}`).join("\n")
    )
    .join("\n\n");

  const md = `# ${gig.title}

## Tags
${(gig.tags || []).join(", ")}

## Description
${gig.description}

## Pricing Packages
${packagesText}

## FAQs
${(gig.faqs || []).map((f: any) => `**Q: ${f.question}**\nA: ${f.answer}`).join("\n\n")}

## Visual Brief & Script
- **Main Headline**: ${visual.main_headline || ""}
- **Sub Headline**: ${visual.sub_headline || ""}
- **Video Script**: ${visual.video_60s_script || ""}
`;

  res.setHeader("Content-Type", "text/markdown; charset=utf-8");
  res.setHeader("Content-Disposition", `attachment; filename="gig_${req.params.run_id}.md"`);
  res.send(md);
});

// Download JSON/CSV dumps
app.get("/download/:filename", (req, res) => {
  if (!isAuthenticated(req)) {
    res.redirect(`/login?redirect=${encodeURIComponent(req.originalUrl)}`);
    return;
  }
  const filename = req.params.filename;
  const filePath = path.join(OUTPUT_DIR, filename);
  if (!fs.existsSync(filePath)) {
    // Generate dynamically if needed from job ID
    const match = filename.match(/^([a-f0-9-]+)\.(json|csv)$/);
    if (match) {
      const jobId = match[1];
      const format = match[2];
      const { results } = storage.getJobResults(jobId, 0, 1000);
      if (results.length > 0) {
        if (format === "json") {
          res.setHeader("Content-Type", "application/json");
          res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
          res.send(JSON.stringify(results, null, 2));
          return;
        } else if (format === "csv") {
          res.setHeader("Content-Type", "text/csv");
          res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
          const headers = ["id", "title", "seller_name", "seller_level", "starting_price_usd", "rating", "review_count", "url"];
          const lines = [headers.join(",")];
          for (const r of results) {
            lines.push(
              headers
                .map((h) => {
                  const v = (r as any)[h];
                  if (v === null || v === undefined) return "";
                  const s = String(v).replace(/"/g, '""');
                  return s.includes(",") || s.includes("\n") || s.includes('"') ? `"${s}"` : s;
                })
                .join(",")
            );
          }
          res.send(lines.join("\n"));
          return;
        }
      }
    }
    res.status(404).json({ detail: "Export not found" });
    return;
  }
  res.download(filePath);
});

// Catch-all route to redirect
app.use((req, res) => {
  res.redirect("/");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`GigCraft Server running on port ${PORT}`);
});
