import io
import json
import math
import struct
import wave
from pathlib import Path

import pytest

from videoagents.contracts import (
    Alignment,
    AlignmentSegment,
    Brief,
    DirectorRequirements,
    Job,
    Script,
    ScriptSegment,
    Shot,
    ShotLayer,
    Timeline,
)
from videoagents.nodes.director import _performance_payload, _validate_director_plan_payload
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.services.jobs import JobService
from videoagents.storage import Conflict, Repository
from videoagents.tools import components
from videoagents.tools.components import (
    component_requirement_usage,
    prompt_native_component_requirements,
    validate_component_requirements,
)


def write_native_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "native-component-capabilities.json"
    path.write_text(json.dumps({"schema_version": "1", "entries": entries}, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def clear_native_cache(monkeypatch, tmp_path):
    path = write_native_manifest(tmp_path, [
        {"component_id": "Snapcn-PhoneFrame", "roles": ["main"], "source": "phone.tsx", "renderer": "PhoneFrameMaterial", "use_case": "真实手机截图", "content_constraints": {"media_required": True, "image_only": True}},
        {"component_id": "RenderComp-KpiCounter", "roles": ["main"], "source": "kpi.tsx", "renderer": "CuratedScene:kpi-counter", "use_case": "真实指标", "content_constraints": {"metric_required": True}},
        {"component_id": "Snapcn-TextReveal", "roles": ["title", "emphasis"], "source": "text.tsx", "renderer": "SnapcnNativeTitle:TextReveal", "use_case": "标题揭示", "content_constraints": {"body_required": True}},
        {"component_id": "Snapcn-SearchTyping", "roles": ["title"], "source": "search.tsx", "renderer": "SnapcnNativeTitle:SearchTyping", "use_case": "搜索问题", "content_constraints": {"items_min": 1, "numeric_first_item": True}},
        {"component_id": "Snapcn-TextSwap", "roles": ["title"], "source": "swap.tsx", "renderer": "SnapcnNativeTitle:TextSwap", "use_case": "替换文字", "content_constraints": {"replacement_required": True, "items_distinct": True}},
        {"component_id": "Snapcn-TextHighlight", "roles": ["main", "title"], "source": "highlight.tsx", "renderer": "SnapcnNativeTitle:TextHighlight", "use_case": "关键词强调", "content_constraints": {"keyword_required": True, "min_visible_frames": 45}},
        {"component_id": "Rve-QuoteCard", "roles": ["main"], "source": "quote.tsx", "renderer": "NativeMediaScene:QuoteCard", "use_case": "纯文字引用卡", "content_constraints": {"items_min": 1, "asset_forbidden": True}},
    ])
    monkeypatch.setattr(components, "NATIVE_COMPONENT_CAPABILITIES_PATH", path)
    components.native_component_capabilities.cache_clear()
    yield
    components.native_component_capabilities.cache_clear()


def timeline_with_native_usage() -> Timeline:
    return Timeline(
        job_id="job-components",
        revision=1,
        width=1080,
        height=1920,
        fps=30,
        duration_in_frames=120,
        audio_src="audio.wav",
        captions=[],
        shots=[
            Shot(
                shot_id="s1",
                start_frame=0,
                end_frame=60,
                component_id="Snapcn-PhoneFrame",
                title="真实界面",
                body="展示当前素材",
                asset_src="videoagents/job-components/assets/app.png",
                layers=[
                    ShotLayer(
                        component_id="Snapcn-TextReveal",
                        role="title",
                        start_frame=0,
                        end_frame=30,
                        title="可能是 AI",
                        body="旁白里的风险点",
                    ),
                    ShotLayer(
                        component_id="Snapcn-SearchTyping",
                        role="emphasis",
                        start_frame=30,
                        end_frame=60,
                        title="不支持 emphasis",
                    ),
                ],
            ),
            Shot(
                shot_id="s2",
                start_frame=60,
                end_frame=120,
                component_id="title",
                title="基础组件",
                body="adapter 不计数",
                layers=[],
            ),
        ],
    )


def test_component_quota_counts_only_native_main_and_supported_layers():
    usage = component_requirement_usage(timeline_with_native_usage(), "personal", required=2)
    assert usage["library_count"] == 2
    assert usage["library_ids"] == ["Snapcn-PhoneFrame", "Snapcn-TextReveal"]
    assert usage["main_count"] == 1
    assert usage["layer_count"] == 1
    assert usage["native_manifest_fingerprint"]
    assert validate_component_requirements(timeline_with_native_usage(), "personal", 2) == usage
    with pytest.raises(ValueError, match="至少 3 个"):
        validate_component_requirements(timeline_with_native_usage(), "personal", 3)


def test_missing_native_manifest_blocks_positive_quota(monkeypatch, tmp_path):
    monkeypatch.setattr(components, "NATIVE_COMPONENT_CAPABILITIES_PATH", tmp_path / "missing.json")
    components.native_component_capabilities.cache_clear()
    with pytest.raises(ValueError, match="缺少原生组件能力清单"):
        validate_component_requirements(timeline_with_native_usage(), "personal", 1)
    assert component_requirement_usage(timeline_with_native_usage(), "personal", 0)["library_count"] == 0


def test_content_constraints_block_silent_null_native_usage():
    missing_metric = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=60, audio_src=None, captions=[],
        shots=[Shot(shot_id="s1", start_frame=0, end_frame=60, component_id="RenderComp-KpiCounter",
                    title="指标", body="真实指标")],
    )
    # Legacy no-quota, no-layer timelines remain readable; the main-content restriction is only required as quota proof.
    assert validate_component_requirements(missing_metric, "personal", 0)["library_count"] == 1
    with pytest.raises(ValueError, match="props.metric"):
        validate_component_requirements(missing_metric, "personal", 1)

    bad_layer = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=60, audio_src=None, captions=[],
        shots=[Shot(
            shot_id="s1", start_frame=0, end_frame=60, component_id="title", title="基础", body="",
            layers=[ShotLayer(component_id="Snapcn-SearchTyping", role="title", start_frame=0, end_frame=30,
                              title="怎么识别", props={"items": ["普通提示"]})],
        )],
    )
    with pytest.raises(ValueError, match="真实数字"):
        validate_component_requirements(bad_layer, "personal", 0)

    good_layer = Timeline.model_validate({
        **bad_layer.model_dump(),
        "shots": [{**bad_layer.shots[0].model_dump(), "layers": [
            {**bad_layer.shots[0].layers[0].model_dump(), "props": {"items": ["3 个信号"]}}
        ]}],
    })
    assert validate_component_requirements(good_layer, "personal", 0)["layer_count"] == 1

    duplicate_replacement = Timeline.model_validate({
        **good_layer.model_dump(),
        "shots": [{**good_layer.shots[0].model_dump(), "layers": [
            {
                "component_id": "Snapcn-TextSwap", "role": "title", "start_frame": 0, "end_frame": 30,
                "title": "替换", "props": {"from_text": "AI", "to_text": "AI", "items": ["AI", "AI"]},
            }
        ]}],
    })
    with pytest.raises(ValueError, match="from_text/to_text"):
        validate_component_requirements(duplicate_replacement, "personal", 0)

    distinct_replacement = Timeline.model_validate({
        **duplicate_replacement.model_dump(),
        "shots": [{**duplicate_replacement.shots[0].model_dump(), "layers": [
            {**duplicate_replacement.shots[0].layers[0].model_dump(),
             "props": {"from_text": "真人", "to_text": "AI", "items": ["真人", "AI"]}}
        ]}],
    })
    assert "Snapcn-TextSwap" in validate_component_requirements(distinct_replacement, "personal", 0)["library_ids"]

    missing_keyword_layer = Timeline.model_validate({
        **good_layer.model_dump(),
        "shots": [{**good_layer.shots[0].model_dump(), "layers": [
            {
                "component_id": "Snapcn-TextHighlight", "role": "title", "start_frame": 0, "end_frame": 45,
                "title": "关键词", "props": {},
            }
        ]}],
    })
    with pytest.raises(ValueError, match="props.highlight"):
        validate_component_requirements(missing_keyword_layer, "personal", 0)

    keyword_layer = Timeline.model_validate({
        **missing_keyword_layer.model_dump(),
        "shots": [{**missing_keyword_layer.shots[0].model_dump(), "layers": [
            {**missing_keyword_layer.shots[0].layers[0].model_dump(), "props": {"highlight": "AI"}}
        ]}],
    })
    assert "Snapcn-TextHighlight" in validate_component_requirements(keyword_layer, "personal", 0)["library_ids"]

    keyword_main = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=60, audio_src=None, captions=[],
        shots=[Shot(shot_id="s1", start_frame=0, end_frame=60, component_id="Snapcn-TextHighlight",
                    title="主镜头", body="关键词", props={"items": ["AI"]})],
    )
    assert validate_component_requirements(keyword_main, "personal", 1)["main_count"] == 1


def test_prompt_explains_entries_layers_and_no_empty_text_quota():
    guide = prompt_native_component_requirements("personal")
    assert "entries" in guide
    assert "layers 字段形状" in guide
    assert "不能为了凑数量填空泛文案" in guide
    assert "Snapcn-PhoneFrame" in guide and "roles=main" in guide
    assert "Snapcn-TextReveal" in guide and "roles=emphasis,title" in guide


def test_min_visible_frames_duration_constraint_omits_and_rejects_short_native_usage():
    short_main = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=60, audio_src=None, captions=[],
        shots=[
            Shot(shot_id="s1", start_frame=0, end_frame=44, component_id="Snapcn-TextHighlight",
                 title="主镜头", body="关键词", props={"items": ["AI"]}),
            Shot(shot_id="s2", start_frame=44, end_frame=60, component_id="title", title="补齐", body=""),
        ],
    )
    assert validate_component_requirements(short_main, "personal", 0)["main_count"] == 1
    assert component_requirement_usage(short_main, "personal", 1)["main_count"] == 0
    with pytest.raises(ValueError, match="可见 44 帧，要求至少 45 帧"):
        validate_component_requirements(short_main, "personal", 1)

    boundary_main = Timeline.model_validate({
        **short_main.model_dump(),
        "duration_in_frames": 61,
        "shots": [
            {**short_main.shots[0].model_dump(), "end_frame": 45},
            {**short_main.shots[1].model_dump(), "start_frame": 45, "end_frame": 61},
        ],
    })
    assert validate_component_requirements(boundary_main, "personal", 1)["main_count"] == 1

    short_layer = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=90, audio_src=None, captions=[],
        shots=[Shot(
            shot_id="s1", start_frame=0, end_frame=90, component_id="title", title="基础", body="",
            layers=[ShotLayer(component_id="Snapcn-TextHighlight", role="title", start_frame=0, end_frame=44,
                              title="关键词", props={"highlight": "AI"})],
        )],
    )
    assert component_requirement_usage(short_layer, "personal", 0)["layer_count"] == 0
    with pytest.raises(ValueError, match="可见 44 帧，要求至少 45 帧"):
        validate_component_requirements(short_layer, "personal", 0)

    boundary_layer = Timeline.model_validate({
        **short_layer.model_dump(),
        "shots": [{**short_layer.shots[0].model_dump(), "layers": [
            {**short_layer.shots[0].layers[0].model_dump(), "end_frame": 45}
        ]}],
    })
    assert validate_component_requirements(boundary_layer, "personal", 0)["layer_count"] == 1


def test_asset_forbidden_blocks_fake_media_on_required_native_main():
    fake_media_quote = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=60, audio_src=None, captions=[],
        shots=[Shot(shot_id="s1", start_frame=0, end_frame=60, component_id="Rve-QuoteCard",
                    title="引用", body="解释", asset_src="videoagents/job-components/assets/evidence.png",
                    props={"items": ["真实引用"]})],
    )
    assert validate_component_requirements(fake_media_quote, "personal", 0)["main_count"] == 1
    with pytest.raises(ValueError, match="不允许 asset_src"):
        validate_component_requirements(fake_media_quote, "personal", 1)

    pure_quote = Timeline.model_validate({
        **fake_media_quote.model_dump(),
        "shots": [{**fake_media_quote.shots[0].model_dump(), "asset_src": None}],
    })
    assert validate_component_requirements(pure_quote, "personal", 1)["main_count"] == 1


def test_chip_grid_cannot_count_before_its_selection_and_explanation_finish(monkeypatch):
    monkeypatch.setattr(components, "NATIVE_COMPONENT_CAPABILITIES_PATH",
                        Path(__file__).resolve().parents[2] / "videoagents" / "native-component-capabilities.json")
    components.native_component_capabilities.cache_clear()
    timeline = Timeline(
        job_id="job-components", revision=1, width=1080, height=1920, fps=30,
        duration_in_frames=180, audio_src=None, captions=[],
        shots=[Shot(shot_id="s1", start_frame=0, end_frame=180, component_id="title",
                    title="先停下来", body="", layers=[ShotLayer(
                        component_id="Talkcraft-chip-grid-single-select", role="emphasis",
                        start_frame=0, end_frame=33, title="先停下来",
                        props={"items": ["持续充值", "送礼刷亲密度", "先停下来"]},
                    )])],
    )
    assert component_requirement_usage(timeline, "personal", 1)["library_count"] == 0
    with pytest.raises(ValueError, match="要求至少 150 帧"):
        validate_component_requirements(timeline, "personal", 1)
    timeline.shots[0].layers[0].end_frame = 150
    assert validate_component_requirements(timeline, "personal", 1)["library_count"] == 1
    timeline.shots[0].layers[0].title = "充值"
    with pytest.raises(ValueError, match="精确匹配唯一选项"):
        validate_component_requirements(timeline, "personal", 1)
    timeline.shots[0].layers[0].props["highlight"] = "先停下来"
    assert validate_component_requirements(timeline, "personal", 1)["library_count"] == 1
    timeline.shots[0].layers[0].props["items"] = ["先停下来", "先停下来！"]
    with pytest.raises(ValueError, match="精确匹配唯一选项"):
        validate_component_requirements(timeline, "personal", 1)


def test_director_plan_payload_records_and_revalidates_component_usage():
    timeline = timeline_with_native_usage()
    job = Job(
        job_id=timeline.job_id,
        revision=1,
        status="DRAFT",
        stage="director",
        message="unit",
        created_at="2026-10-10T00:00:00Z",
        updated_at="2026-10-10T00:00:00Z",
        brief=Brief(topic="组件约束", script_text="讲清组件约束。", usage="personal", width=1080, height=1920, fps=30),
        director_requirements=DirectorRequirements(min_library_components=2),
        script=Script(title="组件约束", revision=1, segments=[ScriptSegment(segment_id="seg-1", narration="讲清组件约束。")]),
        timeline=timeline,
    )
    alignment = Alignment(origin="manual", verified=True, audio_sha256="a" * 64, segments=[AlignmentSegment(segment_id="seg-1", text="讲清组件约束。", start_ms=0, end_ms=3000)])
    payload = _performance_payload("unit", job, timeline, alignment)
    assert payload["component_usage"]["library_ids"] == ["Snapcn-PhoneFrame", "Snapcn-TextReveal"]
    _validate_director_plan_payload(payload, job, timeline, alignment)
    broken = {**payload, "component_usage": {**payload["component_usage"], "library_count": 99}}
    with pytest.raises(ValueError, match="库组件使用统计不匹配"):
        _validate_director_plan_payload(broken, job, timeline, alignment)


def _tone(seconds=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(i / 10))) for i in range(int(seconds * 16000))))
    return output.getvalue()


def _job_with_director_review_subject(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="gate", script_text="Keep script.", usage="personal", width=1080, height=1920, fps=30))
    script = Script(title="Keep script", revision=job.revision, origin="user",
                    segments=[ScriptSegment(segment_id="seg-1", narration="Keep script.")])
    job = repo.update_job(job.job_id, job.revision, script=script)
    audio = service.upload(job.job_id, _tone(), "unit.wav", "audio", license_note="UNIT", alignment={
        "origin": "manual", "verified": True, "audio_sha256": "",
        "segments": [{"segment_id": "seg-1", "text": "Keep script.", "start_ms": 0, "end_ms": 1000}],
    })
    job = repo.get_job(job.job_id)
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])
    timeline = Timeline(
        job_id=job.job_id, revision=job.revision, width=1080, height=1920, fps=30, duration_in_frames=30,
        audio_src=audio.timeline_src, shots=[Shot(shot_id="s1", start_frame=0, end_frame=30, component_id="title", title="Keep", body="Script")],
        captions=[{"text": "Keep script.", "start_ms": 0, "end_ms": 1000}],
    )
    job = repo.update_job(job.job_id, job.revision, timeline=timeline)
    plan = _performance_payload("unit", job, timeline, alignment)
    plan_artifact = service.write_json(job, "director-plan.json", plan, "director_plan")
    job = repo.get_job(job.job_id)
    preview = service.write_json(job, "director-demo.json", {"preview": True}, "preview")
    from videoagents.nodes.reviewers import dependency_fingerprint
    repo.update_artifact_metadata(preview.artifact_id, {
        "director_plan_sha256": plan_artifact.sha256,
        "dependency_fingerprint": dependency_fingerprint(job),
        "frame_range": [plan["demo"]["start_frame"], plan["demo"]["end_frame"]],
    })
    return repo, repo.get_job(job.job_id), audio


def test_director_requirements_persist_only_through_real_director_revise_gate(tmp_path, monkeypatch):
    repo, job, audio = _job_with_director_review_subject(tmp_path)
    original_revision = job.revision
    original_script = job.script
    original_audio = (audio.asset_id, audio.sha256)
    original_alignment = repo.asset_metadata(audio.asset_id)["alignment"]

    def answer_confirm_with_requirements(pending):
        return {
            "decision": "confirm", "note": "UNIT：确认但错误携带导演要求。",
            "pending_token": pending["pending_token"],
            "director_requirements": {"min_library_components": 60},
        }

    monkeypatch.setattr("videoagents.nodes.human_review.interrupt", answer_confirm_with_requirements)
    state = {"job_id": job.job_id, "revision": job.revision, "route": "director_human_gate", "thread_id": "UNIT-director-gate"}
    with pytest.raises(Conflict, match="只能随导演 Demo 返工提交"):
        HumanReviewNode(repo, node_name="director_human_gate", stage="director", revise_route="director")(state)
    assert repo.get_job(job.job_id).director_requirements is None

    def answer_revise_with_requirements(pending):
        return {
            "decision": "revise", "note": "UNIT：请至少使用60个不同原生库组件。",
            "pending_token": pending["pending_token"],
            "director_requirements": {"min_library_components": 60},
        }

    monkeypatch.setattr("videoagents.nodes.human_review.interrupt", answer_revise_with_requirements)
    result = HumanReviewNode(repo, node_name="director_human_gate", stage="director", revise_route="director")(state)
    current = repo.get_job(job.job_id)
    assert result["route"] == "revise"
    assert current.director_requirements.min_library_components == 60
    assert current.revision == original_revision
    assert current.script == original_script
    assert (next(asset for asset in current.assets if asset.role == "audio").asset_id,
            next(asset for asset in current.assets if asset.role == "audio").sha256) == original_audio
    assert repo.asset_metadata(audio.asset_id)["alignment"] == original_alignment
