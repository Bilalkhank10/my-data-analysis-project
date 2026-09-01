import asyncio
from dotenv import load_dotenv
load_dotenv()
from fiverr_fetcher import FiverrNicheFetcher, FetcherSettings

async def main():
    settings = FetcherSettings(allow_reader_fallback=True)
    fetcher = FiverrNicheFetcher(settings)
    print("Starting crawl...")
    result = await fetcher.crawl("python script", limit=2)
    
    print(f"Discovered: {result['discovered_count']}")
    print(f"Processed: {result['processed_count']}")
    print(f"Success: {result['success_count']}")
    
    for i, gig in enumerate(result['results']):
        print(f"\n--- Gig {i+1} ---")
        for k, v in gig.items():
            if k in ['about_text', 'packages_text', 'faq_text', 'reviews_text', 'raw_visible_text', 'raw_card_text']:
                print(f"{k}: <text of length {len(str(v)) if v else 0}>")
            elif k == 'raw_state':
                num_keys = len(v.keys()) if v else 0
                print(f"{k}: <dict with {num_keys} top-level keys>")
                if v:
                    # Print the top-level keys
                    print(f"   -> Top level keys: {list(v.keys())[:10]} ...")
                    # Check if 'gig' or something similar exists to verify real data
                    if 'gig' in v:
                        print(f"   -> gig.id: {v['gig'].get('gig_id')}")
                    if 'seller' in v:
                        print(f"   -> seller.id: {v['seller'].get('seller_id')}")
            elif isinstance(v, list) and len(v) > 3:
                print(f"{k}: <list of {len(v)} items>")
            else:
                print(f"{k}: {v}")

if __name__ == "__main__":
    asyncio.run(main())
