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
const PORT = Number(process.env.PORT) || 3000;

// No hardcoded password/secret fallbacks: generate an ephemeral random secret
// on boot if AUTH_SECRET is unset, and require APP_PASSWORD to be configured.
// If it is missing, fall back to a random per-boot password printed to the
// server log so access is never silently wide-open with a known default.
const AUTH_SECRET = process.env.AUTH_SECRET || crypto.randomBytes(32).toString("hex");
const APP_PASSWORD = process.env.APP_PASSWORD || crypto.randomBytes(12).toString("base64url");
if (!process.env.APP_PASSWORD) {
  console.warn(
    "[security] APP_PASSWORD is not set. A temporary password was generated for this session:\n" +
      `           ${APP_PASSWORD}\n` +
      "           Set APP_PASSWORD in your environment to use a stable password."
  );
}
const activeSessions = new Set<string>();

// Cookies are marked Secure only when the request arrived over HTTPS. Local
// and LAN access is typically plain HTTP, where a Secure cookie would be
// dropped by the browser and break persistent login.
function cookieFlags(req: express.Request, maxAgeSeconds: number): string {
  const isHttps = req.secure || req.headers["x-forwarded-proto"] === "https";
  // Over HTTPS use SameSite=None so the cookie survives when the app is
  // embedded in a cross-site iframe (hosted previews, dashboards). Browsers
  // require Secure with SameSite=None, so plain HTTP keeps Lax instead.
  const sameSite = isHttps ? "None; Secure" : "Lax";
  return `Path=/; HttpOnly; SameSite=${sameSite}; Max-Age=${maxAgeSeconds}`;
}

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
app.use(express.json({ limit: "1mb" }));

// Return a clean JSON error (instead of an Express HTML stack trace) when the
// request body is not valid JSON.
app.use((err: any, _req: express.Request, res: express.Response, next: express.NextFunction) => {
  if (err instanceof SyntaxError && "body" in err) {
    res.status(400).json({ detail: "Invalid JSON in request body" });
    return;
  }
  next(err);
});

function clampInt(value: any, min: number, max: number, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.round(n)));
}

const VALID_AI_MODES = new Set(["dry_run", "test", "standard", "deep"]);
const VALID_QUALITY = new Set(["fast", "recommended", "best"]);

// Neutralize spreadsheet formula injection: a leading =, +, -, @ (or tab/CR)
// can execute formulas when the CSV is opened in Excel/Sheets.
function csvCell(value: any): string {
  if (value === null || value === undefined) return "";
  let s = String(value).replace(/"/g, '""');
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  if (s.includes(",") || s.includes("\n") || s.includes('"')) s = `"${s}"`;
  return s;
}

// Ensure output and static directories exist.
// Exports are written by the storage layer to <cwd>/data/exports.
const STATIC_DIR = path.join(process.cwd(), "static");
const EXPORT_DIR = storage.getExportsDir();
const OUTPUT_DIR = path.join(process.cwd(), "output");
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// Strict whitelist for downloadable export filenames: job-id style basename
// plus a known extension. This prevents path traversal (e.g. "../../etc/passwd").
const SAFE_DOWNLOAD_NAME = /^[A-Za-z0-9_-]+\.(json|csv)$/;

function resolveDownloadPath(filename: string): string | null {
  if (typeof filename !== "string" || !SAFE_DOWNLOAD_NAME.test(filename)) {
    return null;
  }
  // The basename regex above already strips any path separators, but resolve
  // and confirm the final path stays inside the intended directory as defence
  // in depth.
  const candidates = [EXPORT_DIR, OUTPUT_DIR];
  for (const dir of candidates) {
    const resolved = path.resolve(dir, filename);
    if (resolved.startsWith(dir + path.sep) && fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
      return resolved;
    }
  }
  return null;
}

// Serve static assets (publicly available for stylesheets, icons, fonts)
app.use("/static", express.static(STATIC_DIR));

// Authentication Endpoints
function passwordMatches(input: string): boolean {
  const a = Buffer.from(input.trim());
  const b = Buffer.from(APP_PASSWORD);
  // Constant-time comparison; lengths differing still do a compare against a
  // dummy buffer to avoid leaking length via timing.
  const ref = a.length === b.length ? b : Buffer.alloc(a.length);
  try {
    return a.length === b.length && crypto.timingSafeEqual(a, ref);
  } catch {
    return false;
  }
}

app.post("/api/auth/login", (req, res) => {
  const { password } = req.body || {};
  if (typeof password === "string" && passwordMatches(password)) {
    const token = generateToken();
    res.setHeader("Set-Cookie", `auth_token=${token}; ${cookieFlags(req, 2592000)}`);
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
  const customHeader = req.headers["x-auth-token"];
  if (typeof customHeader === "string") {
    activeSessions.delete(customHeader);
  }
  if (typeof req.query.token === "string") {
    activeSessions.delete(req.query.token);
  }
  res.setHeader("Set-Cookie", `auth_token=; ${cookieFlags(req, 0)}`);
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
  const hasKey = Boolean(process.env.GEMINI_API_KEY);
  res.json({
    configured: hasKey,
    model: "gemini-2.5-flash",
    max_gigs: 25,
    fallback: !hasKey ? "deterministic-local" : undefined,
  });
});

app.get("/api/generation/config", (req, res) => {
  const hasKey = Boolean(process.env.GEMINI_API_KEY);
  res.json({
    configured: hasKey,
    model: "gemini-2.5-flash",
    fallback: !hasKey ? "deterministic-local" : undefined,
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
    if (niche.trim().length > 200) {
      res.status(400).json({ detail: "Niche must be 200 characters or fewer" });
      return;
    }
    const workflow = simpleWorkflowManager.startWorkflow({
      niche: niche.trim(),
      quality: VALID_QUALITY.has(quality) ? quality : "recommended",
      buyer: typeof buyer === "string" ? buyer.slice(0, 500) : "",
      language: typeof language === "string" && language.trim() ? language.slice(0, 50) : "English",
      existing_url: typeof existing_url === "string" ? existing_url.slice(0, 2000) : null,
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
  if (niche.trim().length > 200) {
    res.status(400).json({ detail: "Niche must be 200 characters or fewer" });
    return;
  }
  const job = crawlerManager.startJob(niche.trim(), clampInt(limit, 4, 60, 10));
  res.status(202).json(job);
});

app.post("/api/fetch", (req, res) => {
  const { niche, limit } = req.body;
  if (!niche || typeof niche !== "string" || !niche.trim()) {
    res.status(400).json({ detail: "Niche is required" });
    return;
  }
  const job = crawlerManager.startJob(niche.trim(), clampInt(limit, 4, 60, 10));
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
  const csvLines = [headers.map(csvCell).join(",")];
  for (const row of rows) {
    csvLines.push(headers.map((h) => csvCell(row[h])).join(","));
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
  const { mode, max_gigs } = req.body || {};
  const safeMode = VALID_AI_MODES.has(mode) ? mode : "standard";
  const run = aiEngine.startAudit(req.params.job_id, safeMode, clampInt(max_gigs, 1, 50, 10));
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
  const body = req.body && typeof req.body === "object" ? req.body : {};
  if (body.mode && !VALID_AI_MODES.has(body.mode)) {
    res.status(400).json({ detail: "Invalid mode. Use dry_run, test, standard, or deep." });
    return;
  }
  const run = aiEngine.startBuilderRun(req.params.job_id, body);
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
  const safePath = resolveDownloadPath(filename);
  if (safePath) {
    res.download(safePath);
    return;
  }

  // Generate dynamically from in-memory job results if the export file was
  // not persisted. Filenames look like "<jobId>-gigs.<json|csv>".
  const match = filename.match(/^([A-Za-z0-9_-]+)-gigs\.(json|csv)$/);
  if (match) {
    const jobId = match[1];
    const format = match[2];
    const { results } = storage.getJobResults(jobId, 0, 100000);
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
        const lines = [headers.map(csvCell).join(",")];
        for (const r of results) {
          lines.push(headers.map((h) => csvCell((r as any)[h])).join(","));
        }
        res.send(lines.join("\n"));
        return;
      }
    }
  }
  res.status(404).json({ detail: "Export not found" });
});

// Catch-all route to redirect
app.use((req, res) => {
  res.redirect("/");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`GigCraft Server running on port ${PORT}`);
});
