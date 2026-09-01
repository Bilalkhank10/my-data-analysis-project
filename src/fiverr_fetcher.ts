/**
 * Fiverr public-market fetcher (TypeScript port of fiverr-mcp/fiverr_fetcher.py).
 *
 * Two-stage pipeline over the public Jina Reader proxy (r.jina.ai), which
 * converts Fiverr pages to clean Markdown and sidesteps datacenter anti-bot
 * blocks without any account/auth:
 *   1. discoverSearch  — paginate Fiverr search, parse ranked gig *cards*
 *      (title, seller, level, rating, reviews, price, sponsored/organic rank).
 *   2. fetchGig        — fetch each gig detail page and parse packages, FAQs,
 *      reviews, seller info, tags and media out of the Markdown.
 *
 * No authentication, CAPTCHA or private data is accessed.
 */

import { GigResult, GigPackage, GigFAQ, GigReview, GigSearchRecord } from "./types.js";
import { utcNow } from "./storage.js";

const FIVERR_BASE = "https://www.fiverr.com";

const EXCLUDED_FIRST_PATHS = new Set([
  "about_us", "agencies", "business", "categories", "community", "content",
  "events", "gigs", "login", "logout", "pe", "pro", "resources", "search",
  "start_selling", "support", "users",
]);

const GIG_URL_PATTERN =
  /https?:\/\/(?:www\.)?fiverr\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_-]+(?:\?[^)\s\]]*)?/gi;
const CLOUDINARY_PATTERN =
  /https?:\/\/(?:fiverr-res|fiverr-dev-res)\.cloudinary\.com\/[^\s\])>"']+/gi;

const BADGE_PATTERN = /\b(Vetted Pro|Top Rated|Level\s*[12]|Fiverr's Choice|Pro)\b/gi;

export interface SearchResultRecord {
  url: string;
  niche: string;
  page_number: number;
  page_position: number;
  global_position: number;
  organic_position: number | null;
  sponsored_position: number | null;
  is_sponsored: boolean;
  seller_online: boolean;
  card_title?: string;
  card_seller_name?: string;
  card_seller_username?: string;
  card_seller_level?: string;
  card_rating?: number;
  card_review_count?: number;
  card_price?: number;
  currency?: string;
  thumbnail_url?: string;
  badges: string[];
}

export interface DiscoveryOutcome {
  records: SearchResultRecord[];
  source: string;
  pages_scanned: number;
  available_results: number | null;
  warnings: string[];
}

export interface FetcherSettings {
  maxConcurrency: number;
  delaySeconds: number;
  maxSearchPages: number;
  searchPageDelaySeconds: number;
  retryCount: number;
  retryBaseDelaySeconds: number;
  readerTimeoutSeconds: number;
  allowReaderFallback: boolean;
}

function envInt(name: string, def: number, min: number, max: number): number {
  const raw = process.env[name];
  const n = raw === undefined ? NaN : Number(raw);
  if (!Number.isFinite(n)) return def;
  return Math.min(max, Math.max(min, n));
}

function envFloat(name: string, def: number, min: number, max: number): number {
  const raw = process.env[name];
  const n = raw === undefined ? NaN : Number(raw);
  if (!Number.isFinite(n)) return def;
  return Math.min(max, Math.max(min, n));
}

function defaultSettings(): FetcherSettings {
  const allow = (process.env.ALLOW_READER_FALLBACK || "true").trim().toLowerCase();
  return {
    maxConcurrency: envInt("MAX_CONCURRENCY", 2, 1, 5),
    delaySeconds: envFloat("REQUEST_DELAY_SECONDS", 2.0, 0, 30),
    maxSearchPages: envInt("MAX_SEARCH_PAGES", 5, 1, 30),
    searchPageDelaySeconds: envFloat("SEARCH_PAGE_DELAY_SECONDS", 0.75, 0, 10),
    retryCount: envInt("RETRY_COUNT", 3, 0, 5),
    retryBaseDelaySeconds: envFloat("RETRY_BASE_DELAY_SECONDS", 1.0, 0.1, 30),
    readerTimeoutSeconds: envFloat("READER_TIMEOUT_SECONDS", 60, 15, 180),
    allowReaderFallback: !["0", "false", "no", "off"].includes(allow),
  };
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function unescapeHtml(s: string): string {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function unique(items: Iterable<string>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of items) {
    const item = (raw || "").trim();
    if (item && !seen.has(item)) {
      seen.add(item);
      out.push(item);
    }
  }
  return out;
}

function toInt(value: any): number | null {
  if (value === null || value === undefined) return null;
  const m = String(value).replace(/,/g, "").match(/\d[\d,]*/);
  return m ? parseInt(m[0].replace(/,/g, ""), 10) : null;
}

function toFloat(value: any): number | null {
  if (value === null || value === undefined) return null;
  const m = String(value).replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
  return m ? parseFloat(m[0]) : null;
}

function cleanInline(value: string): string {
  let v = value;
  v = v.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  v = v.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  v = v.replace(/\*\*/g, "").replace(/__/g, "").replace(/`/g, "");
  v = v.replace(/<[^>]+>/g, "");
  return v.replace(/\s+/g, " ").trim();
}

function markdownToText(markdown: string): string {
  let text = markdown.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  text = text.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  text = text.replace(/\*\*/g, "").replace(/__/g, "").replace(/`/g, "");
  const cleaned: string[] = [];
  for (const line of text.split("\n")) {
    let l = line.replace(/^\s{0,4}#{1,6}\s*/, "");
    l = l.replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+)/, "");
    l = l.replace(/[ \t]+/g, " ").trim();
    cleaned.push(l);
  }
  text = cleaned.join("\n").replace(/\n{3,}/g, "\n\n");
  const marker = text.indexOf("Markdown Content:");
  if (marker >= 0 && marker < 1000) {
    text = text.slice(marker + "Markdown Content:".length).replace(/^\s+/, "");
  }
  return text.trim();
}

/** Return the markdown under a heading (## style) up to the next same/higher heading. */
function markdownHeadingSection(markdown: string, headingPattern: RegExp): string | null {
  // Always apply global + case-insensitive + multiline; heading markers rely on
  // ^/$ anchoring to line starts/ends.
  const re = new RegExp(headingPattern.source, "gim");
  const m = re.exec(markdown);
  if (!m) return null;
  const rest = markdown.slice(m.index + m[0].length);
  const next = /^#{1,2}\s+/m.exec(rest);
  return rest.slice(0, next ? next.index : rest.length).trim();
}

/** Find a labelled free-text section in plain text. */
function section(
  text: string,
  starts: string[],
  ends: string[],
  maxChars = 60000
): string | null {
  const lower = text.toLowerCase();
  const candidates: { pos: number; marker: string }[] = [];
  for (const marker of starts) {
    const pos = lower.indexOf(marker.toLowerCase());
    if (pos >= 0) candidates.push({ pos, marker });
  }
  if (!candidates.length) return null;
  candidates.sort((a, b) => a.pos - b.pos);
  const { pos, marker } = candidates[0];
  const contentStart = pos + marker.length;
  const endings: number[] = [];
  for (const end of ends) {
    const idx = lower.indexOf(end.toLowerCase(), contentStart);
    if (idx >= 0) endings.push(idx);
  }
  const contentEnd = endings.length ? Math.min(...endings) : text.length;
  const value = text.slice(contentStart, contentEnd).trim();
  return value ? value.slice(0, maxChars) : null;
}

function regexGroup(pattern: RegExp, text: string): string | null {
  const flags = pattern.flags.includes("g") ? pattern.flags.replace("g", "") : pattern.flags;
  const re = new RegExp(pattern.source, flags);
  const m = re.exec(text);
  return m ? m[1].trim() : null;
}

export function readerUrl(target: string): string {
  let t = target.trim();
  if (!/^https?:\/\//i.test(t)) t = "https://" + t;
  return `https://r.jina.ai/${t}`;
}

/** Normalize a Fiverr gig URL to canonical https://www.fiverr.com/<user>/<slug>, or null. */
export function normalizeGigUrl(href: string | null | undefined): string | null {
  if (!href) return null;
  let h = unescapeHtml(href.trim());
  // DuckDuckGo redirect unwrap
  try {
    const u = new URL(h, FIVERR_BASE);
    if (u.hostname.includes("duckduckgo.com")) {
      const uddg = u.searchParams.get("uddg");
      if (uddg) h = decodeURIComponent(uddg);
    }
  } catch {
    return null;
  }

  let absolute: URL;
  try {
    absolute = new URL(h, FIVERR_BASE);
  } catch {
    return null;
  }
  const host = absolute.hostname.toLowerCase().split(":")[0];
  if (host !== "fiverr.com" && host !== "www.fiverr.com") return null;
  const parts = absolute.pathname.split("/").filter(Boolean).map((p) => decodeURIComponent(p));
  if (parts.length !== 2) return null;
  const [first, second] = parts;
  if (EXCLUDED_FIRST_PATHS.has(first.toLowerCase())) return null;
  if (!/^[A-Za-z0-9_.-]+$/.test(first)) return null;
  if (!/^[A-Za-z0-9_-]+$/.test(second)) return null;
  if (["portfolio", "reviews", "about"].includes(second.toLowerCase())) return null;
  return `${FIVERR_BASE}/${first}/${second}`;
}

// ---------------------------------------------------------------------------
// Search page parsing
// ---------------------------------------------------------------------------

export function parseSearchPage(
  markdown: string,
  niche: string,
  pageNumber: number,
  seen: Set<string>,
  globalStart: number,
  organicStart: number,
  sponsoredStart: number
): { records: SearchResultRecord[]; availableResults: number | null } {
  const localSeen = new Set<string>();
  const firstMatches: { pos: number; rawUrl: string; canonical: string }[] = [];
  const urlRe = new RegExp(GIG_URL_PATTERN.source, "gi");
  let m: RegExpExecArray | null;
  while ((m = urlRe.exec(markdown)) !== null) {
    const rawUrl = unescapeHtml(m[0]);
    const canonical = normalizeGigUrl(rawUrl);
    if (!canonical || localSeen.has(canonical) || seen.has(canonical)) continue;
    localSeen.add(canonical);
    firstMatches.push({ pos: m.index, rawUrl, canonical });
  }

  const totalMatch = /\b([\d,]+)\s+results?\b/i.exec(markdown);
  const availableResults = totalMatch ? toInt(totalMatch[1]) : null;

  const records: SearchResultRecord[] = [];
  let organicPosition = organicStart;
  let sponsoredPosition = sponsoredStart;

  firstMatches.forEach((entry, index) => {
    const nextPos = index + 1 < firstMatches.length ? firstMatches[index + 1].pos : markdown.length;
    // Mirror Python markdown.rfind("\n[![", pos-2500, pos): search only within
    // the window immediately preceding this gig link for its card-image marker.
    const windowStart = Math.max(0, entry.pos - 2500);
    let marker = markdown.lastIndexOf("\n[![", entry.pos);
    if (marker < windowStart) marker = -1;
    let cardStart: number;
    if (marker >= 0 && entry.pos - marker <= 2500) {
      cardStart = marker;
    } else {
      cardStart = Math.max(0, entry.pos - 800);
    }
    const seg = markdown.slice(cardStart, nextPos);

    let query: URLSearchParams;
    try {
      query = new URL(entry.rawUrl, FIVERR_BASE).searchParams;
    } catch {
      query = new URLSearchParams();
    }
    const pagePosition = toInt(query.get("pos")) || index + 1;
    const username = entry.canonical.split("/")[3];

    // Title: a markdown link to this gig whose label starts with "I will" etc.
    let title: string | null = null;
    const linkRe = /\[([^\]\n]{3,350})\]\((https?:\/\/[^)\s]+)\)/gi;
    let lm: RegExpExecArray | null;
    while ((lm = linkRe.exec(seg)) !== null) {
      const label = cleanInline(lm[1]);
      const target = normalizeGigUrl(lm[2]);
      if (target === entry.canonical && /^(i will|our agency will|we will)/i.test(label)) {
        title = label;
        break;
      }
    }
    if (!title) {
      const imgAlt = /Image\s+\d+\s*:\s*([^\]]+)/i.exec(seg);
      title = imgAlt ? cleanInline(imgAlt[1]) : null;
    }

    let sellerName: string | null = null;
    const profileRe = new RegExp(
      `\\[([^\\]\\n]{2,120})\\]\\(https?://(?:www\\.)?fiverr\\.com/${username.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:\\?[^)]*)?\\)`,
      "i"
    );
    const pm = profileRe.exec(seg);
    if (pm) sellerName = cleanInline(pm[1]);

    const badges = unique(
      Array.from(seg.matchAll(BADGE_PATTERN)).map((x) => x[1])
    );
    const level =
      badges.find((b) => /^(level|top rated|vetted pro)/i.test(b)) || null;

    const ratingMatch = /\*\*([1-5](?:\.\d)?)\*\*\s*\(([\d,]+)/.exec(seg);
    const priceMatch = /(?:from|starting at)\s*\$\s*([\d,.]+)/i.exec(seg);
    const sponsored = /^\s*(?:ad|promoted)\s*$/im.test(seg);

    let currentOrganic: number | null = null;
    let currentSponsored: number | null = null;
    if (sponsored) {
      sponsoredPosition += 1;
      currentSponsored = sponsoredPosition;
    } else {
      organicPosition += 1;
      currentOrganic = organicPosition;
    }

    const cloudinary = unique(
      Array.from(seg.matchAll(CLOUDINARY_PATTERN)).map((x) => unescapeHtml(x[0]))
    );
    const thumbnail =
      cloudinary.find((v) => v.includes("t_gig_cards") || v.includes("/gigs/") || v.includes("/gigs2/")) ||
      cloudinary[0] ||
      null;

    const onlineParam = (query.get("seller_online") || "").toLowerCase() === "true";
    const onlineLine = /^\s*online\s*$/im.test(seg);

    records.push({
      url: entry.canonical,
      niche,
      page_number: pageNumber,
      page_position: pagePosition,
      global_position: globalStart + records.length + 1,
      organic_position: currentOrganic,
      sponsored_position: currentSponsored,
      is_sponsored: sponsored,
      seller_online: onlineParam || onlineLine,
      card_title: title || undefined,
      card_seller_name: sellerName || undefined,
      card_seller_username: username,
      card_seller_level: level || undefined,
      card_rating: ratingMatch ? toFloat(ratingMatch[1])! : undefined,
      card_review_count: ratingMatch ? toInt(ratingMatch[2])! : undefined,
      card_price: priceMatch ? toFloat(priceMatch[1])! : undefined,
      currency: priceMatch ? "USD" : undefined,
      thumbnail_url: thumbnail || undefined,
      badges,
    });
    seen.add(entry.canonical);
  });

  return { records, availableResults };
}

// ---------------------------------------------------------------------------
// Package / FAQ / review parsing from gig-page markdown
// ---------------------------------------------------------------------------

interface RawPackage {
  name: string;
  price: number | null;
  currency: string | null;
  description: string | null;
  delivery_time: string | null;
  revisions: string | null;
  features: Record<string, boolean | string>;
}

export function parsePackagesFromMarkdown(markdown: string): { packages: RawPackage[]; packagesText: string | null } {
  const sectionMd = markdownHeadingSection(markdown, /^##\s+Compare packages\s*$/);
  const packages: RawPackage[] = [];

  if (sectionMd) {
    const tableLines = sectionMd
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("|"));
    const rows: string[][] = [];
    for (const line of tableLines) {
      const cells = line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => cleanInline(c));
      if (cells.every((c) => /^[-: ]*$/.test(c || "-"))) continue;
      rows.push(cells);
    }
    if (rows.length && rows[0].length >= 2) {
      const headers = rows[0];
      const packageCount = headers.length - 1;
      for (let col = 1; col <= packageCount; col++) {
        const rawHeader = headers[col] || `Package ${col}`;
        const nameMatch = /(Basic|Standard|Premium)/i.exec(rawHeader);
        const name = nameMatch
          ? nameMatch[1][0].toUpperCase() + nameMatch[1].slice(1).toLowerCase()
          : rawHeader.replace(/\$[\d,.]+/g, "").trim();
        const pkg: RawPackage = {
          name: name || `Package ${col}`,
          price: toFloat(rawHeader),
          currency: rawHeader.includes("$") ? "USD" : null,
          description: null,
          delivery_time: null,
          revisions: null,
          features: {},
        };
        for (const row of rows.slice(1)) {
          if (!row.length) continue;
          const label = (row[0] || "").trim();
          const value = col < row.length ? row[col].trim() : "";
          if (!label && value && !pkg.description) {
            pkg.description = value;
            continue;
          }
          if (!label) continue;
          const lowered = label.toLowerCase();
          if (lowered === "total" && pkg.price === null) {
            pkg.price = toFloat(value);
          } else if (lowered.includes("delivery")) {
            pkg.delivery_time = value || null;
          } else if (lowered.includes("revision")) {
            pkg.revisions = value || null;
          } else if (lowered !== "package") {
            pkg.features[label] = value || true;
          }
        }
        packages.push(pkg);
      }
    }
  }

  if (!packages.length) {
    // Fiverr often renders only the selected package above the page body.
    const sel = /^###\s+\*\*(Basic|Standard|Premium)\*\*\s*([\s\S]*?)(?=^###\s+|^#\s+I will|\nContinue\s*$)/im.exec(
      markdown
    );
    if (sel) {
      const name = sel[1][0].toUpperCase() + sel[1].slice(1).toLowerCase();
      const block = sel[2];
      const priceMatch = /\$\s*([\d,.]+)/.exec(block);
      const deliveryMatch = /\*\*([^*]*delivery)\*\*/i.exec(block);
      const revisionMatch = /\*\*([^*]*revision[^*]*)\*\*/i.exec(block);
      const features = unique(
        Array.from(block.matchAll(/^\*\s+(.+)$/gm)).map((x) => cleanInline(x[1]))
      );
      const plainLines = block
        .split("\n")
        .map((l) => cleanInline(l))
        .filter(
          (l) =>
            l &&
            !l.includes("$") &&
            !/service fees/i.test(l) &&
            !/delivery/i.test(l) &&
            !/revision/i.test(l) &&
            !/^\*/.test(l.trim())
        );
      packages.push({
        name,
        price: priceMatch ? toFloat(priceMatch[1]) : null,
        currency: priceMatch ? "USD" : null,
        description: plainLines[0] || null,
        delivery_time: deliveryMatch ? cleanInline(deliveryMatch[1]) : null,
        revisions: revisionMatch ? cleanInline(revisionMatch[1]) : null,
        features: Object.fromEntries(features.map((f) => [f, true])),
      });
    }
  }

  return { packages, packagesText: sectionMd ? markdownToText(sectionMd) : null };
}

export function parseFaqsFromMarkdown(markdown: string): { faqs: GigFAQ[]; faqText: string | null } {
  const sec = markdownHeadingSection(markdown, /^#{1,3}\s+(?:FAQs?|Frequently Asked Questions?)\s*$/);
  if (!sec) return { faqs: [], faqText: null };
  const faqs: GigFAQ[] = [];

  // Strategy 1: ### sub-heading per question.
  const headings = Array.from(sec.matchAll(/^###\s+(.+?)\s*$/gm));
  headings.forEach((h, i) => {
    const question = cleanInline(h[1]);
    const end = i + 1 < headings.length ? headings[i + 1].index! - h.index! : sec.length;
    const answer = markdownToText(sec.slice(h.index! + h[0].length, end)).trim();
    if (question && answer) faqs.push({ question, answer });
  });

  // Strategy 2: **Bold question** / paragraph answer.
  if (!faqs.length) {
    const bolds = Array.from(sec.matchAll(/^\*\*(.+?)\*\*\s*$/gm));
    bolds.forEach((b, i) => {
      const end = i + 1 < bolds.length ? bolds[i + 1].index! - b.index! : sec.length;
      const answer = markdownToText(sec.slice(b.index! + b[0].length, end)).trim();
      if (answer) faqs.push({ question: cleanInline(b[1]), answer });
    });
  }

  // Strategy 3: paragraph Q/A pairs.
  if (!faqs.length) {
    const paragraphs = sec.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
    for (let i = 0; i < paragraphs.length - 1; i++) {
      const q = markdownToText(paragraphs[i]).trim();
      const a = markdownToText(paragraphs[i + 1]).trim();
      const looksLikeQuestion =
        q.length <= 200 &&
        !/^[-*#]/.test(q) &&
        (q.endsWith("?") || /^(what|how|why|when|can|do|does|is|are|will|should|who)/i.test(q));
      if (looksLikeQuestion && a && !a.endsWith("?")) {
        faqs.push({ question: q, answer: a });
        i++;
      }
    }
  }

  return { faqs, faqText: markdownToText(sec) };
}

function reviewMarkdownSection(markdown: string): string | null {
  let m = /^##\s+[\d,]+\s+reviews?\s+for\s+this\s+gig\s*$/im.exec(markdown);
  if (!m) m = /^Reviews\s*$/im.exec(markdown);
  if (!m) return null;
  const tail = markdown.slice(m.index);
  const endings: number[] = [];
  const related = /^##\s+Related tags\s*$/im.exec(tail);
  if (related) endings.push(related.index);
  const dup = /^Reviews\s*\n\s*##\s+[\d,]+\s+reviews?\s+for\s+this\s+gig/im.exec(tail.slice(200));
  if (dup) endings.push(200 + dup.index);
  const end = endings.length ? Math.min(...endings) : tail.length;
  return tail.slice(0, end).trim();
}

export function parseReviewsFromMarkdown(markdown: string): {
  summary: Record<string, any>;
  reviews: GigReview[];
  reviewsText: string | null;
} {
  const sec = reviewMarkdownSection(markdown);
  if (!sec) return { summary: {}, reviews: [], reviewsText: null };

  const totalMatch = /##\s+([\d,]+)\s+reviews?/i.exec(sec);
  const overallMatch = /\n\*\*([1-5](?:\.\d)?)\*\*\s*\n/.exec(sec);
  const stars: Record<string, number> = {};
  for (const m of sec.matchAll(/([1-5])\s+Stars?\s*\(([\d,]+)\)/gi)) {
    stars[m[1]] = toInt(m[2]) || 0;
  }
  const filesMatch = /Only show reviews with files\s*\(([\d,]+)\)/i.exec(sec);
  const summary: Record<string, any> = {
    total_reviews: totalMatch ? toInt(totalMatch[1]) : null,
    overall_rating: overallMatch ? toFloat(overallMatch[1]) : null,
    star_distribution: stars,
    reviews_with_files: filesMatch ? toInt(filesMatch[1]) : null,
  };

  const reviews: GigReview[] = [];
  const chunks = sec.split(/^\*\s{2,}/m);
  const seenKeys = new Set<string>();
  for (const chunk of chunks) {
    const flag = /!\[Image\s+\d+\s*:\s*([A-Z]{2})\]\(https?:\/\/fiverr-dev-res\.cloudinary\.com\/general_assets\/flags\/[^)]+\)/.exec(
      chunk
    );
    const dateMatch = /\b(\d+\s+(?:day|week|month|year)s?\s+ago)\b/i.exec(chunk);
    const ratingMatch = /\*\*([1-5](?:\.\d)?)\*\*/.exec(chunk);
    if (!flag || !dateMatch || !ratingMatch) continue;

    const beforeFlag = chunk.slice(0, flag.index).replace(/!\[[^\]]*\]\([^)]*\)/g, " ");
    const tokens = beforeFlag.match(/[A-Za-z][A-Za-z0-9_.-]+/g);
    const username = tokens ? tokens[tokens.length - 1] : "unknown";
    const afterFlag = chunk.slice(flag.index + flag[0].length);
    const countryMatch = /^\s*\n?\s*([^\n*]{2,80})/.exec(afterFlag);
    const country = countryMatch ? cleanInline(countryMatch[1]) : null;

    const rest = chunk.slice(dateMatch.index + dateMatch[0].length);
    const priceMatch = /\$[\d,]+(?:\s*-\s*\$[\d,]+)?/.exec(rest);
    const reviewEndCandidates: number[] = [];
    for (const pat of [/Seller's Response/i, /Helpful\?/i, /Price\s+/i]) {
      const mm = pat.exec(rest);
      if (mm) reviewEndCandidates.push(mm.index);
    }
    if (priceMatch) reviewEndCandidates.push(priceMatch.index);
    const reviewEnd = reviewEndCandidates.length ? Math.min(...reviewEndCandidates) : rest.length;
    const reviewText = markdownToText(rest.slice(0, reviewEnd)).replace(/^[\s-]+|[\s-]+$/g, "").trim();
    const responseMatch = /Seller's Response\s+([\s\S]*?)\s+Helpful\?/i.exec(rest);
    const sampleMatch = /(https?:\/\/fiverr-res\.cloudinary\.com\/[^\s)]*t_delivery_large[^\s)]*)/i.exec(rest);

    const key = `${username}|${dateMatch[1].toLowerCase()}|${reviewText.slice(0, 100)}`;
    if (seenKeys.has(key)) continue;
    seenKeys.add(key);

    reviews.push({
      buyer_name: username,
      buyer_country: country || undefined,
      rating: toFloat(ratingMatch[1]) || undefined,
      created_at: dateMatch[1],
      comment: reviewText || undefined,
      work_sample: !!sampleMatch,
      seller_response: responseMatch ? markdownToText(responseMatch[1]).trim() : undefined,
    });
    if (reviews.length >= 50) break;
  }

  summary.visible_reviews_parsed = reviews.length;
  return { summary, reviews, reviewsText: markdownToText(sec) };
}

function parseCategoryPath(markdown: string): string[] {
  const h1 = /^#\s+I will\b/im.exec(markdown);
  const prefix = h1 ? markdown.slice(0, h1.index) : markdown.slice(0, 10000);
  const labels = Array.from(
    prefix.matchAll(/\[([^\]]+)\]\(https?:\/\/(?:www\.)?fiverr\.com\/categories\/[^)]+\)/gi)
  ).map((x) => cleanInline(x[1]));
  return unique(labels).slice(-5);
}

function readerTitle(markdown: string, url: string): string {
  const heading = /^#\s+(.+?)\s*$/m.exec(markdown);
  if (heading) return cleanInline(heading[1]);
  const meta = /^Title:\s*(.+?)\s*$/m.exec(markdown);
  if (meta) {
    let v = meta[1].trim();
    v = v.replace(/^[^:]{1,80}:\s+(?=I will\b)/i, "");
    v = v.replace(/\s+for\s+\$[\d,.]+\s+on\s+fiverr\.com\s*$/i, "");
    return v.trim();
  }
  const slug = new URL(url, FIVERR_BASE).pathname.replace(/\/$/, "").split("/").pop() || "";
  return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Gig detail page -> GigResult
// ---------------------------------------------------------------------------

function deliveryDays(text: string | null): number | undefined {
  if (!text) return undefined;
  const m = text.match(/(\d+)/);
  return m ? parseInt(m[1], 10) : undefined;
}

function mapPackages(raw: RawPackage[]): GigPackage[] {
  return raw.map((p) => ({
    name: p.name,
    price_usd: p.price ?? 0,
    description: p.description || "",
    delivery_days: deliveryDays(p.delivery_time) ?? 0,
    revisions: p.revisions ?? "",
    deliverables: Object.keys(p.features).filter((k) => p.features[k]),
    features: p.features,
  }));
}

export function parseGigMarkdown(url: string, markdown: string): GigResult {
  const visible = markdownToText(markdown);
  const pathParts = new URL(url, FIVERR_BASE).pathname.split("/").filter(Boolean);
  const username = pathParts[0] || undefined;

  let title = readerTitle(markdown, url);
  title = title.replace(/\s+by\s+[^|]+\|\s*Fiverr\s*$/i, "").trim();

  let rating: number | undefined;
  let reviewCount: number | undefined;
  const ratingMatch = /\b([1-5](?:\.\d)?)\s*\(([\d,]+)(?:\s*reviews?)?\)/i.exec(visible.slice(0, 9000));
  if (ratingMatch) {
    rating = toFloat(ratingMatch[1]) || undefined;
    reviewCount = toInt(ratingMatch[2]) || undefined;
  }

  const { packages, packagesText } = parsePackagesFromMarkdown(markdown);
  const packagePrices = packages.map((p) => p.price).filter((p): p is number => p !== null);
  let startingPrice: number | null = packagePrices.length ? Math.min(...packagePrices) : null;
  let currency: string | undefined = packagePrices.length ? "USD" : undefined;
  if (startingPrice === null) {
    const pm = /(?:from|starting at)\s*\$\s*([\d,.]+)/i.exec(visible.slice(0, 15000));
    startingPrice = pm ? toFloat(pm[1]) : null;
    if (startingPrice !== null) currency = "USD";
  }

  const sellerName = regexGroup(/Get to know\s+([^\n\r]+)/, visible) || undefined;
  const sellerLevel =
    regexGroup(/\b(Level\s*[12]|Top Rated|Vetted Pro|New Seller)\b/, visible.slice(0, 12000)) || undefined;
  const sellerCountry = regexGroup(/(?:^|\n)From\s*(?:\n\s*)?([^\n\r]+)/, visible) || undefined;
  const memberSince = regexGroup(/Member since\s*(?:\n\s*)?([^\n\r]+)/, visible) || undefined;
  const responseTime = regexGroup(/Avg\.? response time\s*:?\s*(?:\n\s*)?([^\n\r]+)/, visible) || undefined;
  const lastDelivery = regexGroup(/Last delivery\s*(?:\n\s*)?([^\n\r]+)/, visible) || undefined;

  const about =
    section(visible, ["About this gig", "Gig Summary"], ["Get to know", "Compare packages", "About the seller"]) ||
    undefined;
  const { faqs, faqText } = parseFaqsFromMarkdown(markdown);
  const { summary: reviewSummary, reviews, reviewsText } = parseReviewsFromMarkdown(markdown);

  if (!reviewCount && reviewSummary.total_reviews) reviewCount = reviewSummary.total_reviews;
  if (!rating && reviewSummary.overall_rating) rating = reviewSummary.overall_rating;

  const tagsText =
    section(visible, ["Related tags"], ["Message the seller", "Message ", "About Fiverr"], 4000) || "";
  const relatedTags = unique(
    tagsText
      .split("\n")
      .map((l) => l.replace(/^[•\-\s]+/, "").trim())
      .filter((l) => l.length > 1 && l.length < 80)
  ).slice(0, 30);

  const mediaUrls = unique(
    Array.from(markdown.matchAll(CLOUDINARY_PATTERN)).map((x) => unescapeHtml(x[0]))
  ).slice(0, 150);
  const galleryCount = mediaUrls.filter(
    (u) => u.includes("/gigs/") || u.includes("/gigs2/") || u.includes("t_delivery") || u.includes("attachments/delivery")
  ).length;
  const hourlyMatch = /\*\*\$\s*([\d,.]+)\*\*\s*\/hour/i.exec(markdown);
  const hasVideo = markdown.includes("video/upload") || /\[Video\s+\d+/i.test(markdown);
  const categoryPath = parseCategoryPath(markdown);

  return {
    url,
    fetched_at: utcNow(),
    title,
    seller_username: username,
    seller_name: sellerName,
    seller_level: sellerLevel,
    seller_country: sellerCountry,
    member_since: memberSince,
    average_response_time: responseTime,
    last_delivery: lastDelivery,
    rating,
    review_count: reviewCount,
    starting_price_usd: startingPrice ?? undefined,
    hourly_rate_usd: hourlyMatch ? toFloat(hourlyMatch[1]) || undefined : undefined,
    currency,
    meta_description: undefined,
    category_path: categoryPath,
    about_text: about,
    packages: mapPackages(packages),
    packages_text: packagesText || undefined,
    faqs,
    faq_text: faqText || undefined,
    review_summary: reviewSummary && Object.keys(reviewSummary).length ? JSON.stringify(reviewSummary) : undefined,
    visible_reviews: reviews,
    reviews_text: reviewsText || undefined,
    related_tags: relatedTags,
    media_urls: mediaUrls,
    gallery_count: galleryCount,
    has_video: hasVideo,
    json_ld: [],
    raw_visible_text: visible,
  } as GigResult;
}

// ---------------------------------------------------------------------------
// HTTP fetcher over Jina Reader
// ---------------------------------------------------------------------------

export class FiverrReaderFetcher {
  settings: FetcherSettings;

  constructor(settings?: Partial<FetcherSettings>) {
    this.settings = { ...defaultSettings(), ...(settings || {}) };
    if (!this.settings.allowReaderFallback) {
      throw new Error("Reader mode is disabled (ALLOW_READER_FALLBACK=false).");
    }
  }

  /** Optional reader cache (attached by the server; avoids re-hitting Jina). */
  readerCache: { get(url: string, ttlMs: number): string | null; set(url: string, markdown: string): void } | null =
    null;
  readerCacheTtlMs = Math.max(60, Number(process.env.CRAWL_CACHE_TTL_SECONDS) || 6 * 60 * 60) * 1000;

  private readerHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: "text/markdown",
      "User-Agent": "Mozilla/5.0 (compatible; GigCraft/1.0)",
      "X-Return-Format": "markdown",
    };
    // A (free) Jina API key raises the rate limit from ~20 RPM to ~500 RPM.
    const jinaKey = process.env.JINA_API_KEY;
    if (jinaKey && jinaKey.trim()) headers["Authorization"] = `Bearer ${jinaKey.trim()}`;
    return headers;
  }

  private async getText(url: string): Promise<string> {
    // Cache hit: serve the previously fetched markdown within the TTL.
    if (this.readerCache) {
      const cached = this.readerCache.get(url, this.readerCacheTtlMs);
      if (cached) return cached;
    }
    let lastError: any = null;
    const attempts = this.settings.retryCount + 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
      try {
        const res = await fetch(url, {
          headers: this.readerHeaders() as any,
          signal: AbortSignal.timeout(this.settings.readerTimeoutSeconds * 1000),
          redirect: "follow",
        });
        if ([429, 500, 502, 503, 504].includes(res.status)) {
          throw new Error(`Retryable status ${res.status}`);
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const text = await res.text();
        if (text.trim().length < 200) throw new Error("Reader returned an empty or unusable response.");
        if (this.readerCache) {
          try {
            this.readerCache.set(url, text);
          } catch {
            // cache failures never break the crawl
          }
        }
        return text;
      } catch (err: any) {
        lastError = err;
        const retryable = /retryable status|http (429|50[0-9])|network|fetch|timeout|abort|tls|eof|reset/i.test(
          String(err?.message || err)
        );
        if (attempt >= attempts - 1 || !retryable) break;
        const wait = Math.min(this.settings.retryBaseDelaySeconds * Math.pow(2, attempt), 30);
        await new Promise((r) => setTimeout(r, wait * 1000));
      }
    }
    throw new Error(`Reader request failed after retries: ${lastError?.message || lastError}`);
  }

  async discoverSearch(niche: string, limit: number): Promise<DiscoveryOutcome> {
    const q = niche.trim().replace(/\s+/g, " ");
    const cap = Math.min(500, Math.max(1, Math.round(limit)));
    const collected: SearchResultRecord[] = [];
    const seen = new Set<string>();
    let pagesWithoutNew = 0;
    let pagesScanned = 0;
    let availableResults: number | null = null;
    let organicCount = 0;
    let sponsoredCount = 0;
    const warnings: string[] = [];

    for (let page = 1; page <= this.settings.maxSearchPages; page++) {
      const source =
        `https://www.fiverr.com/search/gigs?query=${encodeURIComponent(q)}` +
        `&source=top-bar&search_in=everywhere&page=${page}`;
      let markdown: string;
      try {
        markdown = await this.getText(readerUrl(source));
      } catch (err: any) {
        if (collected.length) {
          warnings.push(`Search page ${page} stopped pagination: ${err?.message}`);
          break;
        }
        throw err;
      }
      pagesScanned = page;
      const { records, availableResults: pageTotal } = parseSearchPage(
        markdown,
        q,
        page,
        seen,
        collected.length,
        organicCount,
        sponsoredCount
      );
      if (pageTotal !== null) availableResults = pageTotal;
      if (records.length) {
        pagesWithoutNew = 0;
        for (const rec of records) {
          if (rec.is_sponsored) sponsoredCount = Math.max(sponsoredCount, rec.sponsored_position || 0);
          else organicCount = Math.max(organicCount, rec.organic_position || 0);
          collected.push(rec);
          if (collected.length >= cap) break;
        }
      } else {
        pagesWithoutNew += 1;
      }
      if (collected.length >= cap || pagesWithoutNew >= 2) break;
      await new Promise((r) => setTimeout(r, this.settings.searchPageDelaySeconds * 1000));
    }

    return {
      records: collected.slice(0, cap),
      source: "reader-search",
      pages_scanned: pagesScanned,
      available_results: availableResults,
      warnings,
    };
  }

  private async fetchGig(url: string): Promise<GigResult> {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return { url, fetched_at: utcNow(), error: "Invalid URL" } as GigResult;
    }
    const source = `https://${parsed.hostname}${parsed.pathname}`;
    try {
      const markdown = (await this.getText(readerUrl(source))).trim();
      return parseGigMarkdown(url, markdown);
    } catch (err: any) {
      const pathParts = parsed.pathname.split("/").filter(Boolean);
      return {
        url,
        fetched_at: utcNow(),
        seller_username: pathParts[0] || undefined,
        error: `${err?.name || "Error"}: ${err?.message || err}`,
      } as GigResult;
    }
  }

  async crawl(
    niche: string,
    limit: number,
    opts: { onProgress?: (p: Record<string, any>) => void; isCancelled?: () => boolean } = {}
  ): Promise<{
    results: GigResult[];
    discoverySource: string;
    pagesScanned: number;
    availableResults: number | null;
    discoveredCount: number;
    processedCount: number;
    successCount: number;
    failedCount: number;
    warnings: string[];
  }> {
    const q = niche.trim().replace(/\s+/g, " ");
    const discovery = await this.discoverSearch(q, limit);
    const records = discovery.records;
    const discovered = records.length;

    opts.onProgress?.({
      stage: "fetching",
      pages_scanned: discovery.pages_scanned,
      available_results: discovery.available_results,
      discovered_count: discovered,
      processed_count: 0,
      progress_percent: 15,
    });

    if (!discovered) {
      return {
        results: [],
        discoverySource: discovery.source,
        pagesScanned: discovery.pages_scanned,
        availableResults: discovery.available_results,
        discoveredCount: 0,
        processedCount: 0,
        successCount: 0,
        failedCount: 0,
        warnings: discovery.warnings,
      };
    }

    let processed = 0;
    let successes = 0;
    let failures = 0;
    const results: GigResult[] = new Array(discovered).fill(null as any);
    let cursor = 0;

    const worker = async () => {
      while (cursor < discovered) {
        if (opts.isCancelled?.()) return;
        const index = cursor++;
        const rec = records[index];
        let gig = await this.fetchGig(rec.url);

        // Merge search-card metadata as fallback for missing detail fields.
        gig.title = gig.title || rec.card_title || "";
        gig.seller_name = gig.seller_name || rec.card_seller_name;
        gig.seller_username = gig.seller_username || rec.card_seller_username;
        gig.seller_level = gig.seller_level || rec.card_seller_level;
        gig.rating = gig.rating ?? rec.card_rating;
        gig.review_count = gig.review_count ?? rec.card_review_count;
        gig.starting_price_usd = gig.starting_price_usd ?? rec.card_price;
        const search: GigSearchRecord = {
          niche: q,
          global_position: rec.global_position,
          organic_position: rec.organic_position ?? undefined,
          sponsored_position: rec.sponsored_position ?? undefined,
          page_number: rec.page_number,
          page_position: rec.page_position,
          is_sponsored: rec.is_sponsored,
          card_title: rec.card_title,
          card_price: rec.card_price != null ? `$${rec.card_price}` : undefined,
          badges: rec.badges,
          seller_online: rec.seller_online,
        };
        gig.search = search;
        if (gig.error) failures += 1;
        else successes += 1;
        processed += 1;
        results[index] = gig;

        opts.onProgress?.({
          stage: "fetching",
          pages_scanned: discovery.pages_scanned,
          available_results: discovery.available_results,
          discovered_count: discovered,
          processed_count: processed,
          success_count: successes,
          failed_count: failures,
          progress_percent: Math.min(99.5, 15 + (85 * processed) / discovered),
        });
        await new Promise((r) => setTimeout(r, this.settings.delaySeconds * 1000));
      }
    };

    const workerCount = Math.min(this.settings.maxConcurrency, discovered);
    await Promise.all(Array.from({ length: workerCount }, () => worker()));

    return {
      results: results.filter(Boolean).sort((a, b) => {
        const pa = a.search?.global_position ?? 999999;
        const pb = b.search?.global_position ?? 999999;
        return pa - pb;
      }),
      discoverySource: "reader-search",
      pagesScanned: discovery.pages_scanned,
      availableResults: discovery.available_results,
      discoveredCount: discovered,
      processedCount: processed,
      successCount: successes,
      failedCount: failures,
      warnings: discovery.warnings,
    };
  }
}

export const readerFetcher = new FiverrReaderFetcher();
