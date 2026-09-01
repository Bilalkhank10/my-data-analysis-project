import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        payload = {
            "url": "https://www.fiverr.com/samridhsrivasta/create-python-bots-scripts-automate-jobs",
            "formats": ["markdown", "html", "rawHtml"]
        }
        headers = {
            "Authorization": "Bearer fc-0de01a0c1c7247ae95d060d9f2f18109",
            "Content-Type": "application/json"
        }
        r = await client.post("https://api.firecrawl.dev/v2/scrape", json=payload, headers=headers)
        print("Status:", r.status_code)
        data = r.json()
        print(data.keys())
        if "data" in data:
            print("Keys in data:", data["data"].keys())
            html = data["data"].get("rawHtml", "")
            if "perseus-initial-props" in html:
                import json
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                script = soup.find("script", id="perseus-initial-props")
                if script:
                    try:
                        d = json.loads(script.string)
                        print(f"FOUND PERSEUS JSON WITH {len(d.keys())} keys")
                    except Exception as e:
                        print("JSON ERROR", e)
            else:
                print("perseus-initial-props NOT found in HTML")

if __name__ == "__main__":
    asyncio.run(test())
