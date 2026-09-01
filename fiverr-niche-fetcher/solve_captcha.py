import asyncio
from playwright.async_api import async_playwright

async def get_clearance():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        print("Opening Fiverr. Please solve the CAPTCHA if it appears in the browser window...")
        await page.goto("https://www.fiverr.com/python2020/be-java-python-cpp-c-data-scraping-extraction-bot-programming-project-developer")
        
        while True:
            text = await page.content()
            text = text.lower()
            if "human touch" in text or "just a moment" in text or "denied" in text:
                print("Waiting for you to solve the CAPTCHA...")
                await asyncio.sleep(5)
            else:
                print("CAPTCHA solved or not present!")
                break
                
        cookies = await context.cookies()
        import json
        with open("fiverr_cookies.json", "w") as f:
            json.dump(cookies, f)
        print("Saved cookies to fiverr_cookies.json!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_clearance())
