"""Save actual source HTML/text and optionally browser screenshots."""

import asyncio
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from videoagents.providers.network import safe_get, validate_url
from videoagents.storage.repository import now
from videoagents.tools.media import sha256


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0
        self.in_title = False
        self.title = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "img":
            source = attributes.get("src") or attributes.get("data-src")
            if source and len(self.images) < 12:
                self.images.append({"url": source, "description": attributes.get("alt", "") or ""})
        if tag == "meta" and (attributes.get("property") or attributes.get("name")) in {"og:image", "twitter:image"}:
            if attributes.get("content") and len(self.images) < 12:
                self.images.insert(0, {"url": attributes["content"], "description": ""})
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data.strip())
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
    images = []
    for item in parser.images:
        image_url = urljoin(final_url, item["url"])
        parsed = urlparse(image_url)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            images.append({"url": image_url, "source_url": url, "description": item["description"][:1000]})
    return {"url": url, "final_url": final_url, "content_type": content_type, "retrieved_at": now(),
            "sha256": sha256(path), "text": "\n".join(parser.parts)[:16000],
            "title": " ".join(parser.title)[:500], "images": images}


async def _capture(url: str, output: Path):
    from playwright.async_api import async_playwright
    validate_url(url)
    async with async_playwright() as playwright:
        # 优先自带浏览器；未下载时使用系统 Chrome 的独立无登录实例。
        channel = None if Path(playwright.chromium.executable_path).is_file() else "chrome"
        browser = await playwright.chromium.launch(headless=True, channel=channel)
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900}, service_workers="block", offline=True,
                                          accept_downloads=False)
            requests, total_bytes = 0, 0
            async def route(request_route):
                nonlocal requests, total_bytes
                try:
                    requests += 1
                    if request_route.request.method != "GET" or requests > 64 or total_bytes >= 12 * 1024 * 1024:
                        await request_route.abort()
                        return
                    validate_url(request_route.request.url)
                    data, mime_type, _ = await asyncio.to_thread(safe_get, request_route.request.url,
                                                                max_bytes=3 * 1024 * 1024)
                    total_bytes += len(data)
                    if total_bytes > 12 * 1024 * 1024:
                        await request_route.abort()
                        return
                    # Browser is offline. Every fetched resource goes through
                    # the pinned public TCP connector, including redirects.
                    await request_route.fulfill(status=200, content_type=mime_type, body=data)
                except Exception:
                    await request_route.abort()
            await page.route("**/*", route)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.screenshot(path=str(output), full_page=False)
        finally:
            await browser.close()


def capture_source(url: str, output: Path):
    asyncio.run(_capture(url, output))
