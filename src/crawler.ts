import { GigResult } from "./types.js";
import { Storage, utcNow, storage } from "./storage.js";
import { MarketAnalyzer } from "./market_analyzer.js";
import { readerFetcher } from "./fiverr_fetcher.js";

export class FiverrCrawler {
  private storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  async runJob(jobId: string): Promise<void> {
    const job = this.storage.getJob(jobId);
    if (!job) return;
    // Job may have been cancelled while queued.
    if (job.status === "cancelled") return;

    try {
      this.storage.updateJob(jobId, {
        status: "running",
        stage: "discovering",
        progress_percent: 5,
        started_at: utcNow(),
        discovery_source: "Fetching live Fiverr data via public reader…",
      });

      const niche = job.niche.trim();
      const limit = Math.min(Math.max(job.limit || 12, 4), 60);

      let gigs: GigResult[] = [];
      let isLive = false;
      let availableResults: number | null = null;
      let pagesScanned = 0;
      const warnings: string[] = [];

      try {
        const outcome = await readerFetcher.crawl(niche, limit, {
          isCancelled: () => this.storage.getJob(jobId)?.status === "cancelled",
          onProgress: (p) => {
            this.storage.updateJob(jobId, {
              stage: p.stage === "fetching" ? "fetching_details" : "discovering",
              progress_percent: Math.round(p.progress_percent || 0),
              discovered_count: p.discovered_count,
              processed_count: p.processed_count,
              success_count: p.success_count,
              failed_count: p.failed_count,
              pages_scanned: p.pages_scanned,
            });
          },
        });
        gigs = outcome.results || [];
        pagesScanned = outcome.pagesScanned;
        availableResults = outcome.availableResults;
        warnings.push(...(outcome.warnings || []));
        // "Live" means we actually parsed at least one real gig (successfully,
        // not an error stub).
        isLive = gigs.some((g) => !g.error && g.url);
      } catch (err: any) {
        warnings.push(`Live crawl failed: ${err?.message || err}`);
      }

      if (!isLive || gigs.length === 0) {
        // Fall back to an explicitly-labelled illustrative sample so the UI is
        // still usable offline / when Fiverr blocks the reader.
        gigs = this.generateSampleGigs(niche, limit);
        isLive = false;
        warnings.push(
          "Live Fiverr data was unavailable (network blocked or reader returned no listings); showing an illustrative simulated sample, not real listings."
        );
      }

      const successful = gigs.filter((g) => !g.error).length;
      const failed = gigs.filter((g) => g.error).length;

      this.storage.updateJob(jobId, {
        stage: "analyzing",
        progress_percent: isLive ? 96 : 60,
        discovered_count: gigs.length,
        pages_scanned: pagesScanned || undefined,
        available_results: isLive
          ? availableResults ?? Math.max(gigs.length, successful)
          : gigs.length,
        discovery_source: isLive
          ? "Fiverr live data via public reader"
          : "Illustrative sample (live Fiverr fetch unavailable — showing demo data)",
        warnings,
      });

      for (const gig of gigs) {
        this.storage.saveGigResult(jobId, gig);
      }

      const totalAvailable = isLive ? availableResults || gigs.length : gigs.length;
      const analysis = MarketAnalyzer.analyze(niche, gigs, totalAvailable);
      this.storage.saveAnalysis(jobId, analysis);
      this.storage.writeJobExports(jobId, niche, gigs);

      // Do not overwrite a cancellation that arrived mid-crawl.
      if (this.storage.getJob(jobId)?.status === "cancelled") return;

      this.storage.updateJob(jobId, {
        status: failed > 0 && successful === 0 ? "failed" : "completed",
        stage: "done",
        progress_percent: 100,
        processed_count: gigs.length,
        success_count: successful,
        failed_count: failed,
        finished_at: utcNow(),
        ...(failed > 0 && successful === 0
          ? { error: "All gig detail fetches failed." }
          : {}),
      });
    } catch (err: any) {
      console.error("Job execution failed:", err);
      this.storage.updateJob(jobId, {
        status: "failed",
        stage: "error",
        error: err?.message || "Failed to process gig research job",
        finished_at: utcNow(),
      });
    }
  }

  private generateSampleGigs(niche: string, limit: number): GigResult[] {
    const sellers = [
      { name: "Alex DataPro", username: "alex_datapro", level: "Top Rated", country: "United States", online: true, days: "1 day ago" },
      { name: "Elena Insights", username: "elena_insights", level: "Level 2", country: "United Kingdom", online: true, days: "2 days ago" },
      { name: "Marcus Analytics", username: "marcus_analytics", level: "Level 2", country: "Germany", online: false, days: "3 days ago" },
      { name: "Sophia Visuals", username: "sophia_visuals", level: "Level 1", country: "Canada", online: true, days: "5 days ago" },
      { name: "David BI Studio", username: "david_bistudio", level: "Level 2", country: "Australia", online: false, days: "1 week ago" },
      { name: "Sarah TechCraft", username: "sarah_techcraft", level: "Level 1", country: "United States", online: true, days: "2 weeks ago" },
      { name: "Apex Metrics Hub", username: "apex_metrics", level: "New Seller", country: "Netherlands", online: false, days: "3 weeks ago" },
      { name: "Global Cloud Lab", username: "global_cloud", level: "Level 1", country: "United Kingdom", online: true, days: "1 month ago" },
      { name: "Vanguard Studio", username: "vanguard_studio", level: "New Seller", country: "Singapore", online: false, days: "2 months ago" },
      { name: "Quantum Analytics", username: "quantum_ai", level: "Level 2", country: "United States", online: true, days: "2 days ago" },
    ];

    const titleTemplates = [
      `I will build an automated ${niche} with interactive executive dashboard`,
      `I will design custom ${niche} reports and real-time data tracking`,
      `I will setup, audit, and fix your ${niche} integration and formulas`,
      `I will create professional ${niche} with KPI metrics and daily sync`,
      `I will build high-converting ${niche} visual solutions for your business`,
      `I will provide advanced ${niche} consulting and multi-source connection`,
      `I will automate ${niche} workflows and scheduled client reporting`,
      `I will optimize your ${niche} architecture for speed and accuracy`,
      `I will deliver executive-level ${niche} analytics with custom drilldowns`,
      `I will create modern, responsive ${niche} templates ready to use`,
    ];

    const priceTiers = [45, 60, 35, 75, 50, 90, 40, 120, 30, 85, 150, 25];

    const results: GigResult[] = [];
    for (let i = 0; i < limit; i++) {
      const s = sellers[i % sellers.length];
      const title = titleTemplates[i % titleTemplates.length];
      const basePrice = priceTiers[i % priceTiers.length];
      const revs = Math.max(0, Math.round(180 - i * 14 + (i % 3) * 8));

      results.push({
        url: `https://www.fiverr.com/${s.username}/do-professional-${encodeURIComponent(niche.toLowerCase().replace(/\s+/g, "-"))}-${i + 1}`,
        title,
        fetched_at: utcNow(),
        seller_name: s.name,
        seller_username: s.username,
        seller_level: s.level,
        seller_country: s.country,
        starting_price_usd: basePrice,
        currency: "USD",
        rating: 4.9,
        review_count: revs,
        has_video: i % 2 === 0,
        last_delivery: s.days,
        search: {
          niche,
          global_position: i + 1,
          organic_position: i === 0 ? 1 : i,
          is_sponsored: i === 0,
          seller_online: s.online,
        },
        packages: [
          {
            name: "Basic Setup",
            price_usd: basePrice,
            description: `1 Page ${niche} setup + 1 Data Source Connection`,
            delivery_days: 1,
            revisions: 2,
            deliverables: ["Single page dashboard", "1 connected data source", "Basic KPIs"],
          },
          {
            name: "Standard Pro",
            price_usd: basePrice * 2,
            description: `Up to 3 Pages ${niche} + 3 Data Sources + Custom Filters`,
            delivery_days: 2,
            revisions: 4,
            deliverables: ["3 page dynamic report", "3 data sources", "Custom interactive filters", "Calculated metrics"],
          },
          {
            name: "Enterprise Complete",
            price_usd: basePrice * 4,
            description: `Full Multi-page ${niche} + Unlimited Sources + Video Walkthrough & 30 Days Support`,
            delivery_days: 4,
            revisions: "Unlimited",
            deliverables: ["Enterprise multi-page layout", "Unlimited connections", "Automated daily refresh", "Recorded video walkthrough", "30 days priority support"],
          },
        ],
        related_tags: [
          niche.toLowerCase(),
          "dashboard",
          "data visualization",
          "business intelligence",
          "automated reports",
        ],
      });
    }

    return results;
  }
}

export const crawler = new FiverrCrawler(storage);

export const crawlerManager = {
  startJob(niche: string, limit: number = 10) {
    const id = `job_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const job = storage.createJob(id, niche, limit);
    setTimeout(() => {
      crawler.runJob(id).catch((e) => console.error("Job runner error:", e));
    }, 50);
    return job;
  },

  listJobs(limit: number = 20) {
    return storage.listJobs(limit);
  },

  getJob(id: string) {
    return storage.getJob(id);
  },

  analyzeJob(id: string, force: boolean = false) {
    if (!force) {
      const cached = storage.getAnalysis(id);
      if (cached) return cached;
    }
    const job = storage.getJob(id);
    if (!job) return undefined;
    const gigs = storage.getAllJobResults(id);
    if (gigs.length === 0) return undefined;
    const analysis = MarketAnalyzer.analyze(job.niche, gigs, job.available_results);
    storage.saveAnalysis(id, analysis);
    return analysis;
  },

  cancelJob(id: string) {
    return storage.updateJob(id, { status: "cancelled", stage: "cancelled" });
  },
};
