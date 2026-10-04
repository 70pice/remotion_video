"""第一个业务节点：采集知识与真实视觉素材，交接冻结的研究包。"""

import ipaddress
import json
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from videoagents.contracts import Asset, Job, MaterialResearch
from videoagents.nodes.common import agent_state, request_input, start_stage, state_context
from videoagents.prompts import compose
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.providers.network import validate_url
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint, now
from videoagents.tools.media import detect_media, probe, sha256
from worker.process_manager import RenderCancelled

# 研究行为由独立 Markdown Prompt 定义；统一风格圣经在前，素材角色规则在后。
# CLI provider 只负责执行与接收最终 JSON；业务输入只从共享 VideoState 读取。
PROMPT = compose("shared-style", "materials")


class MaterialsNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "materials", "素材节点正在跨平台检索知识并采集图片与截图")
        try:
            research = self.collect(job, state)
            return state_context(self.repo, state, route="screenwriter", research=research, gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "materials", [str(exc)], getattr(exc, "fields", ["source_urls", "assets"]), exc)

    def active(self, job: Job) -> Job:
        current = self.repo.get_job(job.job_id)
        if current.revision != job.revision:
            raise Conflict("素材采集版本已失效")
        if current.status == "CANCELLED":
            raise RenderCancelled("素材采集已取消")
        return current

    def saved_json(self, job: Job, kind: str) -> dict | None:
        artifact = next((item for item in reversed(job.artifacts) if item.kind == kind and item.revision == job.revision), None)
        if not artifact:
            return None
        path, registered, owner = self.repo.artifact_path(artifact.artifact_id)
        if owner != job.job_id or sha256(path) != registered.sha256:
            raise Conflict("冻结的素材研究记录已改变")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def public_source_url(url: str) -> None:
        """清单 URL 只作公开来源标识；这里不重新联网，也不信任私网标识。"""
        validate_url(url, resolve=False)
        host = urlparse(url).hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise ValueError("素材来源必须是公开 HTTPS 地址")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        if not address.is_global:
            raise ValueError("素材来源不得指向私网或保留地址")

    @staticmethod
    def research_file(folder: Path, relative: str, digest: str, max_bytes: int) -> Path:
        """拒绝绝对路径、目录逃逸和链接逃逸；接收前核对大小与散列。"""
        requested = Path(relative)
        if requested.is_absolute() or requested.drive or ".." in requested.parts or ":" in relative:
            raise ValueError("技能文件必须使用研究目录内的相对路径")
        path = (folder / requested).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():
            raise ValueError("技能输出文件不存在或离开研究目录")
        if not 0 < path.stat().st_size <= max_bytes or sha256(path) != digest:
            raise ValueError("技能输出文件为空、过大或 SHA256 不一致")
        return path

    @staticmethod
    def audit_snapshot(path: Path, target: Path) -> bool:
        """审计接收端再做白名单投影，永远不原样发布输入文件。"""
        if not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024 * 1024:
            return False
        rows = []
        event_types = {"item.started", "item.updated", "item.completed", "turn.completed", "turn.failed", "error"}
        item_types = {"command_execution", "web_search", "mcp_tool_call", "file_change"}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict) or not isinstance(event.get("type"), str) or event["type"] not in event_types:
                continue
            row = {"type": event["type"]}
            if isinstance(event.get("item_type"), str) and event["item_type"] in item_types:
                row["item_type"] = event["item_type"]
            if isinstance(event.get("status"), str) and event["status"] in {"in_progress", "completed", "failed"}:
                row["status"] = event["status"]
            if type(event.get("exit_code")) is int:
                row["exit_code"] = event["exit_code"]
            rows.append(row)
        if not rows:
            return False
        target.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return True

    def collect(self, job: Job, state: VideoState | None = None) -> dict:
        """复用已完成研究，否则直接启动素材模型，再保存其最终产出。"""
        job = self.active(job)
        frozen = self.saved_json(job, "research")
        if frozen is not None and frozen.get("status", "COMPLETED") == "COMPLETED":
            return frozen
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "skills-research"
        folder.mkdir(parents=True, exist_ok=True)
        context = agent_state(self.repo, job, state)
        # sink 在模型可写目录之外；每次调用独立命名，避免重放覆盖已登记记录。
        audit_path = folder.parent / f"material-tool-events-{uuid.uuid4().hex[:12]}.jsonl"
        try:
            output = self.model.invoke(context, "materials", PROMPT, fields=("brief", "assets", "settings"),
                output_schema=MaterialResearch.model_json_schema(), research_directory=folder, audit_path=audit_path)
        finally:
            # 只登记 runner 输出的脱敏事件摘要；异常时也保留用于定位缺口。
            current = self.active(job)
            snapshot = folder.parent / f"material-tool-audit-{uuid.uuid4().hex[:12]}.jsonl"
            if self.audit_snapshot(audit_path, snapshot):
                artifact = self.service.register_artifact(current, snapshot, "material_tool_audit", "application/x-ndjson")
                self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                    artifacts=[item for item in current.artifacts if item.kind != "material_tool_audit"] + [artifact])
        return self.save_research(job, output, folder)

    def save_research(self, job: Job, output: dict, folder: Path) -> dict:
        """校验模型交付的真实文件，登记来源和画面，冻结给后续节点使用。"""
        settings = SettingsService(self.repo).internal()
        bundle = MaterialResearch.model_validate(output)
        if not bundle.sources:
            detail = "；".join(bundle.limitations)[:1500]
            raise CapabilityMissing("技能研究未读取到可用正文；" + (detail or "请补充来源链接或检查检索能力"), ["source_urls", "role_models"])
        if len(bundle.sources) > settings["research_max_sources"] or len(bundle.visuals) > settings["research_max_visuals"]:
            raise ValueError("技能研究清单超过设置中的来源或画面数量上限")
        urls = [item.url for item in bundle.sources]
        if len(urls) != len(set(urls)):
            raise ValueError("技能研究清单包含重复来源")
        files: dict[str, Path] = {}
        texts: dict[str, str] = {}
        # 全部清单校验通过后才登记正文与素材，避免坏清单留下半包产物。
        for item in bundle.sources:
            self.public_source_url(item.url)
            path = self.research_file(folder, item.text_file, item.sha256, 1024 * 1024)
            try:
                text = path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError as exc:
                raise ValueError("技能来源正文必须是 UTF-8 文本") from exc
            if not text:
                raise ValueError("技能来源正文为空")
            files[item.text_file], texts[item.url] = path, text[:16000]
        for item in bundle.visuals:
            if item.source_url not in urls:
                raise ValueError("技能图片没有关联已读取的来源")
            if ((item.kind == "image" and not settings["research_download_images"])
                    or (item.kind == "screenshot" and not settings["capture_enabled"])):
                raise ValueError("技能研究清单违反图片或截图开关设置")
            if item.image_url:
                self.public_source_url(item.image_url)
            path = self.research_file(folder, item.file, item.sha256, 10 * 1024 * 1024)
            mime, _ = detect_media(path.read_bytes())
            streams = probe(path).get("streams", [])
            stream = next((value for value in streams if value.get("codec_type") == "video"), {})
            width, height = stream.get("width", 0), stream.get("height", 0)
            if not mime.startswith("image/") or min(width, height) < 32 or width * height > 40_000_000:
                raise ValueError("技能图片无法解码、过小或分辨率超过限制")
            files[item.file] = path
        self.active(job)
        snapshots = folder.parent / "sources"
        snapshots.mkdir(parents=True, exist_ok=True)

        def freeze_file(relative: str, digest: str, suffix: str) -> Path:
            target = snapshots / f"skill-{digest}{suffix}"
            if not target.exists():
                shutil.copyfile(files[relative], target)
            if sha256(target) != digest:
                raise Conflict("冻结的技能输出文件已改变")
            return target

        research = {"schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
                    "limitations": list(bundle.limitations), "collected_at": now()}
        if not bundle.visuals and settings["research_max_visuals"] and (settings["capture_enabled"] or settings["research_download_images"]):
            research["limitations"].append("本次未取得真实图片或截图，导演仍需补充画面素材。")
        for item in bundle.sources:
            existing = next((artifact for artifact in self.active(job).artifacts
                             if artifact.kind == "source" and artifact.revision == job.revision
                             and artifact.sha256 == item.sha256
                             and self.repo.artifact_metadata(artifact.artifact_id).get("source_url") == item.url), None)
            receipt = None
            if existing:
                path, _, owner = self.repo.artifact_path(existing.artifact_id)
                if owner != job.job_id or sha256(path) != item.sha256:
                    raise Conflict("冻结的技能来源文件已改变")
                receipt = self.repo.artifact_metadata(existing.artifact_id).get("receipt")
            if not receipt:
                path = freeze_file(item.text_file, item.sha256, ".txt")
                current = self.active(job)
                artifact = self.service.register_artifact(current, path, "source", "text/plain")
                receipt = {"url": item.url, "final_url": item.url, "title": item.title,
                    "text": texts[item.url], "platform": item.platform, "content_type": "text/plain",
                    "retrieved_at": now(), "sha256": item.sha256, "knowledge_status": "skill_read",
                    "artifact_id": artifact.artifact_id, "artifact_url": artifact.url}
                self.repo.update_artifact_metadata(artifact.artifact_id, {"source_url": item.url, "receipt": receipt})
                self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                                     artifacts=current.artifacts + [artifact])
            receipt = {**receipt, "asset_ids": []}
            research["sources"].append(receipt)
        sources = {item["url"]: item for item in research["sources"]}
        for item in bundle.visuals:
            _, extension = detect_media(files[item.file].read_bytes())
            path = freeze_file(item.file, item.sha256, extension)
            asset = self.attach_image(job, path, item.source_url,
                "capture" if item.kind == "screenshot" else "source_image", item.description, item.image_url)
            self.add_visual(research, sources[item.source_url], asset, item.kind, item.image_url)
        current = self.active(job)
        known_urls = list(dict.fromkeys(current.brief.source_urls + urls))[:50]
        if known_urls != current.brief.source_urls:
            self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                                brief=current.brief.model_copy(update={"source_urls": known_urls}))
        self.service.write_json(self.active(job), "material-skill-manifest.json", bundle.model_dump(), "material_skill_manifest")
        self.service.write_json(self.active(job), "research.json", research, "research")
        return research

    def attach_image(self, job: Job, path: Path, source_url: str, origin: str, description: str,
                     image_url: str = "") -> Asset:
        mime, extension = detect_media(path.read_bytes())
        info = probe(path)
        stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "video"), None)
        if not mime.startswith("image/") or not stream or stream.get("width", 0) < 32 or stream.get("height", 0) < 32 or stream["width"] * stream["height"] > 40_000_000:
            raise ValueError("采集图片无法解码、过小或分辨率超过限制")
        current = self.active(job)
        digest = sha256(path)
        existing = next((item for item in current.assets if item.role != "audio" and item.source_url == source_url and item.sha256 == digest), None)
        if existing:
            return existing
        artifact = self.service.register_artifact(current, path, "asset", mime)
        asset_id = uuid.uuid4().hex
        asset = Asset(asset_id=asset_id, name=(description or path.name)[:200], role="evidence", mime_type=mime,
            size_bytes=artifact.size_bytes, sha256=artifact.sha256, source_url=source_url,
            license_note="真实网页截图/来源图片；尚未确认再利用许可，请在发布审核时核验",
            artifact_id=artifact.artifact_id, url=artifact.url,
            timeline_src=f"videoagents/{job.job_id}/assets/{asset_id}{extension}")
        self.service.freeze_asset(asset)
        self.repo.update_asset_metadata(asset_id, {"origin": origin, "source_url": source_url,
            "image_url": image_url, "description": description[:1000], "width": stream["width"],
            "height": stream["height"], "collection_key": fingerprint({"url": source_url, "origin": origin, "hash": digest})})
        current = self.active(job)
        self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                             assets=current.assets + [asset], artifacts=current.artifacts + [artifact])
        return asset

    @staticmethod
    def add_visual(research: dict, source: dict, asset: Asset, kind: str, image_url: str) -> None:
        source["asset_ids"].append(asset.asset_id)
        research["visuals"].append({"asset_id": asset.asset_id, "kind": kind, "source_url": source["url"],
            "image_url": image_url, "title": source["title"], "description": asset.name,
            "knowledge_excerpt": source.get("text", "")[:1000], "license_status": "needs_review"})
