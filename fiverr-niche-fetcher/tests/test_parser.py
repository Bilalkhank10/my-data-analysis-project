import unittest

from fiverr_fetcher import (
    normalize_gig_url,
    parse_faqs_from_markdown,
    parse_gig_page,
    parse_packages_from_markdown,
    parse_reviews_from_markdown,
    parse_search_page,
)


class ParserTests(unittest.TestCase):
    def test_url_normalization(self):
        self.assertEqual(
            normalize_gig_url(
                "https://www.fiverr.com/crea8touch/create-google-data-studio?x=1"
            ),
            "https://www.fiverr.com/crea8touch/create-google-data-studio",
        )
        self.assertIsNone(normalize_gig_url("https://www.fiverr.com/categories/data"))
        self.assertIsNone(normalize_gig_url("https://example.com/user/gig"))

    def test_search_card_rank_and_sponsored_parsing(self):
        markdown = """
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
"""
        records, total = parse_search_page(markdown, "Looker Studio", 1)
        self.assertEqual(total, 567)
        self.assertEqual(len(records), 2)
        first, second = records
        self.assertEqual(first.global_position, 1)
        self.assertEqual(first.organic_position, 1)
        self.assertFalse(first.is_sponsored)
        self.assertTrue(first.seller_online)
        self.assertEqual(first.card_seller_name, "Alpha Seller")
        self.assertEqual(first.card_price, 50.0)
        self.assertEqual(first.card_review_count, 120)
        self.assertEqual(second.global_position, 2)
        self.assertTrue(second.is_sponsored)
        self.assertIsNone(second.organic_position)
        self.assertEqual(second.sponsored_position, 1)
        self.assertEqual(second.card_seller_level, "Level 2")

    def test_structured_packages(self):
        markdown = """
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
"""
        packages, text = parse_packages_from_markdown(markdown)
        self.assertEqual(len(packages), 3)
        self.assertEqual(packages[0]["name"], "Basic")
        self.assertEqual(packages[0]["price"], 30.0)
        self.assertEqual(packages[1]["description"], "Two pages")
        self.assertEqual(packages[2]["delivery_time"], "5 days")
        self.assertEqual(packages[2]["features"]["Dashboards"], "5")
        self.assertIn("One page", text)

    def test_faq_parsing(self):
        markdown = """
## Frequently Asked Questions
### What do you need to start?
Please send the data source and required KPIs.

### Can you blend data?
Yes, when the source structure supports it.

## Reviews
"""
        faqs, text = parse_faqs_from_markdown(markdown)
        self.assertEqual(len(faqs), 2)
        self.assertEqual(faqs[0]["question"], "What do you need to start?")
        self.assertIn("data source", faqs[0]["answer"])
        self.assertIn("Can you blend", text)

    def test_review_summary_and_entries(self):
        markdown = """
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
"""
        summary, reviews, text = parse_reviews_from_markdown(markdown)
        self.assertEqual(summary["total_reviews"], 10)
        self.assertEqual(summary["star_distribution"]["5"], 9)
        self.assertEqual(summary["reviews_with_files"], 2)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["username"], "alice")
        self.assertEqual(reviews[0]["country_code"], "US")
        self.assertEqual(reviews[0]["rating"], 5.0)
        self.assertEqual(reviews[0]["duration"], "3 days")
        self.assertIn("Excellent dashboard", reviews[0]["text"])
        self.assertIn("10 reviews", text)

    def test_structured_page_parser(self):
        html = """
        <html><head>
          <meta name="description" content="Custom Looker Studio dashboard service">
          <script type="application/ld+json">
          {
            "@context":"https://schema.org",
            "@type":"Product",
            "name":"Looker dashboard",
            "aggregateRating":{"ratingValue":"4.9","reviewCount":"169"},
            "offers":{"price":"30","priceCurrency":"USD"}
          }
          </script>
        </head><body>
          <h1>I will create a Looker Studio dashboard</h1>
          <img src="https://fiverr-res.cloudinary.com/images/demo.jpg">
        </body></html>
        """
        text = """I will create a Looker Studio dashboard
Sabir Muhammad
Level 2
Gig Summary
I create interactive reports and dashboards.
Get to know Sabir Muhammad
From Pakistan
Member since Sep 2019
Avg. response time 1 hour
Last delivery 1 week
Compare packages
Basic $30 one dashboard
Reviews
5 Stars (157)
Related tags
Data visualization
Looker Studio
Message Sabir Muhammad
"""
        record = parse_gig_page(
            "https://www.fiverr.com/crea8touch/create-google-data-studio",
            html,
            text,
            "Fallback title",
        )
        self.assertEqual(record.title, "I will create a Looker Studio dashboard")
        self.assertEqual(record.seller_username, "crea8touch")
        self.assertEqual(record.seller_name, "Sabir Muhammad")
        self.assertEqual(record.seller_level, "Level 2")
        self.assertEqual(record.seller_country, "Pakistan")
        self.assertEqual(record.rating, 4.9)
        self.assertEqual(record.review_count, 169)
        self.assertEqual(record.starting_price_usd, 30.0)
        self.assertEqual(record.currency, "USD")
        self.assertIn("interactive reports", record.about_text)
        self.assertIn("Basic $30", record.packages_text)
        self.assertIn("Looker Studio", record.related_tags)
        self.assertEqual(len(record.media_urls), 1)


if __name__ == "__main__":
    unittest.main()
