import { test } from "node:test";
import assert from "node:assert/strict";
import { MarketAnalyzer } from "../src/market_analyzer.js";

// Helper to build a minimal gig record for analysis.
function gig(over: any = {}): any {
  return {
    url: "https://www.fiverr.com/seller/gig",
    title: "I will build an automated dashboard",
    seller_name: "Seller",
    seller_username: "seller",
    seller_level: "Level 2",
    seller_country: "United States",
    starting_price_usd: 50,
    rating: 4.9,
    review_count: 10,
    has_video: true,
    last_delivery: "1 day ago",
    search: { niche: "dashboard", global_position: 1, seller_online: true },
    related_tags: ["dashboard"],
    ...over,
  };
}

test("empty gig set does not crash and reports zero sample", () => {
  const a: any = MarketAnalyzer.analyze("niche", [], 0);
  assert.equal(a.overview.sampled_gigs, 0);
  assert.equal(a.market_health.summary.sampled_gigs, 0);
});

test("review-count median is derived from reviews, not prices", () => {
  const a: any = MarketAnalyzer.analyze("niche", [gig({ starting_price_usd: 50, review_count: 10 })], 0);
  // Previously this was price*1.5 = 75 (copy-paste bug). Must be ~10.
  assert.equal(a.overview.review_count.median, 10);
});

test("median for even-sized price groups is averaged, not upper element", () => {
  const gigs = [10, 20, 30, 40].map((p, i) =>
    gig({ url: `u${i}`, seller_name: `s${i}`, starting_price_usd: p, search: { global_position: i + 1, seller_online: true } })
  );
  const a: any = MarketAnalyzer.analyze("niche", gigs, 0);
  // median of [10,20,30,40] = 25
  assert.equal(a.overview.starting_price.median, 25);
});

test("parseLastDeliveryDays via health details: '21 days ago' is not read as 1 day", () => {
  const a: any = MarketAnalyzer.analyze(
    "niche",
    [gig({ last_delivery: "21 days ago", search: { global_position: 1, seller_online: false }, review_count: 5 })],
    0
  );
  const detail = a.market_health.details[0];
  assert.equal(detail.last_delivery_days, "21d");
});

test("exportRows maps every Lab tab to its own data (no silent fallback)", () => {
  const gigs = [gig()];
  const a: any = MarketAnalyzer.analyze("niche", gigs, 0);
  // overview -> overview row with sampled_gigs
  const overview = MarketAnalyzer.exportRows(a, "overview");
  assert.equal(overview[0].sampled_gigs, 1);
  // packages -> feature matrix, not health details
  const packages = MarketAnalyzer.exportRows(a, "packages");
  assert.ok(packages[0].feature, "packages should export feature matrix");
  // movement -> explanatory single row
  const movement = MarketAnalyzer.exportRows(a, "movement");
  assert.equal(movement[0].available, false);
  // reviews -> review summary
  const reviews = MarketAnalyzer.exportRows(a, "reviews");
  assert.ok("average_visible_rating" in reviews[0]);
  // unknown section -> empty (not an unrelated table)
  assert.deepEqual(MarketAnalyzer.exportRows(a, "does-not-exist"), []);
});

test("health status flags dead gigs (no reviews + offline + old delivery)", () => {
  const a: any = MarketAnalyzer.analyze(
    "niche",
    [gig({ review_count: 0, last_delivery: "3 months ago", search: { global_position: 1, seller_online: false } })],
    0
  );
  assert.equal(a.market_health.details[0].health_status, "Dead");
});
