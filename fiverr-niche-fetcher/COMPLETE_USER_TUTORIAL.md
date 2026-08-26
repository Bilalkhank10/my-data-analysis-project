# Fiverr Gig Growth System — Complete User Tutorial

## Roman Urdu Step-by-Step Manual

> Normal user ko ab phases manually run nahi karne. Root page ka **Create My Fiverr Gig** button backend mein complete workflow automatically chalata hai. Neeche ke Phase 1–4 sections Advanced dashboard samajhne ke liye hain.

---

# Simple mode — recommended

1. `START_HERE.bat` run karein.
2. Service/niche likhein.
3. Quick, Recommended, ya Best Quality choose karein.
4. **Create My Fiverr Gig** click karein.
5. `Research → Buyer needs → Build gig → Ready` ka wait karein.
6. Copy buttons se content Fiverr mein paste karein.

Advanced dashboard optional hai:

```text
http://127.0.0.1:8000/advanced
```

---

# 1. System asal mein karta kya hai?

System Fiverr ke public marketplace ko research karke chaar layers mein kaam karta hai:

```text
Phase 1 — Public Fiverr data crawl
       ↓
Phase 2 — Deterministic market intelligence
       ↓
Phase 3 — Optional AI semantic audit
       ↓
Phase 4 — Evidence-led gig draft builder
```

System Fiverr account mein login nahi karta, live gig edit nahi karta aur kuch automatically publish nahi karta.

---

# 2. System start karna

Windows par extracted project folder mein double-click karein:

```text
START_HERE.bat
```

Ye automatically:

- Python check/install offer
- virtual environment
- requirements
- `.env`
- diagnostics
- available port
- server
- browser

handle karta hai.

Terminal window open rehni chahiye. Terminal band hone par local app stop ho jayegi.

Default address:

```text
http://127.0.0.1:8000
```

Agar 8000 busy ho to launcher 8001, 8002 etc. use kar sakta hai. Hamesha terminal mein printed URL dekhein.

---

# 3. Premium UI navigation

Top navigation mein paanch workspaces hain:

```text
01 Crawl
02 Intelligence
03 AI Audit
04 Gig Builder
05 Raw Data
```

Shuru mein sirf Crawl enabled hoga. Crawl complete hone ke baad baqi workspaces unlock hongi.

Ek waqt mein sirf selected workspace visible hota hai, is liye interface clean rehta hai.

---

# 4. Phase 1 — Crawl

## Niche field

Yahan Fiverr search keyword likhein:

```text
Looker Studio
WordPress Development
Amazon PPC
Shopify SEO
Power BI Dashboard
```

Broad keyword ke muqable mein commercially specific keyword zyada useful analysis deta hai.

## Maximum gigs

Options:

```text
3
5
10
25
50
100
250
500
```

Pehli baar 3–5 gigs use karein. Jab system verify ho jaye, 25–100 use karein. 500-gig crawl kaafi time le sakta hai.

## Start Background Job

Button click karne par:

1. Fiverr search pages discover hongi
2. Gig URLs deduplicate hongi
3. Har gig ka public detail page fetch hoga
4. Structured data SQLite mein incrementally save hoga
5. Phase 2 analysis automatically generate hogi

## Progress metrics

### Pages

Kitne Fiverr result pages scan huay.

### Discovered

Kitne unique gigs mile.

### Processed

Kitne detail pages process huay.

### Success

Kitne pages successfully parse huay.

### Failed

Kitne pages network/format problem ki wajah se fail huay.

Agar kuch pages fail hon aur majority successful ho to analytics phir bhi ban sakti hai.

## Cancel Job

Large crawl rokna ho to Cancel click karein. Processed data aur partial exports preserve reh sakte hain.

---

# 5. Crawl mein kya collect hota hai?

## Search position

- Global observed rank
- Organic rank
- Sponsored rank
- Page number
- Page position
- Organic/Sponsored label
- Online status

## Gig fields

- URL
- Title
- Seller name/username
- Seller level
- Country
- Member since
- Response time
- Last delivery
- Rating
- Review count
- Starting price
- Hourly rate
- Category path
- About section

## Structured content

- Basic/Standard/Premium packages
- Package prices
- Delivery
- Revisions
- Features
- FAQs
- Related tags
- Gallery/media links
- Video status

## Reviews

Publicly visible reviews se:

- Buyer country
- Rating
- Relative date
- Review text
- Price range
- Duration
- Ongoing collaboration
- Work sample
- Seller response

Private reviews ya Fiverr dashboard data available nahi hota.

---

# 6. Phase 2 — Intelligence

Crawl complete hone ke baad Intelligence workspace automatically open ho sakta hai.

Phase 2 mein koi LLM/API token use nahi hota.

## Overview

Dikhata hai:

- Sampled gigs
- Fiverr available-result count
- Unique sellers
- Organic/Sponsored share
- Median price
- Average rating
- Median reviews
- Video share
- Seller-level distribution
- Seller-country distribution

## Rankings

- Observed Top gigs
- Organic position
- Sponsored position
- Multi-gig sellers
- Seller concentration
- Price/rating/reviews comparison

Rank ek public-session observation hai, universal Fiverr rank nahi.

## Movement

Same niche ko baad mein dobara crawl karne par:

- Previous rank
- Current rank
- Rank gain/loss
- Price change
- Review-count change
- New gigs
- Removed gigs

Pehli crawl par Movement available nahi hogi; minimum do same-niche snapshots chahiye.

## Keywords

Titles/tags se:

- Single terms
- Two-word phrases
- Three-word phrases
- Title-start phrases
- Top-20 usage
- Gig count/share
- Average rank
- Median price
- Average reviews

## Clusters

Similar repeated phrases deterministic token-overlap se groups mein organize hote hain. Is tab mein LLM use nahi hota.

## Pricing

- Minimum
- Q1
- Median
- Mean
- Q3
- P90
- Maximum
- Price histogram
- Seller-level pricing
- Rank-band pricing
- Package-tier pricing
- Outliers

## Packages

- Basic/Standard/Premium coverage
- Delivery patterns
- Revision patterns
- Feature matrix
- Feature coverage percentage

## Competitors

Filter karein:

- Title/seller
- Seller level
- Organic/Sponsored
- Price
- Rating
- Reviews
- Video
- Packages

## Reviews

Rule-based analysis:

- Visible-review count
- Positive/Neutral/Negative split
- Praise terms
- Concern terms
- Repeated buyer phrases
- Buyer countries
- Price ranges
- Durations
- Ongoing-client share
- Work-sample share
- Seller-response share

## Market Gaps

Diagnostic public-data proxies:

- Keyword opportunities
- Review-language gaps
- Offer-feature gaps

Opportunity score Fiverr ka official search volume ya algorithm score nahi hai.

## CSV download

Har Intelligence tab ke top par current-tab CSV download available hai.

---

# 7. Phase 3 — AI Audit

AI Audit optional hai. OpenRouter key ke baghair Dry Run chalega.

## Modes

### Dry Run — $0

- No API call
- No tokens
- No cost
- Selected gigs/model/batches/cost estimate

Hamesha pehle Dry Run use karein.

### Tiny Live Test

- One gig
- One-gig batches
- Limited structured output
- Real key connection verify karne ke liye

### Standard Audit

- Selected gigs individually audit hoti hain
- Embeddings generate hote hain
- Gemini structured analysis deta hai
- Final market synthesis hoti hai

### Deep Audit

- Gemini individual audits
- Embeddings
- Claude final strategic synthesis

Deep mode Standard se mehnga ho sakta hai.

## Max Gigs

LLM ko all 500 raw gigs nahi jati. Representative gigs select hoti hain.

Testing ke liye:

```text
1 gig
```

Normal audit:

```text
5 gigs
```

Deeper market sample:

```text
10–25 gigs
```

## Your Gig URL

Optional field mein current crawl ke andar maujood apni public gig URL paste karein. Agar URL current crawl dataset mein nahi hai to own-gig comparison include nahi ho sakta.

## AI Overview

- Market summary
- Audited gigs
- Cost
- Cache hits
- Dominant intents
- High-ticket opportunities

## Intent Map

Har selected gig se:

- Service
- Buyer problem
- Desired outcome
- Target buyer
- Industry
- Tools
- Positioning

## Scores

Diagnostic scores:

- Neo readiness
- Intent clarity
- Conversion readiness
- Trust/proof
- Package consistency
- Semantic differentiation
- High-ticket readiness
- Compliance risk

Ye Fiverr internal scores nahi hain.

## Similarity

Embeddings se:

- Similar gig pairs
- Nearest competitors
- Own-gig nearest competitors

## Market Synthesis

- Positioning archetypes
- Semantic gaps
- High-ticket opportunities
- Own-gig strengths/gaps/actions
- Caveats

## Evidence

Har AI interpretation ke saath source section, quote, reason aur confidence.

## Usage & Cost

- Prompt tokens
- Completion tokens
- Total tokens
- Actual cost
- API calls
- Cache hits
- Cost cap

---

# 8. Phase 3 data privacy

Dry Run mein OpenRouter ko kuch nahi jata.

Real mode mein selected compact public data jata hai:

- title
- rank/price/rating
- seller level/country
- limited about excerpt
- packages
- limited FAQs
- maximum three short public review samples
- Phase 2 aggregate statistics

Nahi jata:

- Fiverr password
- login cookies
- private messages
- private reviews
- personal computer files
- complete 500-page database
- API key as prompt text

API key sirf HTTPS Authorization header mein OpenRouter ko jati hai.

---

# 9. Phase 3 invalid JSON issue

Latest release mein:

- OpenRouter response-healing plugin
- Markdown JSON extraction
- Mixed-text JSON extraction
- Content-array parsing
- Double-encoded JSON parsing
- Trailing-comma repair
- One gig per batch
- Larger output-token allowance

included hain.

Apni `.env` mein ensure karein:

```env
OPENROUTER_GIGS_PER_BATCH=1
OPENROUTER_MAX_OUTPUT_TOKENS=4000
```

Agar old run failed ho, new run create karein; failed history delete karna zaroori nahi.

Agar error ho `No endpoints found that can handle requested parameters`, latest release automatic chain use karti hai:

```text
Strict schema → JSON mode → plain JSON parser → primary-model fallback
```

`.env` mein ye enabled rakhein:

```env
OPENROUTER_ALLOW_PARAMETER_FALLBACK=true
```

---

# 10. Phase 4 — Gig Builder

Gig Builder market research ko final draft assets mein convert karta hai. Generated output automatically publish nahi hota.

## Mode

### Dry Run

Zero-token plan aur cost estimate.

### Tiny Live Draft

One constrained Gemini generation request.

### Standard Draft

Complete structured Gemini draft plus deterministic compliance validation.

### Deep Refine

Gemini draft → validator → Claude refinement → final validator.

## Existing Gig URL

Agar current gig optimize karni hai to current crawl ke andar maujood URL paste karein.

Agar new gig banani hai to field blank rehne dein.

## Target Buyer

Example:

```text
Ecommerce marketing teams
Local service businesses
SaaS founders
Digital marketing agencies
```

## Positioning Goal

Example:

```text
Premium GA4 and Looker Studio reporting specialist
Fast WordPress conversion optimization expert
Amazon PPC profitability consultant
```

## Tone

- Professional
- Consultative
- Technical
- Friendly
- Premium

## Pricing

- Budget entry
- Market aligned
- Premium

Pricing market percentiles se informed hoti hai, lekin publish se pehle manually verify karein.

---

# 11. Phase 4 output tabs

## Final Gig

- Strategy summary
- Three positioning options
- Recommended title
- Five tags
- Category/subcategory/service type
- Description
- CTA

## Packages

Basic/Standard/Premium:

- Price
- Description
- Delivery
- Revisions
- Ideal buyer
- Deliverables
- Features

Premium ko sirf more quantity nahi, stronger outcome path dena chahiye.

## FAQ & Requirements

- FAQs
- Buyer requirements
- Scope exclusions

## Visuals & Video

- Thumbnail headline
- Thumbnail subheadline
- Three gallery briefs
- Video hook/problem/solution/proof/CTA

## Compliance

Deterministic checks:

- Title length
- Description length
- Exactly five unique tags
- Three package order
- Ascending prices
- FAQ depth
- Off-platform contact/payment text
- Unverifiable guarantees
- Keyword stuffing
- Thumbnail readability

## Evidence

Keywords, buyer needs, pricing basis, market gaps aur differentiation reason.

## Before/After

Existing gig provided ho to:

- Current/proposed title
- Price
- Description length
- Package count
- FAQ count

## Usage

Tokens, cost, cache, model information.

---

# 12. Draft approve aur download

Generated result pehle `draft` hota hai.

Manual review ke baad:

```text
Approve Draft
```

click kar sakte hain.

Approval sirf local status hai; Fiverr par publish nahi karta.

Markdown file download karne ke liye:

```text
Download Markdown
```

Use karein. Markdown mein title, tags, description, packages, FAQs, requirements, visuals aur compliance report hoti hai.

---

# 13. Raw Data

Raw Data workspace mein every processed gig ka detailed record milta hai.

Har section ka separate Copy button hai:

- Search position
- Gig overview
- Seller
- Description
- Packages
- FAQs
- Reviews
- Tags
- Media URLs
- Raw visible text

Pagination 20 records at a time show karti hai.

---

# 14. Recommended full workflow example

## Niche: Looker Studio

### Day 1

```text
Crawl: 10 gigs
```

Overview, pricing, packages, reviews aur gaps inspect karein.

### Phase 3

```text
Dry Run → Max 1
Tiny Live Test → Max 1
Standard Audit → Max 5
```

### Phase 4

```text
Dry Run
Tiny Live Draft
Standard Draft
```

Target buyer:

```text
Ecommerce marketing teams
```

Positioning:

```text
GA4 and Looker Studio revenue reporting specialist
```

### Later

Same niche ko dobara crawl karke Movement tab mein rank changes compare karein.

---

# 15. OpenRouter cost control

`.env` example:

```env
OPENROUTER_MAX_COST_USD=0.10
OPENROUTER_GIGS_PER_BATCH=1
OPENROUTER_MAX_OUTPUT_TOKENS=4000
```

OpenRouter key par bhi low hard spending limit set karein. Application cap ke saath provider-level cap final safety layer hai.

Same request cache se milne par duplicate model cost avoid ho sakti hai.

---

# 16. Local data and backup

Database:

```text
data\fiverr_phase1.db
```

Exports:

```text
data\exports\
```

Backup:

1. Server stop karein
2. Complete `data` folder copy karein
3. `.env` ko separately secure location mein backup karein
4. `.env` kisi ko share na karein

---

# 17. System stop aur restart

Stop:

```text
Ctrl+C
```

Next time:

```text
START_HERE.bat
```

Browser automatically open hoga.

---

# 18. Common problems

## OpenRouter not configured

New rotated key local `.env` mein set karke app restart karein.

## Invalid JSON

Latest fixed project use karein aur `.env` mein:

```env
OPENROUTER_GIGS_PER_BATCH=1
OPENROUTER_MAX_OUTPUT_TOKENS=4000
```

## Port busy

Launcher automatically next port try karega. Terminal ka URL use karein.

## Crawl fail

```bat
.venv\Scripts\python.exe doctor.py --online
```

Run karein. Firewall aur internet check karein.

## Module missing

`START_HERE.bat` dobara run karein.

## Large crawl slow

Expected hai. 500 detail pages low concurrency aur delays ke saath fetch hoti hain. Pehle small sample use karein.

---

# 19. Golden rules

1. Small crawl se start karein
2. Har AI operation se pehle Dry Run
3. First real request Tiny mode
4. API key chat mein share na karein
5. Cost cap low rakhein
6. AI scores ko Fiverr official metrics na samjhein
7. Generated content manually review karein
8. Fiverr policies check karein
9. Competitor text verbatim copy na karein
10. Data folder ka backup rakhein

---

# 20. Quick cheat sheet

```text
START_HERE.bat
    ↓
Crawl 5–10 gigs
    ↓
Intelligence review
    ↓
AI Audit Dry Run
    ↓
Tiny Live Test
    ↓
Standard Audit 5 gigs
    ↓
Gig Builder Dry Run
    ↓
Tiny/Standard Draft
    ↓
Compliance review
    ↓
Download Markdown
    ↓
Human edits and approval
```
