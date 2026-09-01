import httpx
import asyncio

async def test_direct():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient() as client:
        r = await client.get("https://www.fiverr.com/python2020/be-java-python-cpp-c-data-scraping-extraction-bot-programming-project-developer", headers=headers)
        print("Status:", r.status_code)
        text = r.text.lower()
        if "human touch" in text or "just a moment" in text or "denied" in text:
            print("Blocked by CAPTCHA.")
        else:
            print("Success!")
            print(r.text[:500])

if __name__ == "__main__":
    asyncio.run(test_direct())
