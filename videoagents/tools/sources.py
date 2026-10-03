"""Save actual source HTML/text and optionally browser screenshots."""

import asyncio
from html.parser import HTMLParser
from pathlib import Path

from videoagents.providers.network import safe_get, validate_url
from videoagents.storage.repository import now
from videoagents.tools.media import sha256


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def fetch_source(url: str, path: Path) -> dict:
    content, content_type, final_url = safe_get(url, max_bytes=3 * 1024 * 1024)
    if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
        raise ValueError("首版来源读取只支持 HTML/纯文本；PDF 等请上传截图并补人工核验")
    text = content.decode("utf-8", errors="replace")
    parser = TextExtractor()
    parser.feed(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"url": url, "final_url": final_url, "content_type": content_type, "retrieved_at": now(),
            "sha256": sha256(path), "text": "\n".join(parser.parts)[:16000]}


async def _capture(url: str, output: Path):
    from playwright.async_api import async_playwright
    validate_url(url)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900}, service_workers="block", offline=True)
            async def route(request_route):
                try:
                    if request_route.request.method != "GET":
                        await request_route.abort()
                        return
                    validate_url(request_route.request.url)
                    data, mime_type, _ = await asyncio.to_thread(safe_get, request_route.request.url)
                    # Browser is offline. Every fetched resource goes through
                    # the pinned public TCP connector, including redirects.
                    await request_route.fulfill(status=200, content_type=mime_type, body=data)
                except ValueError:
                    await request_route.abort()
            await page.route("**/*", route)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.screenshot(path=str(output), full_page=False)
        finally:
            await browser.close()


def capture_source(url: str, output: Path):
    asyncio.run(_capture(url, output))
