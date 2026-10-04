"""Bounded multi-platform discovery for the materials node.

The catalog is intentionally honest: most social platforms are searched through
the configured web provider with site filters unless a local logged-in CLI is
available and explicitly supported here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from videoagents.providers.llm import CapabilityMissing
from videoagents.providers.search import search
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, Repository
from worker.process_manager import RenderCancelled, terminate_tree
from worker.windows_job import WindowsJob

PLATFORM_CATALOG: tuple[dict[str, Any], ...] = (
    {"id": "web", "label": "全网网页", "domains": [], "kind": "search", "notes": "使用已配置搜索服务做通用网页发现。"},
    {"id": "google", "label": "Google", "domains": [], "kind": "native_or_search", "native_tool": "opencli", "notes": "优先使用 OpenCLI Google 公开搜索；否则仅在 Google CSE 配置完整时启用。"},
    {"id": "bing", "label": "Bing", "domains": ["bing.com"], "kind": "indexed", "notes": "通过站内索引搜索公开页面。"},
    {"id": "baidu", "label": "百度", "domains": ["baidu.com", "baike.baidu.com"], "kind": "indexed", "notes": "通过站内索引搜索公开页面。"},
    {"id": "x", "label": "X / Twitter", "domains": ["x.com", "twitter.com"], "kind": "login_or_indexed", "native_tool": "twitter", "requires_login": True, "notes": "原生读取需要本机登录态；否则只做公开索引检索。"},
    {"id": "youtube", "label": "YouTube", "domains": ["youtube.com", "youtu.be"], "kind": "native_or_indexed", "native_tool": "yt-dlp", "notes": "安装 yt-dlp 时可原生搜索公开视频元数据。"},
    {"id": "zhihu", "label": "知乎", "domains": ["zhihu.com"], "kind": "indexed", "notes": "默认用搜索服务检索公开知乎内容。"},
    {"id": "reddit", "label": "Reddit", "domains": ["reddit.com"], "kind": "login_or_indexed", "native_tool": "opencli/rdt", "requires_login": True, "notes": "原生读取需要 OpenCLI 或 rdt 登录态；默认只做公开索引检索。"},
    {"id": "bilibili", "label": "B站", "domains": ["bilibili.com"], "kind": "native_or_indexed", "native_tool": "bili", "notes": "安装 bili-cli 时可原生搜索公开视频。"},
    {"id": "xiaohongshu", "label": "小红书", "domains": ["xiaohongshu.com", "xhslink.com"], "kind": "login_or_indexed", "native_tool": "opencli", "requires_login": True, "notes": "原生读取需要 OpenCLI 浏览器登录态；默认只做公开索引检索。"},
    {"id": "weibo", "label": "微博", "domains": ["weibo.com"], "kind": "indexed", "notes": "通过公开索引检索。"},
    {"id": "douyin", "label": "抖音", "domains": ["douyin.com"], "kind": "indexed", "notes": "通过公开索引检索；不使用发布类账号能力。"},
    {"id": "kuaishou", "label": "快手", "domains": ["kuaishou.com"], "kind": "indexed", "notes": "通过公开索引检索；不使用发布类账号能力。"},
    {"id": "wechat", "label": "微信公众号/搜狗微信", "domains": ["weixin.qq.com", "mp.weixin.qq.com", "weixin.sogou.com"], "kind": "indexed", "notes": "通过公开索引检索可访问文章。"},
    {"id": "wikipedia", "label": "Wikipedia", "domains": ["wikipedia.org"], "kind": "indexed", "notes": "公开百科来源。"},
    {"id": "wikimedia", "label": "Wikimedia Commons", "domains": ["commons.wikimedia.org", "upload.wikimedia.org"], "kind": "indexed", "notes": "适合找可溯源图片。"},
    {"id": "github", "label": "GitHub", "domains": ["github.com"], "kind": "native_or_indexed", "native_tool": "gh", "notes": "安装 GitHub CLI 时可原生搜索仓库。"},
    {"id": "arxiv", "label": "arXiv", "domains": ["arxiv.org"], "kind": "indexed", "notes": "论文和技术资料。"},
    {"id": "stackoverflow", "label": "Stack Overflow", "domains": ["stackoverflow.com"], "kind": "indexed", "notes": "技术问答。"},
    {"id": "hackernews", "label": "Hacker News", "domains": ["news.ycombinator.com", "hn.algolia.com"], "kind": "indexed", "notes": "技术社区讨论。"},
    {"id": "v2ex", "label": "V2EX", "domains": ["v2ex.com"], "kind": "indexed", "notes": "公开 API 可扩展；当前做索引检索。"},
    {"id": "medium", "label": "Medium", "domains": ["medium.com"], "kind": "indexed", "notes": "公开文章。"},
    {"id": "quora", "label": "Quora", "domains": ["quora.com"], "kind": "indexed", "notes": "公开问答索引。"},
    {"id": "douban", "label": "豆瓣", "domains": ["douban.com"], "kind": "indexed", "notes": "公开页面索引。"},
    {"id": "google_scholar", "label": "Google Scholar", "domains": ["scholar.google.com"], "kind": "indexed", "notes": "只通过搜索服务发现可访问条目，不抓登录/验证码页面。"},
    {"id": "pexels", "label": "Pexels", "domains": ["pexels.com"], "kind": "indexed", "notes": "图片素材发现；许可仍需人工核验。"},
    {"id": "unsplash", "label": "Unsplash", "domains": ["unsplash.com"], "kind": "indexed", "notes": "图片素材发现；许可仍需人工核验。"},
    {"id": "instagram", "label": "Instagram", "domains": ["instagram.com"], "kind": "login_or_indexed", "native_tool": "opencli", "requires_login": True, "notes": "原生读取需要 OpenCLI 登录态；默认只做公开索引检索。"},
    {"id": "facebook", "label": "Facebook", "domains": ["facebook.com"], "kind": "login_or_indexed", "native_tool": "opencli", "requires_login": True, "notes": "原生读取需要 OpenCLI 登录态；默认只做公开索引检索。"},
    {"id": "linkedin", "label": "LinkedIn", "domains": ["linkedin.com"], "kind": "indexed", "notes": "只检索公开页面。"},
    {"id": "producthunt", "label": "Product Hunt", "domains": ["producthunt.com"], "kind": "indexed", "notes": "产品资料与评论索引。"},
    {"id": "official", "label": "官方网站/新闻稿", "domains": [], "kind": "search", "notes": "与主题词组合，优先发现官方来源。"},
)

CATALOG_BY_ID = {item["id"]: item for item in PLATFORM_CATALOG}
NATIVE_TOOLS = {"yt-dlp": ("yt-dlp",), "bili": ("bili",), "gh": ("gh",), "opencli": ("opencli",)}
NPM_BIN_ENTRIES = {"opencli": ("@jackwener/opencli", "opencli")}


def _user_local_bin() -> Path:
    return Path.home() / ".local" / "bin"


def _native_env() -> dict[str, str]:
    env = os.environ.copy()
    local_bin = _user_local_bin()
    path = env.get("PATH") or env.get("Path") or ""
    if local_bin.is_dir():
        env["PATH"] = str(local_bin) + os.pathsep + path if path else str(local_bin)
    if os.name == "nt":
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _search_ready(settings: dict[str, Any]) -> bool:
    provider = settings.get("search_provider")
    if provider == "opencli_google":
        return _command_prefix("opencli") is not None
    return bool(settings.get("search_api_key")) and (provider == "tavily" or (provider == "google_cse" and settings.get("google_search_engine_id")))


def platform_catalog(settings: dict[str, Any]) -> list[dict[str, Any]]:
    ready = _search_ready(settings)
    result = []
    for item in PLATFORM_CATALOG:
        native = item.get("native_tool")
        status = "search_ready" if ready else "search_unconfigured"
        detail = ("可通过本机 OpenCLI Google 公开索引检索" if settings.get("search_provider") == "opencli_google" and ready
                  else "可通过配置的搜索服务检索公开网页" if ready
                  else "未配置搜索服务，只能使用手动来源或已安装原生工具")
        if native:
            available = any(_command_prefix(name) for name in NATIVE_TOOLS.get(native, (native,)))
            if item.get("requires_login"):
                status = "search_ready" if ready else "search_unconfigured"
                detail = ("当前仅检索公开索引；账号原生读取尚未接入本项目" if ready
                          else "账号原生读取尚未接入；需配置公开搜索服务或补充来源")
            elif available:
                status = "native_installed"
                detail = f"已检测到 {native}；运行时会验证只读原生检索是否可用"
        if item["id"] == "google":
            if any(_command_prefix(name) for name in NATIVE_TOOLS["opencli"]):
                status, detail = "native_installed", "已检测到 OpenCLI；运行时会验证浏览器连接并记录结果"
            elif settings.get("search_provider") == "google_cse" and ready:
                status, detail = "search_ready", "Google CSE 已配置"
            else:
                status, detail = "search_unconfigured", "Google 平台只在 Google CSE 配置完整时启用"
        result.append({**item, "status": status, "detail": detail})
    return result



def _public_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return url


def _host_allowed(url: str, domains: list[str]) -> bool:
    if not domains:
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _result(url: str, title: str, snippet: str, platform: str, backend: str, images: list[dict[str, str]] | None = None) -> dict[str, Any] | None:
    clean = _public_url(url)
    if not clean:
        return None
    return {"url": clean, "title": (title or clean)[:500], "snippet": (snippet or "")[:2000],
            "platform": platform, "backend": backend, "images": images or []}


def _command_prefix(name: str) -> list[str] | None:
    found = shutil.which(name)
    if not found:
        local_bin = _user_local_bin()
        if local_bin.is_dir():
            found = shutil.which(name, path=str(local_bin))
    if not found:
        return None
    path = Path(found).resolve()
    if not path.is_file():
        return None
    if os.name != "nt" or path.suffix.lower() == ".exe":
        return [str(path)]
    if path.suffix.lower() in {".js", ".mjs"}:
        node = shutil.which("node")
        return [node, str(path)] if node else None
    node = shutil.which("node")
    package = NPM_BIN_ENTRIES.get(name)
    if node and package and path.suffix.lower() in {".cmd", ".bat"}:
        package_name, bin_name = package
        package_json = path.parent / "node_modules" / package_name / "package.json"
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        bin_value = data.get("bin", {})
        entry = bin_value.get(bin_name) if isinstance(bin_value, dict) else bin_value if isinstance(bin_value, str) else None
        if isinstance(entry, str):
            script = (package_json.parent / entry).resolve()
            if script.is_file() and package_json.parent in script.parents:
                return [node, str(script)]
    # Do not execute shell shims through cmd.exe; callers will fall back.
    return None


def _check_active(repository: Repository | None, job_id: str, revision: int) -> None:
    if not repository or not job_id:
        return
    job = repository.get_job(job_id)
    if job.revision != revision:
        raise Conflict("素材检索版本已失效")
    if job.status == "CANCELLED":
        raise RenderCancelled("素材检索已取消")


def _safe_cli_query(query: str) -> str:
    if query.startswith("-"):
        raise CapabilityMissing("检索词不能以连字符开头，避免被 CLI 解释为选项", ["query"])
    return query


def _run(args: list[str], timeout: int = 20, *, repository: Repository | None = None, job_id: str = "", revision: int = 1) -> str:
    with tempfile.TemporaryDirectory(prefix="videoagents-research-") as temporary:
        output_path = f"{temporary}/stdout.txt"
        job = WindowsJob()
        try:
            with open(output_path, "wb") as stdout:
                process = subprocess.Popen(args, stdout=stdout, stderr=subprocess.DEVNULL, shell=False,
                                           env=_native_env(),
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                           start_new_session=os.name != "nt")
            try:
                job.assign(process)
            except BaseException:
                terminate_tree(process)
                raise
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                _check_active(repository, job_id, revision)
                if time.monotonic() > deadline:
                    terminate_tree(process)
                    raise TimeoutError("native_timeout")
                if os.path.getsize(output_path) > 2_000_000:
                    terminate_tree(process)
                    raise RuntimeError("native_output_limit")
                time.sleep(0.1)
            if process.returncode:
                raise RuntimeError("native_failed")
            if os.path.getsize(output_path) > 2_000_000:
                raise RuntimeError("native_output_limit")
            _check_active(repository, job_id, revision)
            with open(output_path, "rb") as stream:
                return stream.read(2_000_000).decode("utf-8", errors="replace")
        finally:
            if 'process' in locals():
                terminate_tree(process)
            job.close()


def _youtube(query: str, limit: int, repository: Repository | None = None, job_id: str = "", revision: int = 1) -> list[dict[str, Any]]:
    output = _run([*_command_prefix("yt-dlp"), "--flat-playlist", "--dump-json",
                   f"ytsearch{limit}:{_safe_cli_query(query)}"],
                  repository=repository, job_id=job_id, revision=revision)
    rows = []
    for line in output.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        image = item.get("thumbnail")
        if not image:
            thumbnails = item.get("thumbnails")
            if isinstance(thumbnails, list) and thumbnails:
                image = thumbnails[-1].get("url") if isinstance(thumbnails[-1], dict) else None
        images = [{"url": image, "source_url": item.get("webpage_url") or "", "description": item.get("title") or ""}] if image else []
        value = _result(item.get("webpage_url") or item.get("original_url") or "", item.get("title") or "",
                        item.get("description") or "", "youtube", "yt-dlp", images)
        if value:
            rows.append(value)
    return rows


def _github(query: str, limit: int, repository: Repository | None = None, job_id: str = "", revision: int = 1) -> list[dict[str, Any]]:
    output = _run([*_command_prefix("gh"), "search", "repos", "--sort", "stars", "--limit", str(limit),
                   "--json", "fullName,description,url", "--", _safe_cli_query(query)],
                  repository=repository, job_id=job_id, revision=revision)
    rows = []
    for item in json.loads(output):
        value = _result(item.get("url") or "", item.get("fullName") or "", item.get("description") or "", "github", "gh")
        if value:
            rows.append(value)
    return rows


def _bilibili(query: str, limit: int, repository: Repository | None = None, job_id: str = "", revision: int = 1) -> list[dict[str, Any]]:
    output = _run([*_command_prefix("bili"), "search", "--type", "video", "-n", str(limit), "--", _safe_cli_query(query)],
                  repository=repository, job_id=job_id, revision=revision)
    rows = []
    seen = set()
    for bv in re.findall(r"\bBV[0-9A-Za-z]{10}\b", output):
        if bv in seen:
            continue
        seen.add(bv)
        value = _result(f"https://www.bilibili.com/video/{bv}", bv, "", "bilibili", "bili")
        if value:
            rows.append(value)
    return rows


def _google(query: str, limit: int, repository: Repository | None = None, job_id: str = "", revision: int = 1) -> list[dict[str, Any]]:
    output = _run([*_command_prefix("opencli"), "google", "search", "--limit", str(limit),
                   "--lang", "zh", "--window", "background", "--site-session", "ephemeral",
                   "--keep-tab", "false", "-f", "json", "--", _safe_cli_query(query)],
                  repository=repository, job_id=job_id, revision=revision)
    data = json.loads(output)
    items = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _result(item.get("url") or "", item.get("title") or "", item.get("snippet") or "", "google", "opencli")
        if value:
            rows.append(value)
    return rows


def _site_scoped_query(query: str, domains: list[str]) -> str:
    return query if not domains else query + " (" + " OR ".join(f"site:{domain}" for domain in domains) + ")"


def _google_indexed(query: str, platform_id: str, domains: list[str], limit: int,
                    repository: Repository | None = None, job_id: str = "", revision: int = 1) -> list[dict[str, Any]]:
    rows = []
    for row in _google(_site_scoped_query(query, domains), limit, repository, job_id, revision):
        if not _host_allowed(row["url"], domains):
            continue
        rows.append({**row, "platform": platform_id, "backend": "opencli_google_indexed"})
    return rows


NATIVE_HANDLERS = {"google": ("opencli", _google), "youtube": ("yt-dlp", _youtube),
                   "github": ("gh", _github), "bilibili": ("bili", _bilibili)}


def _owned_images(value: Any, owner_url: str, *, implicit_owner: bool) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    if not isinstance(value, list):
        return images
    for image in value:
        if not isinstance(image, dict) or not _public_url(str(image.get("url") or "")):
            continue
        source_url = image.get("source_url")
        if implicit_owner and not source_url:
            source_url = owner_url
        if source_url != owner_url:
            continue
        images.append({"url": image["url"], "source_url": owner_url,
                       "description": str(image.get("description") or "")[:500]})
    return images


def discover(repository: Repository, query: str, platform_ids: list[str], *, job_id: str,
             revision: int, per_platform: int = 3, max_searches: int = 8) -> dict[str, Any]:
    """Collect public discovery results across platforms with isolated failures."""
    platform_ids = list(dict.fromkeys(platform_ids))
    per_platform = max(1, min(int(per_platform), 5))
    max_searches = max(1, min(int(max_searches), 32))
    settings = SettingsService(repository).internal()
    results: list[dict[str, Any]] = []
    global_images: list[dict[str, str]] = []
    tools: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    searches = 0

    def add_many(rows: list[dict[str, Any]], domains: list[str]) -> int:
        added = 0
        for row in rows:
            url = row.get("url", "")
            if not _public_url(url) or not _host_allowed(url, domains) or url in seen_urls:
                continue
            seen_urls.add(url)
            row["images"] = _owned_images(row.get("images", []), url, implicit_owner=True)
            results.append(row)
            added += 1
            for image in row["images"]:
                global_images.append({"url": image["url"], "source_url": image["source_url"],
                                      "description": image.get("description", "")[:500],
                                      "platform": row["platform"], "backend": row["backend"]})
        return added

    def record(platform: str, backend: str, status: str, *, results_count: int = 0, error: str | None = None) -> None:
        item: dict[str, Any] = {"platform": platform, "backend": backend, "status": status,
                                "results_count": results_count}
        if error:
            item["error"] = error
        tools.append(item)

    def reserve(platform: str, backend: str) -> bool:
        nonlocal searches
        if searches >= max_searches:
            record(platform, backend, "skipped", error="search_budget_exhausted")
            return False
        searches += 1
        _check_active(repository, job_id, revision)
        return True

    for platform_id in platform_ids:
        catalog = CATALOG_BY_ID.get(platform_id)
        if not catalog:
            record(platform_id, "catalog", "error", error="unknown_platform")
            continue
        domains = catalog.get("domains", [])
        handler = NATIVE_HANDLERS.get(platform_id)
        if handler and _command_prefix(handler[0]):
            if not reserve(platform_id, handler[0]):
                continue
            try:
                rows = handler[1](query, per_platform, repository, job_id, revision)
                added = add_many(rows, domains)
                record(platform_id, handler[0], "ok", results_count=added)
                # per_platform 是结果上限，不是必须补满的目标；命中即交给下一平台。
                if rows:
                    continue
            except (Conflict, RenderCancelled):
                raise
            except Exception as exc:
                record(platform_id, handler[0], "error", error=type(exc).__name__)
        elif handler:
            record(platform_id, handler[0], "unavailable")
        provider_name = settings.get("search_provider")
        if platform_id == "google" and handler and _command_prefix(handler[0]) and provider_name == "opencli_google":
            # 相同 OpenCLI 查询不是另一个后端；空结果/失败后不重复启动同一工具。
            continue
        if platform_id == "google" and provider_name not in {"google_cse", "opencli_google"}:
            record(platform_id, "google", "unavailable", error="google_requires_opencli_or_google_cse")
            continue
        if not _search_ready(settings):
            record(platform_id, "search", "unavailable", error="search_not_configured")
            continue
        scoped_query = query if platform_id not in {"official"} else query + " official"
        if provider_name == "opencli_google":
            backend = "opencli_google_indexed"
            if not reserve(platform_id, backend):
                continue
            try:
                rows = _google_indexed(scoped_query, platform_id, domains, per_platform, repository, job_id, revision)
                added = add_many(rows, domains)
                record(platform_id, backend, "ok", results_count=added)
                continue
            except (Conflict, RenderCancelled):
                raise
            except Exception as exc:
                record(platform_id, backend, "error", error=type(exc).__name__)
                continue
        backend = provider_name or "search"
        if not reserve(platform_id, backend):
            continue
        try:
            data = search(repository, scoped_query, job_id, revision, domains=domains or None, limit=per_platform)
            rows = []
            global_provider_images = data.get("images", [])
            for item in data.get("results", []):
                url = item.get("url") or item.get("link") or ""
                images = _owned_images(item.get("images", []), url, implicit_owner=True)
                images.extend(_owned_images(global_provider_images, url, implicit_owner=False))
                value = _result(url, item.get("title") or "", item.get("content") or item.get("snippet") or "",
                                platform_id, backend, images)
                if value:
                    rows.append(value)
            added = add_many(rows, domains)
            record(platform_id, backend, "ok", results_count=added)
        except (Conflict, RenderCancelled):
            raise
        except CapabilityMissing as exc:
            record(platform_id, backend, "error", error=type(exc).__name__)
        except Exception as exc:
            record(platform_id, backend, "error", error=type(exc).__name__)

    return {"query": query, "results": results, "images": global_images, "tools": tools}

