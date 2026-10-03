"""第一个业务节点：采集知识与真实视觉素材，交接冻结的研究包。"""

import json
import uuid
from pathlib import Path
from typing import Any

from videoagents.contracts import Asset, Job, MaterialPlan
from videoagents.nodes.common import request_input, start_stage, state_context
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.providers.network import safe_get
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint, now
from videoagents.tools.media import detect_media, probe, sha256
from videoagents.tools.research import discover
from videoagents.tools.sources import capture_source, fetch_source
from worker.process_manager import RenderCancelled


class MaterialsNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "materials", "素材节点正在跨平台检索知识并采集图片与截图")
        try:
            research = self.collect(job)
            if not research["sources"] and not job.script and not job.brief.script_text.strip():
                raise CapabilityMissing("没有读取到可用来源；请配置搜索工具或补充主题对应的来源链接/真实素材", ["search", "source_urls", "assets"])
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

    def plan(self, job: Job) -> dict:
        frozen = self.saved_json(job, "material_plan")
        if frozen is not None:
            return frozen
        query = " ".join(job.brief.topic.split())[:2000]
        plan = {"query": query, "focus_notes": [], "ambiguities": []}
        if query and self.model.available("materials"):
            plan = MaterialPlan.model_validate(self.model.call(job.job_id, job.revision, "materials",
                "为短视频规划一个跨平台检索词及研究重点。涉及 Muse 等多义名称时记录歧义，"
                "检索词保留原主题且不擅自认定某一种含义。尚未检索，不能编造事实、URL、图片或结论。"
                "只返回 query、focus_notes、ambiguities。",
                {"brief": job.brief.model_dump()}, output_schema=MaterialPlan.model_json_schema())).model_dump()
        self.service.write_json(self.active(job), "material-plan.json", plan, "material_plan")
        return plan

    def collect(self, job: Job) -> dict:
        job = self.active(job)
        frozen = self.saved_json(job, "research")
        # 兼容旧编剧研究包；失败的未完成包允许修正配置后重试采集。
        if frozen is not None and frozen.get("status", "COMPLETED") == "COMPLETED":
            return frozen
        settings = SettingsService(self.repo).internal()
        plan = self.plan(job)
        research = {"schema_version": "2", "status": "COLLECTING", "query": plan["query"], "plan": plan,
                    "sources": [], "search_results": [], "tools": [], "visuals": [], "failures": [],
                    "capture_notes": [], "collected_at": now(), "policy": {
                        name: settings[name] for name in ("research_platforms", "research_results_per_platform",
                        "research_max_searches", "research_max_sources", "research_max_visuals",
                        "capture_enabled", "research_download_images")}}
        urls = list(job.brief.source_urls)
        if job.script:
            urls += [url for segment in job.script.segments for url in segment.source_refs]
        discovered = self.saved_json(job, "material_discovery")
        # 人工链接/已有稿件优先；只有主题创作自动扩展搜索。
        if not (discovered and discovered.get("results")) and plan["query"] and not urls and not job.script and not job.brief.script_text.strip():
            discovered = discover(self.repo, plan["query"], settings["research_platforms"],
                job_id=job.job_id, revision=job.revision, per_platform=settings["research_results_per_platform"],
                max_searches=settings["research_max_searches"])
            # 冻结搜索命中，使读取页面中途崩溃也无需重新启动原生平台工具。
            self.service.write_json(self.active(job), "material-discovery.json", discovered, "material_discovery")
        if discovered:
            research["search_results"] = discovered.get("results", [])
            research["tools"] = discovered.get("tools", [])
            urls += [item["url"] for item in research["search_results"]]
        results = {item["url"]: item for item in research["search_results"]}
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "sources"
        folder.mkdir(parents=True, exist_ok=True)
        visual_attempts = 0
        for index, url in enumerate(list(dict.fromkeys(urls))[:settings["research_max_sources"]]):
            self.active(job)
            hint = results.get(url, {})
            try:
                receipt = self.source(job, url, folder, index)
                receipt.update(title=receipt.get("title") or hint.get("title", ""),
                    platform=hint.get("platform", "manual"), backend=hint.get("backend", "source_url"),
                    knowledge_status="page_fetched", asset_ids=[])
                research["sources"].append(receipt)
            except (Conflict, RenderCancelled):
                raise
            except Exception as exc:
                research["failures"].append({"url": url, "reason": type(exc).__name__, "stage": "read"})
                continue
            existing = [asset for asset in self.active(job).assets if asset.role != "audio" and asset.source_url == url]
            for asset in existing:
                self.add_visual(research, receipt, asset, "existing", "")
            if existing:
                continue
            if settings["capture_enabled"] and visual_attempts < settings["research_max_visuals"]:
                visual_attempts += 1
                screenshot = folder / f"capture-{index}-{uuid.uuid4().hex[:12]}.png"
                try:
                    capture_source(url, screenshot)
                    asset = self.attach_image(job, screenshot, url, "capture", receipt["title"])
                    self.add_visual(research, receipt, asset, "screenshot", "")
                except (Conflict, RenderCancelled):
                    raise
                except Exception as exc:
                    research["capture_notes"].append({"url": url, "reason": type(exc).__name__})
            if settings["research_download_images"]:
                seen_images = set()
                for candidate in receipt.get("images", []) + hint.get("images", []):
                    image_url = candidate.get("url", "")
                    if not image_url or image_url in seen_images or visual_attempts >= settings["research_max_visuals"]:
                        continue
                    seen_images.add(image_url)
                    if candidate.get("source_url", url) != url:
                        continue
                    visual_attempts += 1
                    try:
                        data, _, final_url = safe_get(image_url, max_bytes=10 * 1024 * 1024)
                        mime, extension = detect_media(data)
                        if not mime.startswith("image/"):
                            raise ValueError("搜索图片实际内容不是图片")
                        image = folder / f"image-{index}-{uuid.uuid4().hex[:12]}{extension}"
                        image.write_bytes(data)
                        asset = self.attach_image(job, image, url, "source_image", candidate.get("description", "") or receipt["title"], final_url)
                        self.add_visual(research, receipt, asset, "image", final_url)
                        break  # 每来源最多一张成功原图；失败后继续尝试剩余候选。
                    except (Conflict, RenderCancelled):
                        raise
                    except Exception as exc:
                        research["failures"].append({"url": image_url, "source_url": url,
                            "reason": type(exc).__name__, "stage": "image"})
        current = self.active(job)
        known_urls = list(dict.fromkeys(current.brief.source_urls + [source["url"] for source in research["sources"]]))[:50]
        if known_urls != current.brief.source_urls:
            current = self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                                          brief=current.brief.model_copy(update={"source_urls": known_urls}))
        research["status"] = "COMPLETED" if research["sources"] or job.script or job.brief.script_text.strip() else "NEEDS_INPUT"
        # 冻结早于编剧模型调用；重放不能通过刷新网页改变调用上下文。
        self.service.write_json(current, "research.json", research, "research")
        return research

    def source(self, job: Job, url: str, folder: Path, index: int) -> dict:
        for artifact in self.active(job).artifacts:
            if artifact.kind == "source" and artifact.revision == job.revision:
                metadata = self.repo.artifact_metadata(artifact.artifact_id)
                if metadata.get("source_url") == url and metadata.get("receipt"):
                    path, _, _ = self.repo.artifact_path(artifact.artifact_id)
                    if sha256(path) != artifact.sha256:
                        raise Conflict("来源文件已改变")
                    return dict(metadata["receipt"])
        path = folder / f"source-{index}-{uuid.uuid4().hex[:12]}.html"
        receipt = fetch_source(url, path)
        artifact = self.service.register_artifact(self.active(job), path, "source", "text/plain", f"source-{index}.html.txt")
        receipt.update(artifact_id=artifact.artifact_id, artifact_url=artifact.url)
        self.repo.update_artifact_metadata(artifact.artifact_id, {"source_url": url, "receipt": receipt})
        current = self.active(job)
        self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                             artifacts=current.artifacts + [artifact])
        return dict(receipt)

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
