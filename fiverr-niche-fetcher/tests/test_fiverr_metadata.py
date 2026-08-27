import unittest

from fiverr_metadata import TAG_MAX_CHARS, listing_quality, title_own_text
from gig_builder import validate_generated_gig
from test_phase4 import valid_generation


class FiverrMetadataTests(unittest.TestCase):
    def test_title_own_text_strips_prefix(self):
        self.assertEqual(
            title_own_text("I will build a Looker Studio dashboard"),
            "build a Looker Studio dashboard",
        )

    def test_listing_quality_scores_complete_gig(self):
        score = listing_quality(
            {
                "title": "I will build a Looker Studio marketing dashboard",
                "about_text": "x" * 320,
                "related_tags": ["looker studio", "ga4", "dashboard"],
                "packages": [{}, {}, {}],
                "faqs": [{}] * 5,
                "has_video": True,
                "gallery_count": 4,
                "rating": 5,
            }
        )
        self.assertGreaterEqual(score["score"], 75)

    def test_validator_uses_2026_field_limits(self):
        result = valid_generation()
        ok = validate_generated_gig(result)
        self.assertTrue(ok["passed"])
        self.assertEqual(ok["field_limits"]["tag_max_chars"], TAG_MAX_CHARS)
        result["recommended_gig"]["tags"][0] = "this-tag-is-way-too-long-for-fiverr"
        bad = validate_generated_gig(result)
        self.assertFalse(bad["passed"])
        self.assertTrue(any("20" in note for note in bad["issues"]))


if __name__ == "__main__":
    unittest.main()
