import tempfile
import unittest
from pathlib import Path

from storage import Storage


class StorageTests(unittest.TestCase):
    def test_job_search_and_snapshot_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory) / "test.db")
            job = storage.create_job("job-1", "Looker Studio", 500)
            self.assertEqual(job["status"], "queued")
            storage.update_job(
                "job-1",
                status="running",
                stage="fetching",
                discovered_count=1,
                progress_percent=50,
            )
            storage.save_search_results(
                "job-1",
                [
                    {
                        "url": "https://www.fiverr.com/alpha/create-dashboard",
                        "niche": "Looker Studio",
                        "page_number": 1,
                        "page_position": 1,
                        "global_position": 1,
                        "organic_position": 1,
                        "sponsored_position": None,
                        "is_sponsored": False,
                        "seller_online": True,
                        "card_title": "I will create a dashboard",
                        "card_seller_username": "alpha",
                        "badges": ["Level 2"],
                    }
                ],
            )
            result = {
                "url": "https://www.fiverr.com/alpha/create-dashboard",
                "fetched_at": "2026-08-21T00:00:00+00:00",
                "fetch_method": "reader",
                "title": "I will create a dashboard",
                "seller_username": "alpha",
                "seller_name": "Alpha",
                "seller_level": "Level 2",
                "rating": 5.0,
                "review_count": 10,
                "starting_price_usd": 50.0,
                "error": None,
                "search": {"global_position": 1},
            }
            storage.save_gig_result("job-1", result)
            rows, total = storage.get_job_results("job-1", 0, 20)
            self.assertEqual(total, 1)
            self.assertEqual(rows[0]["title"], "I will create a dashboard")
            self.assertEqual(storage.count_search_results("job-1"), 1)
            cards = storage.get_all_search_results("job-1")
            self.assertEqual(cards[0]["global_position"], 1)
            self.assertEqual(cards[0]["badges"], ["Level 2"])
            self.assertTrue(cards[0]["seller_online"])
            loaded = storage.get_job("job-1")
            self.assertEqual(loaded["stage"], "fetching")
            self.assertEqual(loaded["discovered_count"], 1)

    def test_recovery_marks_running_job_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory) / "test.db")
            storage.create_job("job-2", "WordPress", 5)
            storage.update_job("job-2", status="running", stage="fetching")
            changed = storage.recover_incomplete_jobs()
            self.assertEqual(changed, 1)
            self.assertEqual(storage.get_job("job-2")["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
