import { test } from "node:test";
import assert from "node:assert/strict";
import { MarketAnalyzer } from "../src/market_analyzer.js";

// Helper: minimal gig with detail fields (packages, reviews) for analysis.
function gig(over: any = {}): any {
  return {
    url: `https://www.fiverr.com/seller/gig-${Math.random().toString(36).slice(2, 8)}`,
    title: "I will create looker studio dashboard",
    seller_name: "Seller",
    seller_username: "seller",
    seller_level: "Level 2",
    seller_country: "Pakistan",
    starting_price_usd: 50,
    rating: 4.8,
    review_count: 10,
    has_video: true,
    last_delivery: "1 day ago",
    search: { niche: "looker studio", global_position: 1, seller_online: true },
    related_tags: ["looker studio"],
    packages: [
      { name: "Basic", price_usd: 50, description: "1 page", delivery_days: 1, revisions: 2, features: { "Data source": true } },
      { name: "Standard", price_usd: 100, description: "3 pages", delivery_days: 2, revisions: 4, features: { "Data source": true, "Auto refresh": true } },
      { name: "Premium", price_usd: 200, description: "Full", delivery_days: 4, revisions: "Unlimited", features: { "Data source": true, "Auto refresh": true, "Video walkthrough": true } },
    ],
    visible_reviews: [
      { rating: 5, comment: "Great work, fast delivery and very professional", buyer_country: "United States" },
      { rating: 4, comment: "Good quality dashboard", buyer_country: "Germany" },
    ],
    ...over,
  };
}

test("rating.mean is computed from real gig ratings (not hardcoded 4.95)", () => {
  const a: any = MarketAnalyzer.analyze(
    "niche",
    [gig({ rating: 4.5 }), gig({ rating: 5.0 })],
    0
  );
  assert.ok(Math.abs(a.overview.rating.mean - 4.75) < 0.001);
  assert.ok(Math.abs(a.overview.rating.median - 4.75) < 0.001);
});

test("available_results is honest — no 4x sample inflation when reader gives no total", () => {
  const gigs = Array.from({ length: 10 }, (_, i) => gig({ search: { global_position: i + 1, seller_online: true } }));
  const a: any = MarketAnalyzer.analyze("niche", gigs, 0);
  assert.equal(a.overview.available_results, 10);
  assert.equal(a.overview.available_results_is_estimate, true);

  const a2: any = MarketAnalyzer.analyze("niche", gigs, 350);
  assert.equal(a2.overview.available_results, 350);
  assert.equal(a2.overview.available_results_is_estimate, false);
});

test("detail_coverage_pct reflects fetch failures (not hardcoded 100)", () => {
  const failed: any = { url: "x", title: "t", error: "HTTP 404" };
  const a: any = MarketAnalyzer.analyze("niche", [gig(), failed], 0);
  assert.equal(a.overview.detail_coverage_pct, 50);
});

test("review sentiment is computed from real review text", () => {
  const g: any = gig({
    visible_reviews: [
      { rating: 5, comment: "amazing fast professional, highly recommended" },
      { rating: 2, comment: "slow response, poor quality, disappointed" },
    ],
  });
  const a: any = MarketAnalyzer.analyze("niche", [g], 0);
  assert.equal(a.reviews.visible_reviews_analyzed, 2);
  const s = Object.fromEntries(a.reviews.sentiment.map((r: any) => [r.label, r.count]));
  assert.equal(s.positive, 1);
  assert.equal(s.negative, 1);
  // average_visible_rating from real review ratings (5, 2) -> 3.5
  assert.equal(a.reviews.average_visible_rating, 3.5);
  // buyer countries real
  const g2: any = gig({ visible_reviews: [{ rating: 5, comment: "great", buyer_country: "Canada" }] });
  const a2: any = MarketAnalyzer.analyze("niche", [g2], 0);
  assert.deepEqual(a2.reviews.buyer_countries, [{ label: "Canada", count: 1 }]);
});

test("keyword clusters are real (shared bigrams cluster via Jaccard)", () => {
  const gigs = [
    gig({ title: "I will build automated looker studio dashboard", search: { global_position: 1, seller_online: true } }),
    gig({ title: "I will create automated looker studio reports", search: { global_position: 2, seller_online: true } }),
    gig({ title: "I will design looker studio dashboard fix", search: { global_position: 3, seller_online: true } }),
  ];
  const a: any = MarketAnalyzer.analyze("looker studio", gigs, 0);
  assert.ok(Array.isArray(a.keyword_clusters));
  assert.ok(a.keyword_clusters.length >= 1, "expected at least one real cluster");
  const first = a.keyword_clusters[0];
  assert.ok(first.gig_count >= 2);
  assert.ok(first.phrases.length >= 2);
  assert.ok(typeof first.share_pct === "number");
  assert.ok(typeof first.median_price === "number" || first.median_price === null);
});

test("package tiers + feature matrix come from real package data", () => {
  const a: any = MarketAnalyzer.analyze("niche", [gig(), gig({ starting_price_usd: 60 })], 0);
  // Basic tier: real prices [50, 50] -> median 50
  assert.equal(a.pricing.package_tiers.Basic.median, 50);
  assert.equal(a.pricing.package_tiers.Premium.median, 200);
  // premium/basic multiplier [4, 4]
  assert.equal(a.pricing.premium_to_basic_multiplier.median, 4);
  // feature matrix: "data source" in all 2 gigs (100%), "video walkthrough" only premium tier
  const fm = Object.fromEntries(a.packages.feature_matrix.map((f: any) => [f.feature, f]));
  assert.equal(fm["data source"].gig_count, 2);
  assert.equal(fm["data source"].basic_count, 2);
  assert.equal(fm["video walkthrough"].premium_count, 2);
  assert.equal(a.packages.gigs_with_packages, 2);
  // tier counts real: 2 gigs x 3 tiers
  const tiers = Object.fromEntries(a.packages.tier_counts.map((t: any) => [t.tier, t.count]));
  assert.equal(tiers.Basic, 2);
  assert.equal(tiers.Standard, 2);
  assert.equal(tiers.Premium, 2);
});

test("pricing histogram is dynamic and real", () => {
  const gigs = [10, 20, 80, 120].map((p, i) => gig({ starting_price_usd: p, search: { global_position: i + 1, seller_online: true } }));
  const a: any = MarketAnalyzer.analyze("niche", gigs, 0);
  const total = a.pricing.histogram.reduce((s: number, b: any) => s + b.count, 0);
  assert.equal(total, 4);
  assert.equal(a.pricing.overall.min, 10);
  assert.equal(a.pricing.overall.max, 120);
});

test("competitors table carries real seller_country / has_video / package_count", () => {
  const a: any = MarketAnalyzer.analyze("niche", [gig({ seller_country: "Pakistan", has_video: false, packages: [] })], 0);
  assert.equal(a.competitors[0].seller_country, "Pakistan");
  assert.equal(a.competitors[0].has_video, false);
  assert.equal(a.competitors[0].package_count, 0);
});

test("rank movement compares against a real previous snapshot", () => {
  const gigs = [
    gig({ url: "https://www.fiverr.com/a/one", search: { global_position: 2, seller_online: true } }),
    gig({ url: "https://www.fiverr.com/a/two", search: { global_position: 1, seller_online: true } }),
    gig({ url: "https://www.fiverr.com/a/new", search: { global_position: 3, seller_online: true } }),
  ];
  const prev = [
    { url: "https://www.fiverr.com/a/one", rank: 5, captured_at: "2026-08-01T00:00:00Z" },
    { url: "https://www.fiverr.com/a/two", rank: 1, captured_at: "2026-08-01T00:00:00Z" },
    { url: "https://www.fiverr.com/a/gone", rank: 2, captured_at: "2026-08-01T00:00:00Z" },
  ];
  const a: any = MarketAnalyzer.analyze("niche", gigs, 0, prev);
  assert.equal(a.rank_movement.available, true);
  const byUrl = Object.fromEntries(a.rank_movement.movements.map((m: any) => [m.url, m]));
  assert.equal(byUrl["https://www.fiverr.com/a/one"].movement, "up");
  assert.equal(byUrl["https://www.fiverr.com/a/two"].movement, "stable");
  assert.equal(byUrl["https://www.fiverr.com/a/new"].movement, "new");

  const b: any = MarketAnalyzer.analyze("niche", gigs, 0, null);
  assert.equal(b.rank_movement.available, false);
  assert.ok(b.rank_movement.reason);
});

test("market gaps keyword opportunities are derived from real stats", () => {
  const gigs = Array.from({ length: 6 }, (_, i) =>
    gig({
      title: "I will build automated looker studio dashboard",
      starting_price_usd: 80,
      search: { global_position: i + 1, seller_online: true },
    })
  );
  const a: any = MarketAnalyzer.analyze("looker studio", gigs, 0);
  assert.ok(a.market_gaps.keyword_opportunities.length >= 1);
  const opp = a.market_gaps.keyword_opportunities[0];
  assert.equal(opp.gig_count, 6);
  assert.ok(opp.evidence.includes("6 of 6"));
});
