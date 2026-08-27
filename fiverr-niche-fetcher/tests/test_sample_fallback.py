import asyncio
import unittest

import httpx

from fiverr_fetcher import FetcherSettings, FiverrNicheFetcher


class SampleFallbackTests(unittest.TestCase):
    def test_tls_failure_loads_bundled_market(self):
        settings = FetcherSettings(allow_sample_fallback=True, retry_count=0)
        fetcher = FiverrNicheFetcher(settings)

        async def boom(*_args, **_kwargs):
            raise httpx.ConnectError("TLS/SSL connection has been closed (EOF) (_ssl.c:992)")

        fetcher._get_text = boom  # type: ignore[method-assign]

        async def run():
            return await fetcher.crawl("Looker Studio", 5)

        payload = asyncio.run(run())
        self.assertEqual(payload["discovery_source"], "sample-fallback")
        self.assertEqual(payload["success_count"], 5)
        self.assertEqual(len(payload["results"]), 5)
        self.assertTrue(payload["warnings"])
        self.assertIn("sample", payload["results"][0]["fetch_method"])


if __name__ == "__main__":
    unittest.main()
