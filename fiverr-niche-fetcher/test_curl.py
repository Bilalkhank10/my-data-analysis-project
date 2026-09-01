import asyncio
from curl_cffi.requests import AsyncSession

async def test():
    async with AsyncSession(impersonate="chrome") as s:
        r = await s.get("https://www.fiverr.com/python2020/be-java-python-cpp-c-data-scraping-extraction-bot-programming-project-developer")
        text = r.text.lower()
        if "human touch" in text or "just a moment" in text or "denied" in text:
            print(f"Status: {r.status_code}")
            print("Blocked by CAPTCHA.")
        else:
            print("Success!")
            print(r.text[:500])

if __name__ == "__main__":
    asyncio.run(test())
