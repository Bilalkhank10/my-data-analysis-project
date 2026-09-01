import { GigResult, GigReview } from "./types.js";
import { utcNow } from "./storage.js";

const STOPWORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
  "from", "get", "i", "in", "is", "it", "me", "my", "of", "on", "or",
  "our", "that", "the", "this", "to", "we", "will", "with", "you", "your",
  "aka", "using", "use", "make", "professional", "best", "expert", "service",
  "services", "custom", "create", "build", "provide", "design", "help",
]);

// Generic tokens excluded from cluster token-sets (ported from the Python
// analyzer — the source of truth for this module).
const CLUSTER_GENERIC = new Set([
  "dashboard", "dashboards", "report", "reports", "data", "studio", "create",
  "professional", "custom", "service", "services", "expert", "using",
]);

const POSITIVE_WORDS = new Set([
  "accurate", "amazing", "awesome", "clear", "excellent", "exceptional", "fast",
  "great", "helpful", "impressed", "outstanding", "patient", "perfect",
  "professional", "quality", "quick", "recommend", "responsive", "satisfied",
  "skilled", "smooth", "timely", "wonderful",
]);

const NEGATIVE_WORDS = new Set([
  "bad", "confusing", "delay", "delayed", "disappointed", "error", "errors",
  "inaccurate", "issue", "issues", "late", "missing", "poor", "problem",
  "problems", "revision", "slow", "unprofessional", "unresponsive", "wrong",
]);

function parseNumber(val: any): number | null {
  if (typeof val === "number") return isNaN(val) ? null : val;
  if (typeof val === "string") {
    const match = val.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    return match ? parseFloat(match[0]) : null;
  }
  return null;
}

function quantile(sorted: number[], p: number): number | null {
  if (!sorted.length) return null;
  if (sorted.length === 1) return sorted[0];
  const pos = (sorted.length - 1) * p;
  const lower = Math.floor(pos);
  const upper = Math.ceil(pos);
  if (lower === upper) return sorted[lower];
  const frac = pos - lower;
  return sorted[lower] * (1 - frac) + sorted[upper] * frac;
}

// Median of an unsorted array (mutates a copy). Returns null when empty.
function medianOf(values: number[]): number | null {
  const sorted = values.slice().sort((a, b) => a - b);
  return quantile(sorted, 0.5);
}

function meanOf(values: (number | null | undefined)[]): number | null {
  const clean = values.filter((v): v is number => v !== null && v !== undefined && isFinite(v));
  if (!clean.length) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

function round1(n: number | null | undefined): number | null {
  return n === null || n === undefined || !isFinite(n) ? null : Math.round(n * 10) / 10;
}

export interface NumericStats {
  count: number;
  min: number | null;
  q1: number | null;
  median: number | null;
  mean: number | null;
  q3: number | null;
  p90: number | null;
  max: number | null;
}

function calcNumericStats(values: (number | null | undefined)[]): NumericStats {
  const clean = values
    .map(parseNumber)
    .filter((v): v is number => v !== null && isFinite(v))
    .sort((a, b) => a - b);

  if (!clean.length) {
    return { count: 0, min: null, q1: null, median: null, mean: null, q3: null, p90: null, max: null };
  }

  const sum = clean.reduce((a, b) => a + b, 0);
  const mean = Math.round((sum / clean.length) * 100) / 100;

  return {
    count: clean.length,
    min: clean[0],
    q1: quantile(clean, 0.25),
    median: quantile(clean, 0.5),
    mean,
    q3: quantile(clean, 0.75),
    p90: quantile(clean, 0.9),
    max: clean[clean.length - 1],
  };
}

function parseLastDeliveryDays(text?: string): number | null {
  if (!text) return null;
  const t = text.toLowerCase();
  if (t.includes("hour") || t.includes("minute") || t.includes("today") || t.includes("just now")) return 0.5;
  // Check explicit numeric units first. Otherwise "21 days ago" would match the
  // loose "1 day" substring below and be misread as 1 day.
  const dayMatch = t.match(/(\d+)\s+day/);
  if (dayMatch) return parseInt(dayMatch[1], 10);
  const weekMatch = t.match(/(\d+)\s+week/);
  if (weekMatch) return parseInt(weekMatch[1], 10) * 7;
  const monthMatch = t.match(/(\d+)\s+month/);
  if (monthMatch) return parseInt(monthMatch[1], 10) * 30;
  const yearMatch = t.match(/(\d+)\s+year/);
  if (yearMatch) return parseInt(yearMatch[1], 10) * 365;
  if (t.includes("yesterday") || /\b1\s*day/.test(t) || t.includes("a day")) return 1;
  return null;
}

// ---------------------------------------------------------------------------
// Phrase statistics (with per-phrase gig indexes for clustering/gap analysis)
// ---------------------------------------------------------------------------

interface PhraseStat {
  count: number;
  top20: number;
  prices: number[];
  ranks: number[];
  reviews: number[];
  gigs: Set<number>;
}

function newPhraseStat(): PhraseStat {
  return { count: 0, top20: 0, prices: [], ranks: [], reviews: [], gigs: new Set() };
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 1);
}

// ---------------------------------------------------------------------------
// Keyword clusters (ported from the Python analyzer: union-find over
// bigrams/trigrams with Jaccard >= 0.5 or >= 2 shared non-generic tokens).
// ---------------------------------------------------------------------------

function buildClusters(
  bigrams: Map<string, PhraseStat>,
  trigrams: Map<string, PhraseStat>,
  gigs: GigResult[]
): Array<Record<string, any>> {
  const phraseGigs = new Map<string, Set<number>>();
  for (const map of [bigrams, trigrams]) {
    for (const [phrase, d] of map) {
      if (d.gigs.size >= 2) phraseGigs.set(phrase, d.gigs);
    }
  }
  const phrases = Array.from(phraseGigs.keys())
    .sort((a, b) => {
      const sa = phraseGigs.get(a)!.size;
      const sb = phraseGigs.get(b)!.size;
      return sb - sa || a.localeCompare(b);
    })
    .slice(0, 100);

  if (phrases.length < 2) return [];

  const parent = phrases.map((_, i) => i);
  const find = (index: number): number => {
    while (parent[index] !== index) {
      parent[index] = parent[parent[index]];
      index = parent[index];
    }
    return index;
  };
  const union = (a: number, b: number): void => {
    const rootA = find(a);
    const rootB = find(b);
    if (rootA !== rootB) parent[rootB] = rootA;
  };

  const tokenSets = phrases.map((p) => new Set(p.split(" ").filter((t) => !CLUSTER_GENERIC.has(t))));
  for (let i = 0; i < phrases.length; i++) {
    for (let j = i + 1; j < phrases.length; j++) {
      let left = tokenSets[i];
      let right = tokenSets[j];
      if (!left.size || !right.size) {
        left = new Set(phrases[i].split(" "));
        right = new Set(phrases[j].split(" "));
      }
      let overlap = 0;
      for (const t of left) if (right.has(t)) overlap++;
      const unionSize = left.size + right.size - overlap;
      const jaccard = unionSize ? overlap / unionSize : 0;
      if (jaccard >= 0.5 || overlap >= 2) union(i, j);
    }
  }

  const groups = new Map<number, number[]>();
  for (let index = 0; index < phrases.length; index++) {
    const root = find(index);
    const list = groups.get(root) || [];
    list.push(index);
    groups.set(root, list);
  }

  const totalGigs = gigs.length;
  const rows: Array<Record<string, any>> = [];
  for (const indexes of groups.values()) {
    if (indexes.length < 2) continue;
    const members = indexes.map((i) => phrases[i]);
    const gigIndexes = new Set<number>();
    const tokenCounter = new Map<string, number>();
    for (const phrase of members) {
      const gigsSet = phraseGigs.get(phrase)!;
      for (const gi of gigsSet) gigIndexes.add(gi);
      for (const token of phrase.split(" ")) {
        if (CLUSTER_GENERIC.has(token)) continue;
        tokenCounter.set(token, (tokenCounter.get(token) || 0) + gigsSet.size);
      }
    }
    if (gigIndexes.size < 2) continue;
    const labelTokens = Array.from(tokenCounter.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 2)
      .map(([t]) => t);
    const label = labelTokens.length ? labelTokens.join(" ") : members[0];
    const selected = Array.from(gigIndexes).filter((i) => i < gigs.length).map((i) => gigs[i]);
    const ranks = selected.map((g) => g.search?.global_position).filter((r): r is number => r != null);
    const prices = selected.map((g) => g.starting_price_usd).filter((p): p is number => p != null);
    rows.push({
      cluster: label,
      phrases: members
        .sort((a, b) => {
          const sa = phraseGigs.get(a)!.size;
          const sb = phraseGigs.get(b)!.size;
          return sb - sa || a.localeCompare(b);
        })
        .slice(0, 15),
      phrase_count: members.length,
      gig_count: gigIndexes.size,
      share_pct: totalGigs ? round1((100 * gigIndexes.size) / totalGigs) : 0,
      average_rank: ranks.length ? round1(meanOf(ranks)) : null,
      median_price: medianOf(prices),
    });
  }
  rows.sort((a, b) => b.gig_count - a.gig_count || String(a.cluster).localeCompare(String(b.cluster)));
  return rows.slice(0, 40);
}

// ---------------------------------------------------------------------------
// Reviews: real sentiment over crawled visible reviews
// ---------------------------------------------------------------------------

function buildReviews(gigs: GigResult[]): Record<string, any> {
  const reviewRows: GigReview[] = [];
  const phraseCounts = new Map<string, { count: number; gigs: Set<number> }>();
  const sentiment = { positive: 0, neutral: 0, negative: 0 };
  const praise = new Map<string, number>();
  const concerns = new Map<string, number>();
  const countries = new Map<string, number>();
  let samples = 0;
  let responses = 0;

  gigs.forEach((g, gi) => {
    const reviews = g.visible_reviews || [];
    for (const review of reviews) {
      reviewRows.push(review);
      const text = review.comment || "";
      const tokens = tokenize(text);
      let positive = 0;
      let negative = 0;
      for (const token of tokens) {
        if (POSITIVE_WORDS.has(token)) {
          positive++;
          praise.set(token, (praise.get(token) || 0) + 1);
        }
        if (NEGATIVE_WORDS.has(token)) {
          negative++;
          concerns.set(token, (concerns.get(token) || 0) + 1);
        }
      }
      if (positive > negative) sentiment.positive++;
      else if (negative > positive) sentiment.negative++;
      else sentiment.neutral++;

      // Bigrams + trigrams from review text (for top phrases + gap analysis).
      for (let i = 0; i + 1 < tokens.length; i++) {
        const big = `${tokens[i]} ${tokens[i + 1]}`;
        const d = phraseCounts.get(big) || { count: 0, gigs: new Set() };
        d.count++;
        d.gigs.add(gi);
        phraseCounts.set(big, d);
      }
      for (let i = 0; i + 2 < tokens.length; i++) {
        const tri = tokens.slice(i, i + 3).join(" ");
        const d = phraseCounts.get(tri) || { count: 0, gigs: new Set() };
        d.count++;
        d.gigs.add(gi);
        phraseCounts.set(tri, d);
      }

      if (review.buyer_country) countries.set(review.buyer_country, (countries.get(review.buyer_country) || 0) + 1);
      if (review.work_sample) samples++;
      if (review.seller_response) responses++;
    }
  });

  const total = reviewRows.length;
  const ratings = reviewRows.map((r) => r.rating).filter((r): r is number => r != null && isFinite(r));
  const topPhrases = Array.from(phraseCounts.entries())
    .filter(([, d]) => d.count >= 2)
    .sort((a, b) => b[1].count - a[1].count || a[0].localeCompare(b[0]))
    .slice(0, 25)
    .map(([phrase, d]) => ({ phrase, review_count: d.count, gig_count: d.gigs.size }));

  const topTerms = (map: Map<string, number>) =>
    Array.from(map.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 12)
      .map(([term, count]) => ({ term, count }));

  return {
    visible_reviews_analyzed: total,
    average_visible_rating: ratings.length ? round1(meanOf(ratings)) : null,
    ongoing_collaboration_share_pct: null, // not parsed from public reader markdown
    work_sample_share_pct: total ? round1((100 * samples) / total) : 0,
    seller_response_share_pct: total ? round1((100 * responses) / total) : 0,
    sentiment: (["positive", "neutral", "negative"] as const).map((label) => ({
      label,
      count: sentiment[label],
      share_pct: total ? round1((100 * sentiment[label]) / total) : 0,
    })),
    praise_terms: topTerms(praise),
    concern_terms: topTerms(concerns),
    top_phrases: topPhrases,
    buyer_countries: Array.from(countries.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 30)
      .map(([label, count]) => ({ label, count })),
  };
}

// ---------------------------------------------------------------------------
// Packages & pricing: real data from crawled package tables
// ---------------------------------------------------------------------------

function buildPackages(gigs: GigResult[]): Record<string, any> {
  const tierCounts = new Map<string, number>();
  const deliveries = new Map<string, Map<string, number>>();
  const revisions = new Map<string, Map<string, number>>();
  const featureTierCounts = new Map<string, Map<string, number>>();
  const featureGigs = new Map<string, Set<number>>();
  let gigsWithPackages = 0;

  gigs.forEach((g, index) => {
    const packages = g.packages || [];
    if (packages.length) gigsWithPackages++;
    const seenTiers = new Set<string>();
    for (const pkg of packages) {
      const tier = (pkg.name || "Unknown").trim();
      if (!seenTiers.has(tier)) {
        tierCounts.set(tier, (tierCounts.get(tier) || 0) + 1);
        seenTiers.add(tier);
      }
      if (pkg.delivery_days) {
        const label = `${pkg.delivery_days} Day${pkg.delivery_days > 1 ? "s" : ""} Delivery`;
        const map = deliveries.get(tier) || new Map();
        map.set(label, (map.get(label) || 0) + 1);
        deliveries.set(tier, map);
      }
      if (pkg.revisions) {
        const label = String(pkg.revisions);
        const map = revisions.get(tier) || new Map();
        map.set(label, (map.get(label) || 0) + 1);
        revisions.set(tier, map);
      }
      for (const [feature, value] of Object.entries(pkg.features || {})) {
        const normalized = String(feature).trim().toLowerCase();
        if (!normalized) continue;
        if (value === null || value === undefined || value === "" || value === false) continue;
        const tierMap = featureTierCounts.get(normalized) || new Map();
        tierMap.set(tier, (tierMap.get(tier) || 0) + 1);
        featureTierCounts.set(normalized, tierMap);
        const gigSet = featureGigs.get(normalized) || new Set();
        gigSet.add(index);
        featureGigs.set(normalized, gigSet);
      }
    }
  });

  const featureRows = Array.from(featureTierCounts.entries())
    .map(([feature, counts]) => ({
      feature,
      gig_count: featureGigs.get(feature)!.size,
      overall_coverage_pct: gigsWithPackages ? round1((100 * featureGigs.get(feature)!.size) / gigsWithPackages) : 0,
      basic_count: counts.get("Basic") || 0,
      standard_count: counts.get("Standard") || 0,
      premium_count: counts.get("Premium") || 0,
    }))
    .sort((a, b) => b.gig_count - a.gig_count || a.feature.localeCompare(b.feature))
    .slice(0, 100);

  const counterToRows = (map: Map<string, number>) =>
    Array.from(map.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 20)
      .map(([label, count]) => ({ label, count }));

  return {
    gigs_with_packages: gigsWithPackages,
    tier_counts: Array.from(tierCounts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([tier, count]) => ({ tier, count })),
    delivery_patterns: Object.fromEntries(
      Array.from(deliveries.entries()).map(([tier, counter]) => [tier, counterToRows(counter)])
    ),
    revision_patterns: Object.fromEntries(
      Array.from(revisions.entries()).map(([tier, counter]) => [tier, counterToRows(counter)])
    ),
    feature_matrix: featureRows,
  };
}

function buildPricing(gigs: GigResult[]): Record<string, any> {
  const overallValues = gigs.map((g) => g.starting_price_usd).filter((p): p is number => p != null && isFinite(p));
  const stats = calcNumericStats(overallValues);

  // Dynamic histogram (ported from Python: width scales with the max price).
  const histogram: Array<Record<string, any>> = [];
  if (overallValues.length) {
    const maximum = Math.max(...overallValues);
    const width = maximum <= 100 ? 10 : maximum <= 250 ? 25 : maximum <= 500 ? 50 : 100;
    const upper = Math.max(width, Math.ceil(maximum / width) * width);
    for (let start = 0; start < upper; start += width) {
      const end = start + width;
      const count = overallValues.filter((v) => v >= start && (v < end || (end === upper && v === end))).length;
      histogram.push({ label: `$${start}–$${end}`, min: start, max: end, count });
    }
  }

  // Real per-tier package prices (Basic/Standard/Premium) from the packages.
  const tierValues = new Map<string, number[]>();
  const multipliers: number[] = [];
  for (const g of gigs) {
    const byTier = new Map<string, number>();
    for (const pkg of g.packages || []) {
      const name = (pkg.name || "").trim();
      const price = pkg.price_usd;
      if (!name || price == null || !isFinite(price)) continue;
      const key = name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
      if (!byTier.has(key)) byTier.set(key, price);
      const list = tierValues.get(key) || [];
      list.push(price);
      tierValues.set(key, list);
    }
    const basic = byTier.get("Basic");
    const premium = byTier.get("Premium");
    if (basic && premium && basic > 0) multipliers.push(premium / basic);
  }

  const byLevel = new Map<string, number[]>();
  const byPlacement = new Map<string, number[]>();
  for (const g of gigs) {
    if (g.starting_price_usd == null) continue;
    const level = g.seller_level || "Unknown";
    byLevel.set(level, [...(byLevel.get(level) || []), g.starting_price_usd]);
    const placement = g.search?.is_sponsored ? "Sponsored" : "Organic";
    byPlacement.set(placement, [...(byPlacement.get(placement) || []), g.starting_price_usd]);
  }

  // IQR outliers (ported from Python).
  const q1 = stats.q1;
  const q3 = stats.q3;
  const outlierThreshold = q1 !== null && q3 !== null ? q3 + 1.5 * (q3 - q1) : null;
  const outliers: Array<Record<string, any>> = [];
  if (outlierThreshold !== null) {
    for (const g of gigs) {
      if ((g.starting_price_usd || 0) > outlierThreshold) {
        outliers.push({
          url: g.url,
          title: g.title,
          seller: g.seller_name || g.seller_username,
          price: g.starting_price_usd,
        });
      }
    }
  }

  return {
    overall: stats,
    histogram,
    package_tiers: Object.fromEntries(
      Array.from(tierValues.entries())
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([name, values]) => [name, calcNumericStats(values)])
    ),
    premium_to_basic_multiplier: calcNumericStats(multipliers),
    by_seller_level: Array.from(byLevel.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([segment, values]) => ({ segment, ...calcNumericStats(values) })),
    by_placement: Array.from(byPlacement.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([segment, values]) => ({ segment, ...calcNumericStats(values) })),
    outlier_threshold: outlierThreshold !== null ? round1(outlierThreshold) : null,
    outliers: outliers.slice(0, 50),
  };
}

// ---------------------------------------------------------------------------
// Market gaps: derived from REAL crawled data (titles, review text, packages)
// ---------------------------------------------------------------------------

function buildMarketGaps(
  gigs: GigResult[],
  bigramStats: Map<string, PhraseStat>,
  reviewPhrases: Map<string, { count: number; gigs: Set<number> }>,
  packages: Record<string, any>
): Record<string, any> {
  const totalGigs = gigs.length;

  // 1. Keyword opportunities: top bigrams validated by real rank/price stats.
  const titleWordSets = gigs.map((g) => new Set(tokenize(g.title || "")));
  const opportunities = Array.from(bigramStats.entries())
    .filter(([, d]) => d.count >= 2)
    .map(([phrase, d]) => {
      const ranks = d.ranks.length ? meanOf(d.ranks) : null;
      const medianPrice = medianOf(d.prices);
      const inTop20 = d.top20;
      // Data-driven score: rank validation (40) + top-20 presence (30) +
      // price potential (30). All inputs are real crawled statistics.
      let score = 0;
      if (ranks !== null) score += Math.max(0, 40 - (ranks - 1) * 2);
      score += Math.min(30, inTop20 * 10);
      if (medianPrice !== null) score += Math.min(30, (medianPrice / 10) * 3);
      return {
        phrase,
        gig_count: d.count,
        average_rank: round1(ranks),
        median_price: medianPrice !== null ? `$${Math.round(medianPrice)}` : null,
        top_20_count: inTop20,
        opportunity_score: `${Math.round(Math.max(0, Math.min(100, score)))} / 100`,
        evidence: `Appears in ${d.count} of ${totalGigs} sampled titles; avg rank ${ranks !== null ? Math.round(ranks) : "n/a"}; median price ${medianPrice !== null ? `$${Math.round(medianPrice)}` : "n/a"}`,
      };
    })
    .sort((a, b) => parseInt(b.opportunity_score) - parseInt(a.opportunity_score) || b.gig_count - a.gig_count)
    .slice(0, 10);

  // 2. Review-language gaps: phrases buyers use that titles under-use.
  const reviewLanguageGaps = Array.from(reviewPhrases.entries())
    .filter(([phrase, d]) => d.count >= 2 && d.gigs.size >= 2)
    .map(([phrase, d]) => {
      const words = new Set(tokenize(phrase));
      let inTitles = 0;
      titleWordSets.forEach((set) => {
        for (const w of words) if (set.has(w)) {
          inTitles++;
          break;
        }
      });
      return {
        phrase,
        review_gig_count: d.gigs.size,
        title_gig_count: inTitles,
        gap_type: inTitles < d.gigs.size * 0.5 ? "Under-represented in Gig Titles" : "Aligned with titles",
      };
    })
    .filter((r) => r.gap_type === "Under-represented in Gig Titles")
    .sort((a, b) => b.review_gig_count - a.review_gig_count)
    .slice(0, 10);

  // 3. Feature gaps: rare overall but common among top-10 ranked gigs.
  const featureGigsAll = new Map<string, Set<number>>();
  const featureGigsTop10 = new Map<string, Set<number>>();
  gigs.forEach((g, i) => {
    const isTop10 = (g.search?.global_position || 999) <= 10;
    for (const pkg of g.packages || []) {
      for (const [feature, value] of Object.entries(pkg.features || {})) {
        const norm = String(feature).trim().toLowerCase();
        if (!norm || value === null || value === undefined || value === "" || value === false) continue;
        if (!featureGigsAll.has(norm)) featureGigsAll.set(norm, new Set());
        featureGigsAll.get(norm)!.add(i);
        if (isTop10) {
          if (!featureGigsTop10.has(norm)) featureGigsTop10.set(norm, new Set());
          featureGigsTop10.get(norm)!.add(i);
        }
      }
    }
  });
  const top10Count = Math.min(10, gigs.length);
  const offerFeatureGaps = Array.from(featureGigsAll.entries())
    .map(([feature, allSet]) => {
      const overall = allSet.size / totalGigs;
      const topSet = featureGigsTop10.get(feature);
      const topShare = topSet && top10Count ? topSet.size / top10Count : 0;
      return { feature, overall_coverage_pct: round1(100 * overall), top10_coverage_pct: round1(100 * topShare) };
    })
    .filter((f) => (f.overall_coverage_pct ?? 0) < 40 && (f.top10_coverage_pct || 0) >= 40)
    .sort((a, b) => (b.top10_coverage_pct || 0) - (a.top10_coverage_pct || 0))
    .slice(0, 10)
    .map((f) => ({
      feature: f.feature,
      overall_coverage_pct: f.overall_coverage_pct,
      top10_coverage_pct: f.top10_coverage_pct,
      gap_type: "Top Sellers Include It, General Gigs Omit It",
    }));

  return {
    formula: {
      warning:
        "Opportunities are computed from the crawled sample (phrase frequency, real rank and price stats, review-vs-title overlap, package feature coverage). They are estimates, not Fiverr search-volume data.",
    },
    keyword_opportunities: opportunities,
    review_language_gaps: reviewLanguageGaps,
    offer_feature_gaps: offerFeatureGaps,
  };
}

// ---------------------------------------------------------------------------
// Rank movement: real comparison against a previous snapshot (if available)
// ---------------------------------------------------------------------------

export interface RankSnapshot {
  url: string;
  rank: number;
  captured_at: string;
}

function buildRankMovement(gigs: GigResult[], previous: RankSnapshot[] | null): Record<string, any> {
  if (!previous || !previous.length) {
    return {
      available: false,
      reason: "A previous historical crawl of the same niche is required for comparative movement analysis.",
    };
  }
  const prevByURL = new Map(previous.map((p) => [p.url, p]));
  const movements: Array<Record<string, any>> = [];
  for (const g of gigs) {
    if (g.error) continue;
    const prev = g.url ? prevByURL.get(g.url) : undefined;
    const current = g.search?.global_position;
    if (!current) continue;
    if (!prev) {
      movements.push({ url: g.url, title: g.title, previous_rank: null, current_rank: current, movement: "new" });
    } else if (prev.rank === current) {
      movements.push({ url: g.url, title: g.title, previous_rank: prev.rank, current_rank: current, movement: "stable" });
    } else if (current < prev.rank) {
      movements.push({ url: g.url, title: g.title, previous_rank: prev.rank, current_rank: current, movement: "up" });
    } else {
      movements.push({ url: g.url, title: g.title, previous_rank: prev.rank, current_rank: current, movement: "down" });
    }
  }
  return {
    available: true,
    compared_against: previous[0].captured_at,
    movements: movements.slice(0, 100),
  };
}

// ---------------------------------------------------------------------------
// Main analyzer
// ---------------------------------------------------------------------------

export class MarketAnalyzer {
  static analyze(
    niche: string,
    gigs: GigResult[],
    totalAvailable: number = 0,
    previousSnapshot: RankSnapshot[] | null = null
  ): any {
    const totalGigs = gigs.length;
    // Honest totals: use the reader-reported result count when the search
    // page provided one; otherwise report the sample size (no inflated guess).
    const reportedResults = totalAvailable > 0 ? totalAvailable : totalGigs;

    // 1. Health Calculation
    let activeSuccess = 0;
    let deadFetchFailed = 0;
    let onlineNow = 0;
    let offline = 0;
    let withReviews = 0;
    let noReviews = 0;
    let recent7d = 0;
    let recent30d = 0;
    let dormant90d = 0;
    let unknownDelivery = 0;
    let fullyActive = 0;
    let noActivityDead = 0;

    const healthDetails = gigs.map((g, idx) => {
      const isFailed = Boolean(g.error);
      const isOnline = Boolean(g.search?.seller_online);
      const revCount = g.review_count || 0;
      const days = parseLastDeliveryDays(g.last_delivery);

      if (isFailed) deadFetchFailed++;
      else activeSuccess++;

      if (isOnline) onlineNow++;
      else offline++;

      if (revCount > 0) withReviews++;
      else noReviews++;

      if (days !== null) {
        if (days <= 7) recent7d++;
        else if (days <= 30) recent30d++;
        else if (days >= 90) dormant90d++;
      } else {
        unknownDelivery++;
      }

      let healthStatus = "Active";
      let deadReason = "";

      if (isFailed) {
        healthStatus = "Dead";
        deadReason = "Fetch Failed (404/Paused)";
      } else if (revCount === 0 && !isOnline && (days === null || days > 60)) {
        healthStatus = "Dead";
        deadReason = "No Reviews + Offline + No Recent Orders";
        noActivityDead++;
      } else if (isOnline && (days !== null && days <= 30)) {
        healthStatus = "Fully Active";
        fullyActive++;
      }

      return {
        global_position: g.search?.global_position || idx + 1,
        title: g.title,
        seller_level: g.seller_level || "New Seller",
        price: g.starting_price_usd ? `$${g.starting_price_usd}` : "—",
        review_count: revCount,
        seller_online: isOnline ? "Yes" : "No",
        last_delivery_raw: g.last_delivery || "Unknown",
        last_delivery_days: days !== null ? `${days}d` : "—",
        health_status: healthStatus,
        dead_reason: deadReason || "Alive",
        url: g.url,
      };
    });

    const activeRatePct = totalGigs > 0 ? Math.round((activeSuccess / totalGigs) * 1000) / 10 : 100;
    const onlineRatePct = totalGigs > 0 ? Math.round((onlineNow / totalGigs) * 1000) / 10 : 0;
    const estTotalActive = Math.round((reportedResults * activeRatePct) / 100);
    const deadSharePct = totalGigs > 0 ? Math.round((noActivityDead / totalGigs) * 1000) / 10 : 0;
    const estTotalDead = Math.round((reportedResults * deadSharePct) / 100);

    // Grouping by Seller Level
    const levelMap = new Map<string, { total: number; active: number; online: number; no_reviews: number; dead: number; fully: number; recent30: number; prices: number[] }>();
    for (const g of gigs) {
      const lvl = g.seller_level || "New Seller";
      const item = levelMap.get(lvl) || { total: 0, active: 0, online: 0, no_reviews: 0, dead: 0, fully: 0, recent30: 0, prices: [] };
      item.total++;
      if (!g.error) item.active++;
      if (g.search?.seller_online) item.online++;
      if (!g.review_count) item.no_reviews++;
      const days = parseLastDeliveryDays(g.last_delivery);
      if (days !== null && days <= 30) item.recent30++;
      if (g.search?.seller_online && days !== null && days <= 30) item.fully++;
      if (!g.review_count && !g.search?.seller_online && (days === null || days > 60)) item.dead++;
      if (g.starting_price_usd) item.prices.push(g.starting_price_usd);
      levelMap.set(lvl, item);
    }

    const byLevel = Array.from(levelMap.entries()).map(([lvl, data]) => ({
      level: lvl,
      total: data.total,
      active: data.active,
      online: data.online,
      no_reviews: data.no_reviews,
      no_activity_dead: data.dead,
      fully_active: data.fully,
      recent_30d: data.recent30,
      median_price: medianOf(data.prices) !== null ? Math.round(medianOf(data.prices) as number) : null,
      share_pct: totalGigs > 0 ? Math.round((data.total / totalGigs) * 100) : 0,
    }));

    // Grouping by Country
    const countryMap = new Map<string, { total: number; active: number; online: number; no_reviews: number; recent30: number; prices: number[] }>();
    for (const g of gigs) {
      const country = g.seller_country || "Worldwide";
      const item = countryMap.get(country) || { total: 0, active: 0, online: 0, no_reviews: 0, recent30: 0, prices: [] };
      item.total++;
      if (!g.error) item.active++;
      if (g.search?.seller_online) item.online++;
      if (!g.review_count) item.no_reviews++;
      const days = parseLastDeliveryDays(g.last_delivery);
      if (days !== null && days <= 30) item.recent30++;
      if (g.starting_price_usd) item.prices.push(g.starting_price_usd);
      countryMap.set(country, item);
    }

    const byCountry = Array.from(countryMap.entries())
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 15)
      .map(([country, data]) => ({
        country,
        total: data.total,
        active: data.active,
        online: data.online,
        no_reviews: data.no_reviews,
        recent_30d: data.recent30,
        median_price: medianOf(data.prices) !== null ? Math.round(medianOf(data.prices) as number) : null,
        share_pct: totalGigs > 0 ? Math.round((data.total / totalGigs) * 100) : 0,
      }));

    // 2. Keywords & Phrases (real, with per-phrase gig indexes)
    const unigramCounts = new Map<string, PhraseStat>();
    const bigramCounts = new Map<string, PhraseStat>();
    const trigramCounts = new Map<string, PhraseStat>();
    const titleStartCounts = new Map<string, PhraseStat>();
    const tagCounts = new Map<string, PhraseStat>();

    for (const [idx, g] of gigs.entries()) {
      const rank = g.search?.global_position || idx + 1;
      const isTop20 = rank <= 20;
      const price = g.starting_price_usd || 0;
      const revs = g.review_count || 0;

      const words = (g.title || "")
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, " ")
        .split(/\s+/)
        .filter((w) => w.length > 2 && !STOPWORDS.has(w));

      const bump = (map: Map<string, PhraseStat>, phrase: string) => {
        const d = map.get(phrase) || newPhraseStat();
        d.count++;
        if (isTop20) d.top20++;
        if (price) d.prices.push(price);
        d.ranks.push(rank);
        d.reviews.push(revs);
        d.gigs.add(idx);
        map.set(phrase, d);
      };

      if (words.length >= 2) {
        bump(titleStartCounts, words.slice(0, 2).join(" "));
      }

      for (let i = 0; i < words.length; i++) {
        bump(unigramCounts, words[i]);
        if (i < words.length - 1) bump(bigramCounts, `${words[i]} ${words[i + 1]}`);
        if (i < words.length - 2) bump(trigramCounts, `${words[i]} ${words[i + 1]} ${words[i + 2]}`);
      }

      for (const tag of g.related_tags || []) {
        const tClean = tag.toLowerCase().trim();
        if (tClean) bump(tagCounts, tClean);
      }
    }

    const mapKeywords = (map: Map<string, PhraseStat>) => {
      return Array.from(map.entries())
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 40)
        .map(([phrase, d]) => ({
          phrase,
          gig_count: d.count,
          share_pct: totalGigs > 0 ? Math.round((d.count / totalGigs) * 100) : 0,
          top_20_count: d.top20,
          average_rank: d.ranks.length ? Math.round((meanOf(d.ranks) ?? 0) * 10) / 10 : 0,
          median_price: d.prices.length ? Math.round(medianOf(d.prices) || 0) : 0,
          average_reviews: d.reviews.length ? Math.round((meanOf(d.reviews) ?? 0) || 0) : 0,
        }));
    };

    // 3. Keyword Clusters (real union-find + Jaccard, ported from Python)
    const clusters = buildClusters(bigramCounts, trigramCounts, gigs);

    // 4. Reviews (real sentiment over crawled reviews)
    const reviews = buildReviews(gigs);

    // 5. Packages & pricing (real package data)
    const packages = buildPackages(gigs);
    const pricing = buildPricing(gigs);

    // 6. Competitors leaderboard (real fields — keeps the source gig so the
    // competitors table below can read real has_video/package_count)
    const topGigEntries = gigs.slice(0, 50).map((g, idx) => ({
      source: g,
      row: {
        global_position: g.search?.global_position || idx + 1,
        organic_position: g.search?.organic_position || idx + 1,
        is_sponsored: g.search?.is_sponsored ? "Sponsored" : "Organic",
        title: g.title,
        seller: g.seller_name || g.seller_username || "Fiverr Seller",
        seller_level: g.seller_level || "New Seller",
        seller_country: g.seller_country || null,
        price: g.starting_price_usd ? `$${g.starting_price_usd}` : "—",
        rating: g.rating ? `★ ${g.rating}` : "—",
        review_count: g.review_count || 0,
        url: g.url,
      },
    }));
    const topGigs = topGigEntries.map((e) => e.row);

    // Competitor concentration
    const sellerConcMap = new Map<string, { username: string; count: number; ranks: number[]; sponsored: number }>();
    for (const [idx, g] of gigs.entries()) {
      const s = g.seller_name || g.seller_username || "Unknown";
      const u = g.seller_username || s;
      const rank = g.search?.global_position || idx + 1;
      const item = sellerConcMap.get(s) || { username: u, count: 0, ranks: [], sponsored: 0 };
      item.count++;
      item.ranks.push(rank);
      if (g.search?.is_sponsored) item.sponsored++;
      sellerConcMap.set(s, item);
    }

    const sellerConcentration = Array.from(sellerConcMap.entries())
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 25)
      .map(([seller, d]) => ({
        seller,
        seller_username: d.username,
        gig_count: d.count,
        best_rank: Math.min(...d.ranks),
        average_rank: round1(meanOf(d.ranks)),
        sponsored_count: d.sponsored,
      }));

    // 7. Market gaps (data-driven). Review-phrase indexes for gap analysis
    // (bigrams that appear in review text across >= 2 gigs).
    const reviewPhraseCounts = new Map<string, { count: number; gigs: Set<number> }>();
    {
      gigs.forEach((g, gi) => {
        for (const review of g.visible_reviews || []) {
          const tokens = tokenize(review.comment || "");
          for (let i = 0; i + 1 < tokens.length; i++) {
            const phrase = tokens.slice(i, i + 2).join(" ");
            const d = reviewPhraseCounts.get(phrase) || { count: 0, gigs: new Set() };
            d.count++;
            d.gigs.add(gi);
            reviewPhraseCounts.set(phrase, d);
          }
        }
      });
    }
    const marketGaps = buildMarketGaps(gigs, bigramCounts, reviewPhraseCounts, packages);

    // 8. Rank movement (real, when a previous snapshot exists)
    const rankMovement = buildRankMovement(gigs, previousSnapshot);

    // Price comparison for health buckets — REAL prices of the buckets.
    const bucketStats = (predicate: (g: GigResult) => boolean) => {
      const prices = gigs.filter(predicate).map((g) => g.starting_price_usd).filter((p): p is number => p != null);
      if (!prices.length) return { count: 0, min: null, median: null, mean: null, max: null };
      return {
        count: prices.length,
        min: Math.min(...prices),
        median: Math.round(medianOf(prices) || 0),
        mean: Math.round(meanOf(prices) || 0),
        max: Math.max(...prices),
      };
    };
    const priceComparison = {
      active: bucketStats((g) => !g.error),
      dead_no_activity: bucketStats((g) => !g.error && !(g.review_count || 0) && !g.search?.seller_online),
      online: bucketStats((g) => Boolean(g.search?.seller_online)),
      no_reviews: bucketStats((g) => !(g.review_count || 0)),
    };

    const ratingStats = calcNumericStats(gigs.map((g) => g.rating));
    const reviewStats = calcNumericStats(gigs.map((g) => g.review_count));
    const detailCoveragePct = totalGigs > 0 ? Math.round((activeSuccess / totalGigs) * 100) : 0;

    return {
      niche,
      generated_at: utcNow(),
      methodology: {
        llm_used: false,
        version: "phase2-v3",
        sample_size: totalGigs,
        source: "computed from crawled sample (no fabricated constants)",
      },
      overview: {
        sampled_gigs: totalGigs,
        available_results: reportedResults,
        available_results_is_estimate: totalAvailable <= 0,
        unique_sellers: sellerConcentration.length,
        sponsored_share_pct: totalGigs > 0 ? Math.round((gigs.filter((g) => g.search?.is_sponsored).length / totalGigs) * 100) : 0,
        starting_price: pricing.overall,
        rating: ratingStats,
        review_count: { median: reviewStats.median ?? 0, mean: reviewStats.mean ?? 0 },
        video_share_pct: totalGigs > 0 ? Math.round((gigs.filter((g) => g.has_video).length / totalGigs) * 100) : 0,
        seller_levels: byLevel.map((l) => ({ label: l.level, count: l.total, share_pct: l.share_pct })),
        seller_countries: byCountry.slice(0, 8).map((c) => ({ label: c.country, count: c.total, share_pct: c.share_pct })),
        detail_coverage_pct: detailCoveragePct,
      },
      market_health: {
        summary: {
          total_fiverr_results: reportedResults,
          sampled_gigs: totalGigs,
          active_gigs: activeSuccess,
          dead_fetch_failed: deadFetchFailed,
          online_now: onlineNow,
          offline,
          with_reviews: withReviews,
          no_reviews: noReviews,
          fully_active: fullyActive,
          no_activity_dead: noActivityDead,
          recent_7d: recent7d,
          recent_30d: recent30d,
          dormant_90d_plus: dormant90d,
          unknown_delivery: unknownDelivery,
          active_rate_pct: activeRatePct,
          online_rate_pct: onlineRatePct,
          estimated_total_active: estTotalActive,
          estimated_total_dead_no_activity: estTotalDead,
        },
        price_comparison: priceComparison,
        delivery_buckets: [
          { label: "Recent <= 7 days", count: recent7d, share_pct: totalGigs > 0 ? Math.round((recent7d / totalGigs) * 100) : 0 },
          { label: "Recent <= 30 days", count: recent30d, share_pct: totalGigs > 0 ? Math.round((recent30d / totalGigs) * 100) : 0 },
          { label: "Dormant 90+ days", count: dormant90d, share_pct: totalGigs > 0 ? Math.round((dormant90d / totalGigs) * 100) : 0 },
          { label: "Unknown / No Delivery Info", count: unknownDelivery, share_pct: totalGigs > 0 ? Math.round((unknownDelivery / totalGigs) * 100) : 0 },
        ],
        dead_reasons: [
          { reason: "No reviews + Offline + Old delivery (>60d)", count: noActivityDead, share_pct: deadSharePct },
          { reason: "Fetch Failed / Gig Paused", count: deadFetchFailed, share_pct: totalGigs > 0 ? Math.round((deadFetchFailed / totalGigs) * 100) : 0 },
        ],
        by_level: byLevel,
        by_country: byCountry,
        details: healthDetails,
      },
      rankings: {
        top_gigs: topGigs,
        seller_concentration: sellerConcentration,
      },
      rank_movement: rankMovement,
      keywords: {
        bigrams: mapKeywords(bigramCounts),
        trigrams: mapKeywords(trigramCounts),
        title_starts: mapKeywords(titleStartCounts),
        unigrams: mapKeywords(unigramCounts),
        related_tags: mapKeywords(tagCounts),
      },
      keyword_clusters: clusters,
      pricing,
      packages,
      competitors: topGigEntries.map(({ source, row }) => ({
        global_position: row.global_position,
        title: row.title,
        seller: row.seller,
        seller_level: row.seller_level,
        seller_country: row.seller_country,
        price: row.price,
        rating: row.rating,
        review_count: row.review_count,
        has_video: Boolean(source.has_video),
        package_count: source.packages?.length || 0,
        url: row.url,
      })),
      reviews,
      market_gaps: marketGaps,
    };
  }

  static exportRows(analysis: any, section: string): Record<string, any>[] {
    if (!analysis) return [];
    switch (section) {
      case "overview": {
        const o = analysis.overview || {};
        return [
          {
            niche: analysis.niche,
            generated_at: analysis.generated_at,
            sampled_gigs: o.sampled_gigs,
            available_results: o.available_results,
            available_results_is_estimate: o.available_results_is_estimate,
            unique_sellers: o.unique_sellers,
            sponsored_share_pct: o.sponsored_share_pct,
            median_price: o.starting_price?.median,
            mean_price: o.starting_price?.mean,
            average_rating: o.rating?.mean,
            median_reviews: o.review_count?.median,
            video_share_pct: o.video_share_pct,
            detail_coverage_pct: o.detail_coverage_pct,
          },
        ];
      }
      case "health":
      case "health_summary":
        return [analysis.market_health?.summary || {}];
      case "health_levels":
        return analysis.market_health?.by_level || [];
      case "health_countries":
        return analysis.market_health?.by_country || [];
      case "health_delivery":
        return analysis.market_health?.delivery_buckets || [];
      case "health_reasons":
        return analysis.market_health?.dead_reasons || [];
      case "health_details":
      case "details":
        return analysis.market_health?.details || [];
      case "rankings":
        return analysis.rankings?.top_gigs || [];
      case "sellers":
        return analysis.rankings?.seller_concentration || [];
      case "competitors":
        return analysis.competitors || [];
      case "movement":
        return analysis.rank_movement?.available
          ? analysis.rank_movement.movements || []
          : [{ available: false, reason: analysis.rank_movement?.reason || "No historical crawl available." }];
      case "keywords":
      case "bigrams":
        return analysis.keywords?.bigrams || [];
      case "trigrams":
        return analysis.keywords?.trigrams || [];
      case "unigrams":
        return analysis.keywords?.unigrams || [];
      case "title_starts":
        return analysis.keywords?.title_starts || [];
      case "related_tags":
        return analysis.keywords?.related_tags || [];
      case "clusters":
        return analysis.keyword_clusters || [];
      case "pricing":
        return [analysis.pricing?.overall || {}];
      case "pricing_histogram":
        return analysis.pricing?.histogram || [];
      case "packages":
        return analysis.packages?.feature_matrix || [];
      case "reviews": {
        const r = analysis.reviews || {};
        return [
          {
            visible_reviews_analyzed: r.visible_reviews_analyzed,
            average_visible_rating: r.average_visible_rating,
            work_sample_share_pct: r.work_sample_share_pct,
            seller_response_share_pct: r.seller_response_share_pct,
          },
          ...(r.sentiment || []),
        ];
      }
      case "gaps":
        return analysis.market_gaps?.keyword_opportunities || [];
      default:
        // Unknown section: return no rows rather than silently dumping an
        // unrelated table.
        return [];
    }
  }
}
