import asyncio
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth

async def test_pw():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        response = await page.goto("https://www.fiverr.com/python2020/be-java-python-cpp-c-data-scraping-extraction-bot-programming-project-developer")
        await page.wait_for_timeout(3000)
        content = await page.content()
        print("Status:", response.status)
        text = content.lower()
        if "human touch" in text or "just a moment" in text or "denied" in text:
            print("Blocked by CAPTCHA.")
        else:
            print("Success!")
            print(content[:500])
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_pw())
