import { test } from "node:test";
import assert from "node:assert/strict";
import {
  normalizeGigUrl,
  parseSearchPage,
  parsePackagesFromMarkdown,
  parseFaqsFromMarkdown,
  parseReviewsFromMarkdown,
  parseGigMarkdown,
} from "../src/fiverr_fetcher.js";

test("normalizeGigUrl accepts gig links and rejects non-gig paths", () => {
  assert.equal(
    normalizeGigUrl("http://www.fiverr.com/crea8touch/create-google-data-studio?x=1"),
    "https://www.fiverr.com/crea8touch/create-google-data-studio"
  );
  assert.equal(normalizeGigUrl("https://example.com/foo/bar"), null);
  assert.equal(normalizeGigUrl("https://www.fiverr.com/login"), null);
  assert.equal(normalizeGigUrl("https://www.fiverr.com/seller/portfolio"), null);
});

test("search page: rank, sponsored/organic, seller, price, reviews, online", () => {
  const markdown = `
567 results

[![Image 1: create a looker studio dashboard](https://fiverr-res.cloudinary.com/t_gig_cards_web/gigs/1.jpg)](http://www.fiverr.com/alpha/create-looker-dashboard?context_referrer=search_gigs&pos=1&seller_online=true)

[Alpha Seller](http://www.fiverr.com/alpha?source=gig_cards)
Top Rated
[I will create a looker studio dashboard](http://www.fiverr.com/alpha/create-looker-dashboard?context_referrer=search_gigs&pos=1)
**5.0**(120)
[From$50](http://www.fiverr.com/alpha/create-looker-dashboard?context_referrer=search_gigs&pos=1)

[![Image 2: fix data studio reports](https://fiverr-res.cloudinary.com/t_gig_cards_web/gigs/2.jpg)](http://www.fiverr.com/beta/fix-data-studio?context_referrer=search_gigs&pos=2)

[Beta Seller](http://www.fiverr.com/beta?source=gig_cards)
Ad
Level 2
[I will fix data studio reports](http://www.fiverr.com/beta/fix-data-studio?context_referrer=search_gigs&pos=2)
**4.9**(42)
[From$25](http://www.fiverr.com/beta/fix-data-studio?context_referrer=search_gigs&pos=2)
`;
  const { records, availableResults } = parseSearchPage(markdown, "Looker Studio", 1, new Set(), 0, 0, 0);
  assert.equal(availableResults, 567);
  assert.equal(records.length, 2);
  const [first, second] = records;
  assert.equal(first.global_position, 1);
  assert.equal(first.organic_position, 1);
  assert.equal(first.is_sponsored, false);
  assert.equal(first.seller_online, true);
  assert.equal(first.card_seller_name, "Alpha Seller");
  assert.equal(first.card_price, 50);
  assert.equal(first.card_review_count, 120);
  assert.equal(second.global_position, 2);
  assert.equal(second.is_sponsored, true);
  assert.equal(second.organic_position, null);
  assert.equal(second.sponsored_position, 1);
  assert.equal(second.card_seller_level, "Level 2");
});

test("packages: compare-packages table parses 3 tiers with price/features/delivery", () => {
  const markdown = `
## Compare packages
Prices are before service fees.

| Package | $30 **Basic** | $80 **Standard** | $200 **Premium** |
| --- | --- | --- | --- |
|  | One page | Two pages | Five pages |
| Dashboards | 1 | 2 | 5 |
| Revisions | Unlimited | 3 | 5 |
| Delivery Time | 2 days | 3 days | 5 days |
| Total | $30 Select | $80 Select | $200 Select |

## Reviews
`;
  const { packages, packagesText } = parsePackagesFromMarkdown(markdown);
  assert.equal(packages.length, 3);
  assert.equal(packages[0].name, "Basic");
  assert.equal(packages[0].price, 30);
  assert.equal(packages[1].description, "Two pages");
  assert.equal(packages[2].delivery_time, "5 days");
  assert.equal((packages[2].features as any)["Dashboards"], "5");
  assert.ok(packagesText && packagesText.includes("One page"));
});

test("faqs parse ### sub-headings with answers", () => {
  const markdown = `
## Frequently Asked Questions
### What do you need to start?
Please send the data source and required KPIs.

### Can you blend data?
Yes, when the source structure supports it.

## Reviews
`;
  const { faqs, faqText } = parseFaqsFromMarkdown(markdown);
  assert.equal(faqs.length, 2);
  assert.equal(faqs[0].question, "What do you need to start?");
  assert.ok(faqs[0].answer.includes("data source"));
  assert.ok(faqText && faqText.includes("Can you blend"));
});

test("reviews: summary counts, star distribution and visible entry", () => {
  const markdown = `
## 10 reviews for this Gig

**4.9**
5 Stars(9)
4 Stars(1)
3 Stars(0)
2 Stars(0)
1 Star(0)

*   Seller communication level **4.9**
*   Quality of delivery **5.0**

- [x] Only show reviews with files (2)

*   A alice ![Image 1: US](https://fiverr-dev-res.cloudinary.com/general_assets/flags/us.png)
United States **5**
1 month ago Excellent dashboard and communication. $50-$100

Price 3 days Duration
Seller's Response Thank you Helpful? Yes No

## Related tags
`;
  const { summary, reviews, reviewsText } = parseReviewsFromMarkdown(markdown);
  assert.equal(summary.total_reviews, 10);
  assert.equal(summary.star_distribution["5"], 9);
  assert.equal(summary.reviews_with_files, 2);
  assert.equal(reviews.length, 1);
  assert.equal(reviews[0].buyer_name, "alice");
  assert.equal(reviews[0].buyer_country, "United States");
  assert.equal(reviews[0].rating, 5);
  assert.ok(reviews[0].comment && reviews[0].comment.includes("Excellent dashboard"));
  assert.ok(reviewsText && reviewsText.includes("4.9"));
});

test("full gig markdown populates the detail-page GigResult fields", () => {
  const markdown = `Title: I will build a Looker Studio dashboard for $50 on fiverr.com

[Data Visualization](https://www.fiverr.com/categories/data/data-visualization)

# I will build a Looker Studio dashboard

Get to know Sabir Muhammad
From Pakistan
Member since Sep 2019
Avg. response time 1 hour
Last delivery 1 week
Level 2

Gig Summary
I create interactive reports and executive dashboards with automated refresh.

## Compare packages
| Package | $50 **Basic** | $120 **Standard** | $250 **Premium** |
| --- | --- | --- | --- |
|  | One dashboard | Three dashboards | Full suite |
| Delivery Time | 2 days | 4 days | 7 days |
| Revisions | 2 | 4 | Unlimited |

## Frequently Asked Questions
### Do you offer revisions?
Yes, all tiers include revisions.

## 215 reviews for this Gig
**4.9**
5 Stars(200)

## Related tags
looker studio
dashboard
data visualization

Message Sabir Muhammad
`;
  const gig = parseGigMarkdown("https://www.fiverr.com/crea8touch/create-looker-dashboard", markdown);
  assert.ok(gig.title && gig.title.startsWith("I will build a Looker Studio dashboard"));
  assert.equal(gig.seller_username, "crea8touch");
  assert.equal(gig.seller_name, "Sabir Muhammad");
  assert.equal(gig.seller_country, "Pakistan");
  assert.equal(gig.seller_level, "Level 2");
  assert.equal(gig.member_since, "Sep 2019");
  assert.equal(gig.average_response_time, "1 hour");
  assert.equal(gig.last_delivery, "1 week");
  assert.equal(gig.rating, 4.9);
  assert.equal(gig.review_count, 215);
  assert.equal(gig.starting_price_usd, 50);
  assert.ok(gig.about_text && gig.about_text.includes("interactive reports"));
  assert.equal(gig.packages?.length, 3);
  assert.equal(gig.faqs?.length, 1);
  assert.ok(gig.related_tags && gig.related_tags.includes("looker studio"));
  assert.ok(gig.category_path && gig.category_path.length >= 1);
});
