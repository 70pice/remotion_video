import json
import re
import uuid
from urllib.parse import urlparse

from videoagents.contracts import Job, Script, ScriptSegment
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.providers.search import search
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools.sources import capture_source, fetch_source


class Screenwriter:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def run(self, job: Job) -> tuple[Script, dict]:
        # The caller may be replaying the same pre-acquisition job snapshot.
        # Receipts written before a paid call are authoritative on every run.
        job = self.repo.get_job(job.job_id)
        frozen = next((artifact for artifact in reversed(job.artifacts) if artifact.kind == "research" and artifact.revision == job.revision), None)
        if job.script and frozen:
            return job.script, json.loads(self.repo.artifact_path(frozen.artifact_id)[0].read_text(encoding="utf-8"))
        research = json.loads(self.repo.artifact_path(frozen.artifact_id)[0].read_text(encoding="utf-8")) if frozen else {"sources": [], "failures": [], "capture_notes": []}
        urls = [source["url"] for source in research["sources"]] if frozen else list(job.brief.source_urls)
        if not frozen and not job.script and not job.brief.script_text.strip() and not urls:
            result = search(self.repo, job.brief.topic, job.job_id, job.revision)
            urls = [item["url"] for item in result.get("results", [])[:5] if item.get("url")]
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "sources"
        folder.mkdir(parents=True, exist_ok=True)
        settings = SettingsService(self.repo).internal()
        for index, url in enumerate(urls[:8] if not frozen else []):
            try:
                source_path = folder / f"source-{index}-{uuid.uuid4().hex[:12]}.html"
                receipt = fetch_source(url, source_path)
                source_artifact = self.service.register_artifact(job, source_path, "source", "text/plain", f"source-{index}.html.txt")
                current = self.repo.get_job(job.job_id)
                self.repo.update_job(job.job_id, job.revision, artifacts=current.artifacts + [source_artifact])
                receipt["artifact_id"], receipt["artifact_url"] = source_artifact.artifact_id, source_artifact.url
                research["sources"].append(receipt)
                if settings["capture_enabled"] and not any(asset.role == "evidence" and asset.source_url == url for asset in job.assets):
                    screenshot = folder / f"capture-{index}-{uuid.uuid4().hex[:12]}.png"
                    try:
                        capture_source(url, screenshot)
                        # Upload increments revision for human changes; worker collection must attach in-place.
                        self.attach_capture(job, screenshot, url)
                    except Exception as exc:
                        research["capture_notes"].append({"url": url, "reason": type(exc).__name__})
            except Exception as exc:
                research["failures"].append({"url": url, "reason": type(exc).__name__})
        current = self.repo.get_job(job.job_id)
        discovered = [source["url"] for source in research["sources"]]
        if discovered:
            current.brief.source_urls = list(dict.fromkeys(current.brief.source_urls + discovered))
            self.repo.update_job(job.job_id, job.revision, brief=current.brief)
        if not frozen:
            # Persist immutable research before any paid model request. A
            # timeout/reclaim reuses exactly these receipts and paths.
            self.service.write_json(current, "research.json", research, "research")
        if job.script:
            return job.script, research
        if job.brief.script_text.strip():
            chunks = [item.strip() for item in re.split(r"\n+", job.brief.script_text) if item.strip()]
            # This splits narrative paragraphs, never estimates speech timing.
            if len(chunks) == 1 and len(chunks[0]) > 72:
                chunks = [item.strip() for item in re.findall(r"[^。！？.!?]+[。！？.!?]?", chunks[0]) if item.strip()]
            evidence = [asset.asset_id for asset in current.assets if asset.role == "evidence"]
            available_urls = list(dict.fromkeys(urls + [asset.source_url for asset in current.assets if asset.source_url]))
            script = Script(title=(job.brief.topic or "用户提供文案")[:300], origin="user", revision=job.revision,
                            segments=[ScriptSegment(segment_id=f"s{index + 1}", narration=text, screen_text=text[:100],
                                                    source_refs=available_urls, asset_ids=evidence[:1]) for index, text in enumerate(chunks)])
        else:
            if not research["sources"]:
                raise CapabilityMissing("没有取得可读取的原始来源，请补充真实链接/证据素材", ["source_urls", "assets"])
            schema = Script.model_json_schema()
            value = self.model.call(job.job_id, job.revision, "screenwriter", "根据来源写口播，不编造数字或引用；每段有 source_refs 和素材 asset_ids，旁白宜每段 <=72字。返回 Script JSON。",
                                    {"brief": current.brief.model_dump(), "research": research, "assets": [asset.model_dump() for asset in current.assets]}, output_schema=schema)
            value.update(origin="model", revision=job.revision)
            script = Script.model_validate(value)
        return script, research

    def attach_capture(self, job, screenshot, url):
        import uuid

        from videoagents.contracts import Asset
        artifact = self.service.register_artifact(job, screenshot, "asset", "image/png")
        asset_id = uuid.uuid4().hex
        asset = Asset(asset_id=asset_id, name=screenshot.name, role="evidence", mime_type="image/png",
                      size_bytes=artifact.size_bytes, sha256=artifact.sha256, source_url=url,
                      license_note="网页截图；需人工确认该任务用途的引用与许可范围", artifact_id=artifact.artifact_id,
                      url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/{asset_id}.png")
        current = self.repo.get_job(job.job_id)
        self.repo.update_job(job.job_id, job.revision, assets=current.assets + [asset], artifacts=current.artifacts + [artifact])
        self.repo.update_asset_metadata(asset_id, {"origin": "capture", "source_url": url})
        self.service.freeze_asset(asset)


def script_issues(job: Job) -> list[str]:
    if not job.script:
        return ["没有有效短视频文案"]
    known_assets = {asset.asset_id: asset for asset in job.assets}
    known_sources = set(job.brief.source_urls) | {asset.source_url for asset in job.assets if asset.source_url}
    issues = []
    for segment in job.script.segments:
        if not segment.source_refs and not segment.narration.startswith(("观点：", "个人感受：")):
            issues.append(f"段落 {segment.segment_id} 缺少事实来源；纯观点请明确标注“观点：”")
        for source in segment.source_refs:
            parsed = urlparse(source)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                issues.append(f"段落 {segment.segment_id} 来源 URL 无效")
            elif source not in known_sources:
                issues.append(f"段落 {segment.segment_id} 来源不在用户来源或真实素材清单中")
        for asset_id in segment.asset_ids:
            if asset_id not in known_assets:
                issues.append(f"段落 {segment.segment_id} 素材不存在")
    facts = [segment for segment in job.script.segments if segment.source_refs]
    if facts and not any(asset.role == "evidence" and asset.source_url for asset in job.assets):
        issues.append("事实性文案需要至少一张带原始出处的真实证据图片/截图")
    return issues
