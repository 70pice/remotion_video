"""Role-scoped stdio MCP bridge; models choose inputs, never local paths."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from videoagents.providers.network import safe_get, validate_url
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools.media import detect_media, probe, sha256, video_metadata
from videoagents.tools.research_skills import research_skill_catalog
from videoagents.tools.sources import capture_source, fetch_source

TOOL_NAMES = frozenset({"skill", "search", "source", "visual", "screenshot"})
MAX_MESSAGE_BYTES = 64 * 1024
MAX_WORKSPACE_BYTES = 256 * 1024 * 1024
PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
# Only literal codes raised by this bridge are public; never stringify an exception.
ERROR_RECOVERY = {
    "research_skill_unavailable": "Use search and source directly, or choose another installed catalogue skill; do not retry the missing skill.",
    "research_skill_too_large": "Skip this skill and use search and source directly; report the missing guidance as a limitation.",
    "research_platform_disabled": "Use only configured research_platforms from the input settings; do not retry a disabled platform.",
    "unknown_research_platform": "Choose a supported platform identifier from the configured research_platforms.",
    "research_search_budget_exhausted": "Stop search calls. Use already read evidence and report remaining limitations in the final business result.",
    "research_source_budget_exhausted": "Stop fetching new sources. Use already read evidence and report remaining limitations in the final business result.",
    "research_download_budget_exhausted": "Stop source downloads and visual captures. Use existing files and report remaining limitations in the final business result.",
    "research_images_disabled": "Skip image downloads because settings disable them; use permitted evidence and report the image gap.",
    "research_screenshots_disabled": "Skip screenshots because settings disable them; use permitted evidence and report the screenshot gap.",
    "source_text_empty": "Try another accessible public HTML or plain-text source; do not treat the empty page as evidence.",
    "visual_source_not_read": "Read the source with the source tool before requesting its visual or screenshot.",
    "visual_not_video": "Use a direct playable video file from a read source, or report the video gap; a webpage is not a downloaded video.",
    "visual_not_decodable_image": "Use another valid image from a read source, or report the image gap.",
    "screenshot_size_invalid": "Skip this screenshot and report the gap; do not repeat the same oversized or empty capture.",
    "invalid_research_arguments": "Correct the arguments to match the advertised tool input schema before retrying.",
    "unknown_research_tool": "Use only tools advertised by tools/list for this role; unavailable tools cannot be enabled by a request.",
    "inactive_research_revision": "Stop all research calls. The task revision is inactive; report the blocked revision without changing job state.",
    "invalid_research_workspace": "Stop research calls and report the workspace configuration failure; do not choose another local path.",
    "linked_research_workspace": "Stop research calls and report the workspace boundary failure; do not follow or replace links.",
    "linked_research_file": "Stop research calls and report the file boundary failure; do not follow or replace links.",
}


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1, "maxLength": 1000}
URL = {"type": "string", "minLength": 1, "maxLength": 4000}
TOOLS = [
    {"name": "skill", "description": "Read one installed, catalogued research SKILL.md; no scripts execute.",
     "inputSchema": _schema({"name": TEXT}, ["name"])},
    {"name": "search", "description": "Discover public sources on configured platforms, within the cumulative search budget.",
     "inputSchema": _schema({"query": TEXT, "platforms": {"type": "array", "minItems": 1,
                            "maxItems": 40, "items": TEXT}}, ["query", "platforms"])},
    {"name": "source", "description": "Fetch actual HTML/plain-text evidence. Save parsed UTF-8 text; return source manifest and images.",
     "inputSchema": _schema({"url": URL, "platform": TEXT}, ["url", "platform"])},
    {"name": "visual", "description": "Download a direct image or MP4 from a previously read source; return a real-file manifest and measured metadata.",
     "inputSchema": _schema({"source_url": URL, "url": URL, "kind": {"enum": ["image", "video"]},
                            "description": TEXT}, ["source_url", "url", "kind", "description"])},
    {"name": "screenshot", "description": "Capture a previously read public source when screenshots are enabled; return a real-file manifest.",
     "inputSchema": _schema({"source_url": URL, "description": TEXT}, ["source_url", "description"])},
]


class ResearchBridge:
    def __init__(self, workspace: Path, runtime: Path, job_id: str, revision: int,
                 allowed_tools: set[str] | None = None):
        if not re.fullmatch(r"[0-9a-f]{32}", job_id) or revision < 1:
            raise ValueError("invalid_job_identity")
        self.runtime = runtime.absolute()
        self.workspace = workspace.absolute()
        self.job_id, self.revision = job_id, revision
        # Roles get different toolsets: the writer reads (skill/search/source),
        # the materials node also downloads visuals and captures screenshots.
        self.tools = [item for item in TOOLS if allowed_tools is None or item["name"] in allowed_tools]
        if not self.tools:
            raise ValueError("no_research_tools_enabled")
        self.tool_names = {item["name"] for item in self.tools}
        expected = self.runtime / "jobs" / job_id / "revisions" / str(revision) / "skills-research"
        if self.workspace != expected or not (self.runtime / "application.sqlite").is_file():
            raise ValueError("invalid_research_workspace")
        self._check_workspace()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.repo = Repository(self.runtime)
        self.settings = SettingsService(self.repo).internal()
        self.sources: dict[str, dict[str, Any]] = {}
        self.searches = 0
        self.active()

    def _check_workspace(self) -> None:
        if self.runtime.resolve() != self.runtime or self.workspace.resolve() != self.workspace:
            raise ValueError("linked_research_workspace")
        for path in (self.workspace, *self.workspace.parents):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("linked_research_workspace")
            if path == self.runtime:
                break
        if self.workspace.exists() and not self.workspace.is_dir():
            raise ValueError("invalid_research_workspace")

    def active(self) -> None:
        self._check_workspace()
        job = self.repo.get_job(self.job_id)
        if job.revision != self.revision or job.status == "CANCELLED":
            raise ValueError("inactive_research_revision")

    def _file(self, extension: str) -> Path:
        self.active()
        path = self.workspace / f"mcp-{uuid.uuid4().hex}{extension}"
        with path.open("xb"):
            pass
        return path

    def _space(self, size: int) -> None:
        self.active()
        total = 0
        for path in self.workspace.iterdir():
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("linked_research_file")
            if path.is_file():
                total += path.stat().st_size
        if total + size > MAX_WORKSPACE_BYTES:
            raise ValueError("research_download_budget_exhausted")

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.active()
        tool = next((item for item in self.tools if item["name"] == name), None)
        if not tool or type(arguments) is not dict:
            raise ValueError("unknown_research_tool")
        schema = tool["inputSchema"]
        if set(arguments) - schema["properties"].keys() or not set(schema["required"]) <= arguments.keys():
            raise ValueError("invalid_research_arguments")
        for key, value in arguments.items():
            spec = schema["properties"][key]
            if key == "platforms":
                if (type(value) is not list or not 1 <= len(value) <= 40
                        or any(type(item) is not str or not 1 <= len(item) <= 1000 for item in value)):
                    raise ValueError("invalid_research_arguments")
            elif type(value) is not str or not value.strip() or len(value) > spec.get("maxLength", 1000):
                raise ValueError("invalid_research_arguments")
            if "enum" in spec and value not in spec["enum"]:
                raise ValueError("invalid_research_arguments")
        result = getattr(self, name)(**arguments)
        self.active()
        return result

    def skill(self, name: str) -> dict:
        item = next((item for item in research_skill_catalog() if item["name"] == name and item["installed"]), None)
        if not item:
            raise ValueError("research_skill_unavailable")
        with Path(item["path"]).open("rb") as stream:
            data = stream.read(128 * 1024 + 1)
        if len(data) > 128 * 1024:
            raise ValueError("research_skill_too_large")
        return {"name": name, "guidance": data.decode("utf-8")}

    def search(self, query: str, platforms: list[str]) -> dict:
        # Lazy import prevents llm -> cli_runner -> bridge -> research -> llm cycles.
        from videoagents.tools.research import discover

        platforms = list(dict.fromkeys(platforms))
        if not set(platforms) <= set(self.settings["research_platforms"]):
            raise ValueError("research_platform_disabled")
        remaining = self.settings["research_max_searches"] - self.searches
        if remaining <= 0:
            raise ValueError("research_search_budget_exhausted")
        result = discover(self.repo, query, platforms, job_id=self.job_id, revision=self.revision,
                          per_platform=self.settings["research_results_per_platform"], max_searches=remaining)
        self.searches += sum(item["status"] in {"ok", "error"} for item in result["tools"])
        return result

    def source(self, url: str, platform: str) -> dict:
        from videoagents.tools.research import CATALOG_BY_ID

        validate_url(url)
        if platform not in CATALOG_BY_ID:
            raise ValueError("unknown_research_platform")
        if url in self.sources:
            return self.sources[url]
        if len(self.sources) >= self.settings["research_max_sources"]:
            raise ValueError("research_source_budget_exhausted")
        self._space(3 * 1024 * 1024)
        raw = self._file(".html")
        try:
            receipt = fetch_source(url, raw)
        finally:
            raw.unlink(missing_ok=True)
        text = receipt["text"].strip()
        if not text:
            raise ValueError("source_text_empty")
        self.active()
        path = self._file(".txt")
        try:
            path.write_text(text, encoding="utf-8")
            self.active()
            manifest = {"url": url, "platform": platform, "title": (receipt["title"] or url)[:500],
                        "text_file": path.name, "sha256": sha256(path)}
            result = {"source": manifest, "text": text, "images": receipt["images"], "final_url": receipt["final_url"]}
        except Exception:
            path.unlink(missing_ok=True)
            raise
        self.sources[url] = result
        return result

    def _owner(self, source_url: str) -> None:
        if source_url not in self.sources:
            raise ValueError("visual_source_not_read")

    @staticmethod
    def _metadata(path: Path, kind: str) -> dict:
        mime, _ = detect_media(path.read_bytes(), path)
        if kind == "video":
            if not mime.startswith("video/"):
                raise ValueError("visual_not_video")
            return video_metadata(path)
        stream = next((item for item in probe(path).get("streams", []) if item.get("codec_type") == "video"), {})
        width, height = stream.get("width", 0), stream.get("height", 0)
        if not mime.startswith("image/") or min(width, height) < 32 or width * height > 40_000_000:
            raise ValueError("visual_not_decodable_image")
        return {"width": width, "height": height}

    def visual(self, source_url: str, url: str, kind: str, description: str) -> dict:
        self._owner(source_url)
        validate_url(url)
        if kind == "image" and not self.settings["research_download_images"]:
            raise ValueError("research_images_disabled")
        limit = (100 if kind == "video" else 10) * 1024 * 1024
        # The remaining workspace budget also bounds the request's allocation.
        self._space(0)
        used = sum(path.stat().st_size for path in self.workspace.iterdir() if path.is_file())
        if used >= MAX_WORKSPACE_BYTES:
            raise ValueError("research_download_budget_exhausted")
        data, _, _ = safe_get(url, max_bytes=min(limit, MAX_WORKSPACE_BYTES - used))
        self._space(len(data))
        path = self._file(".mp4" if kind == "video" else ".image")
        try:
            path.write_bytes(data)
            metadata = self._metadata(path, kind)
            self.active()
            manifest = {"source_url": source_url, "kind": kind, "file": path.name, "sha256": sha256(path),
                        "image_url": url if kind == "image" else "", "media_url": url if kind == "video" else "",
                        "description": description}
            return {"visual": manifest, "metadata": metadata}
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def screenshot(self, source_url: str, description: str) -> dict:
        self._owner(source_url)
        if not self.settings["capture_enabled"]:
            raise ValueError("research_screenshots_disabled")
        self._space(10 * 1024 * 1024)
        path = self._file(".png")
        try:
            capture_source(source_url, path)
            if not 0 < path.stat().st_size <= 10 * 1024 * 1024:
                raise ValueError("screenshot_size_invalid")
            metadata = self._metadata(path, "image")
            self.active()
            return {"visual": {"source_url": source_url, "kind": "screenshot", "file": path.name,
                               "sha256": sha256(path), "image_url": "", "media_url": "", "description": description},
                    "metadata": metadata}
        except Exception:
            path.unlink(missing_ok=True)
            raise


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(bridge: ResearchBridge, incoming: BinaryIO, outgoing: TextIO) -> None:
    """UTF-8 newline JSON-RPC per MCP stdio; never emit tracebacks or tool logs."""
    initialized = False
    while line := incoming.readline(MAX_MESSAGE_BYTES + 1):
        if len(line) > MAX_MESSAGE_BYTES:
            # Drain one oversized frame so its remainder cannot become a request.
            while not line.endswith(b"\n") and (line := incoming.readline(MAX_MESSAGE_BYTES + 1)):
                pass
            response = _error(None, -32700, "Message too large")
        else:
            parsed = True
            try:
                request = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                parsed = False
                request = None
            if not parsed:
                response = _error(None, -32700, "Parse error")
            elif (type(request) is not dict or request.get("jsonrpc") != "2.0"
                    or not isinstance(request.get("method"), str)):
                response = _error(None, -32600, "Invalid request")
            elif "id" not in request:
                continue
            else:
                identity, method = request["id"], request["method"]
                params = request.get("params", {})
                result = None
                if type(params) is not dict:
                    response = _error(identity, -32602, "Invalid params")
                elif method == "initialize":
                    version = params.get("protocolVersion")
                    initialized = True
                    result = {"protocolVersion": version if version in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[-1],
                              "capabilities": {"tools": {}}, "serverInfo": {"name": "videoagents_research", "version": "1"}}
                elif not initialized:
                    response = _error(identity, -32000, "Initialize first")
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {"tools": bridge.tools}
                elif method == "tools/call":
                    try:
                        # Existing backends may log; stdout belongs exclusively to MCP.
                        with contextlib.redirect_stdout(io.StringIO()):
                            payload = bridge.call(params.get("name"), params.get("arguments", {}))
                        result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
                    except Exception as exc:
                        code = exc.args[0] if (type(exc) is ValueError and len(exc.args) == 1
                                             and type(exc.args[0]) is str) else None
                        if code not in ERROR_RECOVERY:
                            code = "research_tool_failed"
                        payload = {"error_code": code, "recovery": ERROR_RECOVERY.get(code,
                            "Report the failed tool as a limitation; avoid blind retries. Check source access, settings, budget and active revision.")}
                        result = {"isError": True, "content": [{"type": "text", "text": json.dumps(payload)}]}
                else:
                    response = _error(identity, -32601, "Method not found")
                if result is not None:
                    response = {"jsonrpc": "2.0", "id": identity, "result": result}
        outgoing.write(json.dumps(response, ensure_ascii=False) + "\n")
        outgoing.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--tools", default="", help="逗号分隔的可用工具白名单;留空表示全部")
    args = parser.parse_args()
    allowed = {name.strip() for name in args.tools.split(",") if name.strip()} or None
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        bridge = ResearchBridge(args.workspace, args.runtime, args.job_id, args.revision, allowed_tools=allowed)
        serve(bridge, sys.stdin.buffer, sys.stdout)
    except Exception:
        print("Research bridge could not start or continue.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
