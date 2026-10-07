"""用户旁白不能让第一个视频未经语义判断就被挂到每一段。"""

import pytest

from videoagents.contracts import Asset, Brief, Script, ScriptSegment
from videoagents.nodes.screenwriter import ScreenwriterNode, script_issues
from videoagents.services.jobs import JobService
from videoagents.storage import Repository


def test_creative_direction_is_model_input_not_finished_narration(tmp_path, monkeypatch):
    repository = Repository(tmp_path / "runtime")
    direction = "从住客找不到酒店入口的经历切入，解释路线选择。"
    source = "https://example.com/route"
    job = repository.create_job(Brief(creative_direction=direction, source_urls=[source]))
    state = {"brief": job.brief.model_dump(), "script": None, "assets": [],
             "research": {"sources": [{"url": source}], "visuals": []}}
    node = ScreenwriterNode(repository, JobService(repository, tmp_path))
    calls = []

    def write(context, role, instruction, *, fields, output_schema):
        calls.append((context, role, fields, instruction))
        return {"title": "从地铁站怎么找到酒店入口", "segments": [{
            "segment_id": "s1", "narration": "出站后先沿着有路牌的方向走。",
            "screen_text": "先看路牌", "source_refs": [source], "asset_ids": [],
        }]}

    monkeypatch.setattr(node.model, "invoke", write)
    script, _ = node.write_script(job, state=state)
    assert len(calls) == 1
    assert calls[0][0]["brief"]["creative_direction"] == direction
    assert calls[0][1:3] == ("screenwriter", ("brief", "research", "assets"))
    assert "不是已有口播稿" in calls[0][3]
    assert script.segments[0].narration != direction


def test_user_script_does_not_bind_first_video_to_every_paragraph(tmp_path):
    repository = Repository(tmp_path / "runtime")
    job = repository.create_job(Brief(topic="测试", script_text="第一段任务。\n第二段边界。"))
    asset = Asset(asset_id="test-video", name="unit.mp4", role="evidence", mime_type="video/mp4",
                  size_bytes=100, sha256="a" * 64, source_url="https://example.com/source",
                  artifact_id="unit-artifact", url="/api/artifacts/unit-artifact",
                  timeline_src=f"videoagents/{job.job_id}/assets/unit.mp4")
    state = {"brief": job.brief.model_dump(), "script": None, "assets": [asset.model_dump()],
             "research": {"sources": [{"url": asset.source_url}]}}
    script, _ = ScreenwriterNode(repository, JobService(repository, tmp_path)).write_script(job, state=state)
    assert len(script.segments) == 2
    assert all(segment.asset_ids == [] for segment in script.segments)


def test_natural_source_backed_ending_does_not_require_spoken_opinion_label(tmp_path):
    repository = Repository(tmp_path / "runtime")
    source = "https://example.com/source"
    job = repository.create_job(Brief(topic="测试", source_urls=[source]))
    evidence = Asset(asset_id="evidence", name="演示.mp4", role="evidence", mime_type="video/mp4",
                     size_bytes=100, sha256="a" * 64, source_url=source, artifact_id="artifact",
                     url="/api/artifacts/artifact", timeline_src=f"videoagents/{job.job_id}/assets/demo.mp4")
    script = Script(title="它能替你完成哪一步", origin="model", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="它可以先整理候选项，付款前仍要你确认。",
                                            source_refs=[source], asset_ids=[evidence.asset_id])])
    assert script_issues(job.model_copy(update={"script": script, "assets": [evidence]})) == []


def test_unsupported_ending_is_rejected_without_requesting_an_opinion_prefix(tmp_path):
    repository = Repository(tmp_path / "runtime")
    job = repository.create_job(Brief(topic="测试"))
    script = Script(title="测试", origin="model", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="所以每个人都应该购买它。")])
    issues = script_issues(job.model_copy(update={"script": script}))
    assert len(issues) == 1 and "真实来源" in issues[0]
    assert "观点：" not in issues[0] and "个人感受：" not in issues[0]


@pytest.mark.parametrize("label", ["观点：", "个人感受："])
def test_legacy_user_script_remains_readable_without_rewriting_it(tmp_path, label):
    repository = Repository(tmp_path / "runtime")
    job = repository.create_job(Brief(script_text=label + "我喜欢这个配色。"))
    script = Script(title="历史文案", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration=job.brief.script_text)])
    assert script_issues(job.model_copy(update={"script": script})) == []
