"""用户旁白不能让第一个视频未经语义判断就被挂到每一段。"""

import pytest

from videoagents.contracts import Asset, Brief, Script, ScriptDiscussion, ScriptSegment
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
    assert "不是现成口播稿" in calls[0][3]
    assert script.segments[0].narration != direction


@pytest.mark.parametrize("applied", [False, True], ids=["human-rewrite", "final-machine-rewrite"])
def test_rewrite_keeps_human_direction_after_feedback_is_applied(tmp_path, monkeypatch, applied):
    repository = Repository(tmp_path / "runtime")
    source = "https://example.com/report"
    job = repository.create_job(Brief(topic="报告解读", source_urls=[source]))
    asset = Asset(asset_id="chart", name="chart.png", role="evidence", mime_type="image/png",
                  size_bytes=100, sha256="a" * 64, source_url=source, artifact_id="chart-artifact",
                  url="/api/artifacts/chart-artifact", timeline_src="videoagents/unit/chart.png")
    original = Script(title="旧稿", origin="model", revision=job.revision,
                      segments=[ScriptSegment(segment_id="s1", narration="报告主要统计了付费情况。",
                                              source_refs=[source], asset_ids=[asset.asset_id])])
    job = repository.update_job(job.job_id, script=original, assets=[asset])
    discussion = ScriptDiscussion(run_id="UNIT-rewrite", revision=job.revision,
                                  status="EXHAUSTED", max_rounds=1,
                                  rounds=[{"round": 1, "script": original.model_dump(), "critique": {
                                      "decision": "REVISE", "summary": "修正判断归属", "issues": [{
                                          "category": "fact", "concern": "趋势是本期判断。",
                                          "suggestion": "不要把本期判断归给报告作者。",
                                      }],
                                  }}])
    feedback = {"decision": "revise", "note": "用使用深度的差距作主题，保持三个观点。",
                "applied": applied, "pending_token": "UNIT-feedback", "script": original.model_dump()}
    state = {"job_id": job.job_id, "revision": job.revision, "run_id": "UNIT-rewrite",
             "brief": job.brief.model_dump(), "script": original.model_dump(),
             "assets": [asset.model_dump()], "research": {"sources": [{"url": source}]},
             "extras": {"human_feedback": {"script": feedback}}}
    captured = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        captured.append(context)
        value = original.model_dump()
        value["segments"][0]["narration"] = "付费样本中的使用方式存在差别。"
        return {"script": value, "response": "保留人工主题，修正机器指出的问题。"}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    ScreenwriterNode(repository, JobService(repository, tmp_path)).rewrite(job, discussion, state)
    assert captured[0]["extras"]["human_feedback"]["script"] == feedback
    assert captured[0]["script_discussion"]["rounds"][0]["critique"]["decision"] == "REVISE"
    assert state["extras"]["human_feedback"]["script"]["applied"] is applied


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
