import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { csvCell, toCsv } from "../src/csv.js";
import { securityHeaders } from "../src/security.js";
import { RateLimiter } from "../src/rate_limit.js";
import { Storage, stripBulkyFields } from "../src/storage.js";

// ---------------------------------------------------------------------------
// CSV formula injection
// ---------------------------------------------------------------------------

test("csvCell neutralizes formula injection (all dangerous prefixes)", () => {
  for (const evil of ["=HYPERLINK(\"x\")", "+cmd", "-1+2", "@SUM(A1)", "\tTAB", "\rCR"]) {
    const out = csvCell(evil);
    // The cell must not START with a formula character (after the optional
    // outer CSV quoting) and must carry the ' text-prefix inside.
    const inner = out.startsWith('"') ? out.slice(1, -1) : out;
    assert.ok(!/^[=+\-@\t\r]/.test(out), `${JSON.stringify(evil)} -> ${JSON.stringify(out)}`);
    assert.ok(inner.startsWith("'"), `content should be quote-prefixed: ${JSON.stringify(out)}`);
  }
  // normal values pass through (with proper quoting when needed)
  assert.equal(csvCell("hello"), "hello");
  assert.equal(csvCell("a,b"), '"a,b"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell(null), "");
});

test("storage.writeJobExports writes sanitized CSV and strips bulky fields from JSON", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-csv-"));
  const storage = new Storage(dir);
  const jobId = "job_csv_test";
  storage.createJob(jobId, "logo design", 1);
  storage.saveGigResult(jobId, {
    url: "https://www.fiverr.com/x/y",
    title: '=HYPERLINK("https://evil","click")',
    seller_name: "Seller",
    starting_price_usd: 50,
    related_tags: ["logo", "design"],
    raw_visible_text: "X".repeat(500_000),
    reviews_text: "Y".repeat(500_000),
  } as any);
  storage.writeJobExports(jobId, "logo design", storage.getAllJobResults(jobId));

  const csv = fs.readFileSync(path.join(dir, "exports", `${jobId}-gigs.csv`), "utf8");
  const titleLine = csv.split("\n").find((l) => l.includes("HYPERLINK")) || "";
  // The formula cell must not begin with '=' — it must carry the ' prefix.
  const cell = titleLine.split(",").find((c) => c.includes("HYPERLINK")) || "";
  const inner = cell.startsWith('"') ? cell.slice(1, -1) : cell;
  assert.ok(inner.startsWith("'"), `formula cell must be quote-prefixed: ${JSON.stringify(cell)}`);
  assert.ok(!/^[=+\-@\t\r]/.test(cell), "cell must not start with a formula character");

  const json = fs.readFileSync(path.join(dir, "exports", `${jobId}-gigs.json`), "utf8");
  assert.ok(!json.includes('"raw_visible_text"'), "raw_visible_text must be stripped from export");
  assert.ok(!json.includes('"reviews_text"'));
  assert.ok(json.includes("HYPERLINK"), "title itself is still stored");
});

// ---------------------------------------------------------------------------
// Security headers
// ---------------------------------------------------------------------------

test("security headers include CSP and clickjacking protection", () => {
  const h = securityHeaders();
  assert.ok(h["Content-Security-Policy"].includes("default-src 'self'"));
  assert.ok(h["X-Frame-Options"] === "DENY");
  assert.ok(h["X-Content-Type-Options"] === "nosniff");
  assert.ok(h["Referrer-Policy"] === "same-origin");
});

// ---------------------------------------------------------------------------
// Rate limiter
// ---------------------------------------------------------------------------

test("rate limiter enforces per-key window limits", () => {
  const limiter = new RateLimiter({ windowMs: 60_000, max: 3 });
  const t0 = 1_000_000;
  assert.equal(limiter.allow("ip-a", t0), true);
  assert.equal(limiter.allow("ip-a", t0 + 1000), true);
  assert.equal(limiter.allow("ip-a", t0 + 2000), true);
  assert.equal(limiter.allow("ip-a", t0 + 3000), false, "4th hit in window must be blocked");
  // different key is independent
  assert.equal(limiter.allow("ip-b", t0 + 3000), true);
  // after the window resets, the key works again
  assert.equal(limiter.allow("ip-a", t0 + 61_000), true);
  // sweep drops expired windows
  limiter.sweep(t0 + 120_000);
});




// ---------------------------------------------------------------------------
// Persistence (node:sqlite write-through)
// ---------------------------------------------------------------------------

test("storage persists jobs/results/analyses across restarts", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-persist-"));
  const s1 = new Storage(dir);
  s1.createJob("job_p1", "logo design", 2);
  s1.saveGigResult("job_p1", { url: "https://www.fiverr.com/a/b", title: "t1" } as any);
  s1.saveGigResult("job_p1", { url: "https://www.fiverr.com/a/c", title: "t2" } as any);
  s1.saveAnalysis("job_p1", { niche: "logo design", overview: { sampled_gigs: 2 } });
  s1.createAIRun("air_p1", "job_p1", "standard", 2);
  s1.saveAIResult("air_p1", { run_id: "air_p1", gigs_audited: 2 });
  s1.createGenerationRun("gen_p1", "job_p1", "standard");
  s1.saveGenerationResult("gen_p1", { run_id: "gen_p1", title: "draft" }, "# md");

  // Simulate a restart: brand-new Storage on the same directory.
  const s2 = new Storage(dir);
  const job = s2.getJob("job_p1");
  assert.ok(job, "job must survive restart");
  assert.equal(s2.getAllJobResults("job_p1").length, 2);
  assert.equal(s2.getAnalysis("job_p1")!.overview.sampled_gigs, 2);
  assert.equal(s2.getAIRun("air_p1")!.mode, "standard");
  assert.equal(s2.getAIResult("air_p1")!.gigs_audited, 2);
  assert.equal(s2.getGenerationResult("gen_p1")!.title, "draft");
  assert.ok(s2.getGenerationMarkdown("gen_p1")!.startsWith("# md"));
});

test("rank snapshots enable previous-snapshot lookup (movement history)", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-snap-"));
  const s = new Storage(dir);
  const gig1 = { url: "https://www.fiverr.com/a/one", search: { global_position: 3 } } as any;
  const gig2 = { url: "https://www.fiverr.com/a/two", search: { global_position: 1 } } as any;
  s.saveRankSnapshot("logo design", "job_a", [gig1, gig2]);
  // previous snapshot for a NEW job in the same niche = job_a's snapshot
  const prev = s.getPreviousSnapshot("logo design", "job_b");
  assert.ok(prev && prev.length === 2);
  assert.ok(prev.some((p) => p.url === "https://www.fiverr.com/a/one" && p.rank === 3));
  // excluding the same job yields null
  assert.equal(s.getPreviousSnapshot("logo design", "job_a"), null);
  // different niche is isolated
  assert.equal(s.getPreviousSnapshot("logo design x", "job_b"), null);
});

test("reader cache returns fresh entries and expires stale ones", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-cache-"));
  const s = new Storage(dir);
  assert.equal(s.getReaderCache("https://r.jina.ai/x", 60_000), null);
  s.setReaderCache("https://r.jina.ai/x", "markdown body");
  assert.equal(s.getReaderCache("https://r.jina.ai/x", 60_000), "markdown body");
  // TTL already passed (negative age check via tiny ttl)
  const entry = s.getReaderCache("https://r.jina.ai/x", 0);
  assert.equal(entry, null, "ttl=0 must be treated as expired");
});

test("job cap evicts oldest finished jobs", () => {
  process.env.MAX_JOBS = "5";
  try {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gigcraft-cap-"));
    const s = new Storage(dir);
    for (let i = 0; i < 7; i++) {
      const id = `job_cap_${i}`;
      s.createJob(id, "niche", 1);
      s.updateJob(id, { status: "completed" });
    }
    const jobs = s.listJobs(50);
    assert.ok(jobs.length <= 5, `expected <=5 jobs, got ${jobs.length}`);
    // oldest were evicted, newest kept
    assert.ok(s.getJob("job_cap_6"));
    assert.ok(!s.getJob("job_cap_0"));
  } finally {
    delete process.env.MAX_JOBS;
  }
});

// ---------------------------------------------------------------------------
// Bulky-field stripping (results API + dynamic downloads)
// ---------------------------------------------------------------------------

test("stripBulkyFields removes page-text blobs but keeps UI fields", () => {
  const gig: any = {
    url: "https://www.fiverr.com/a/b",
    title: "t",
    starting_price_usd: 50,
    visible_reviews: [{ rating: 5, comment: "great" }],
    packages: [{ name: "Basic", price_usd: 50 }],
    raw_visible_text: "X".repeat(100_000),
    reviews_text: "Y".repeat(100_000),
    faq_text: "Z".repeat(100_000),
    packages_text: "W".repeat(100_000),
    json_ld: { huge: true },
  };
  const lean = stripBulkyFields(gig);
  assert.ok(!("raw_visible_text" in lean));
  assert.ok(!("reviews_text" in lean));
  assert.ok(!("faq_text" in lean));
  assert.ok(!("packages_text" in lean));
  assert.ok(!("json_ld" in lean));
  assert.equal(lean.title, "t");
  assert.deepEqual(lean.visible_reviews, gig.visible_reviews);
  assert.deepEqual(lean.packages, gig.packages);
  // original object untouched
  assert.ok("raw_visible_text" in gig);
});
