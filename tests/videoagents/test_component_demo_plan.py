import json
from pathlib import Path

import pytest

from videoagents.contracts import Asset, Brief, Timeline
from videoagents.nodes.component_demo import ComponentDemoNode
from videoagents.nodes.director import _validate_director_plan_payload
from videoagents.services.jobs import JobService
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline


def _job_with_asset(tmp_path, *, set_id="A01", video=False, metadata_duration=None, bad_owner=False, metadata_override=None):
    repo = Repository(tmp_path / f"runtime-{set_id}-{video}-{bad_owner}")
    service = JobService(repo, tmp_path / f"project-{set_id}-{video}-{bad_owner}")
    job = repo.create_job(Brief(topic="组件套样片", usage="personal", width=1080, height=1920, fps=30))
    asset_id = f"asset-{set_id.lower()}"
    ext = ".mp4" if video else ".png"
    owner = "other-job" if bad_owner else job.job_id
    timeline_src = f"videoagents/{owner}/assets/{asset_id}{ext}"
    public_file = service.project_root / "public" / timeline_src
    public_file.parent.mkdir(parents=True, exist_ok=True)
    public_file.write_bytes(b"unit-media")
    asset = Asset(
        asset_id=asset_id,
        name=f"{set_id}{ext}",
        role="evidence" if set_id in {"A03", "A05"} else "illustration",
        mime_type="video/mp4" if video else "image/png",
        size_bytes=10,
        sha256="a" * 64,
        source_url="https://example.test/generated-sample",
        license_note="UNIT generated sample",
        artifact_id=f"artifact-{asset_id}",
        url=f"/api/artifacts/artifact-{asset_id}",
        timeline_src=timeline_src,
    )
    job = repo.update_job(job.job_id, job.revision, assets=[asset])
    metadata = {"origin": "unit", "width": 1200, "height": 900}
    if video:
        metadata = {
            "origin": "unit",
            "duration_seconds": metadata_duration if metadata_duration is not None else 12.5,
            "width": 540,
            "height": 960,
        }
    if metadata_override:
        metadata.update(metadata_override)
    repo.update_asset_metadata(asset.asset_id, metadata)
    return repo, service, repo.get_job(job.job_id), asset


def _steps(frames=300):
    return [
        {"start_frame": 0, "end_frame": 90, "instruction": "输入提醒事项", "target": {"x": 0.12, "y": 0.28, "width": 0.76, "height": 0.12}},
        {"start_frame": 90, "end_frame": 180, "instruction": "点击保存提醒", "target": {"x": 0.18, "y": 0.64, "width": 0.64, "height": 0.10}},
        {"start_frame": 180, "end_frame": frames, "instruction": "列表出现结果", "target": {"x": 0.10, "y": 0.38, "width": 0.80, "height": 0.16}},
    ]


def _state(job, asset, set_id, duration_seconds=None, tutorial_steps=None, focus_steps=None, content=None, composition=None):
    request = {"set_id": set_id}
    if asset is not None:
        request["asset_id"] = asset.asset_id
    if duration_seconds is not None:
        request["duration_seconds"] = duration_seconds
    if tutorial_steps is not None:
        request["tutorial_steps"] = tutorial_steps
    if focus_steps is not None:
        request["focus_steps"] = focus_steps
    if content is not None:
        request["content"] = content
    if composition is not None:
        request["composition"] = composition
    return {
        "job_id": job.job_id,
        "revision": job.revision,
        "thread_id": f"unit-{set_id}",
        "run_id": f"run-{set_id}",
        "extras": {"component_demo": request},
    }


def _focus_steps(frames=300):
    return [
        {"start_frame": 0, "end_frame": 120, "instruction": "先看主体", "target": {"x": 0.10, "y": 0.20, "width": 0.80, "height": 0.18}},
        {"start_frame": 120, "end_frame": 210, "instruction": "再看动作", "target": {"x": 0.18, "y": 0.48, "width": 0.62, "height": 0.12}},
        {"start_frame": 210, "end_frame": frames, "instruction": "最后看结果", "target": {"x": 0.12, "y": 0.66, "width": 0.76, "height": 0.14}},
    ]


def _empty_job(tmp_path, *, set_id="B01"):
    repo = Repository(tmp_path / f"runtime-empty-{set_id}")
    service = JobService(repo, tmp_path / f"project-empty-{set_id}")
    job = repo.create_job(Brief(topic="无素材组件套样片", usage="personal", width=1080, height=1920, fps=30))
    return repo, service, job






def _expanded_content(set_id):
    path = Path("tests/fixtures/component-set-expanded-content.json")
    content = json.loads(path.read_text(encoding="utf-8"))
    return content[set_id]


def _material_rich_content(set_id):
    path = Path("tests/fixtures/component-set-material-rich-content.json")
    content = json.loads(path.read_text(encoding="utf-8"))
    return content[set_id]


def _a09_focus_steps():
    return [
        {"start_frame": 0, "end_frame": 115, "instruction": "输入事项", "target": {"x": 0.12, "y": 0.24, "width": 0.76, "height": 0.14}},
        {"start_frame": 115, "end_frame": 179, "instruction": "点保存", "target": {"x": 0.18, "y": 0.68, "width": 0.64, "height": 0.10}},
        {"start_frame": 179, "end_frame": 371, "instruction": "查看列表", "target": {"x": 0.10, "y": 0.38, "width": 0.80, "height": 0.18}},
    ]


MATERIAL_RICH_ACTUAL_COMPONENTS = {
    "A07": ["Talkcraft-slow-push-in", "Snapcn-TextReveal", "Snapcn-TextHighlight", "Rve-QuoteCard", "Rve-ProgressSteps", "Snapcn-WordFlip", "Talkcraft-source-converge"],
    "A08": ["Snapcn-PhoneFrame", "Snapcn-TextReveal", "Snapcn-TextHighlight", "Rve-ProgressSteps", "Rve-SplitScreen", "Snapcn-WordFlip", "Talkcraft-source-converge"],
    "A09": ["Snapcn-PhoneFrame", "Snapcn-TextReveal", "Snapcn-TextHighlight", "Rve-ProgressSteps", "Rve-StatCounter", "Snapcn-TextBuild", "Snapcn-TextSwap"],
    "A10": ["Talkcraft-scanline-annotate", "Snapcn-TextReveal", "Talkcraft-ink-underline", "Rve-ChartAnimation", "Rve-StatCounter", "Snapcn-TextBuild", "Rve-LineChart"],
    "A11": ["Talkcraft-tilt-3d-page", "Snapcn-TextReveal", "Snapcn-TextHighlight", "Rve-QuoteCard", "Snapcn-WordFlip", "Talkcraft-source-converge", "Talkcraft-ink-underline"],
    "A12": ["Talkcraft-slow-pull-reveal", "Snapcn-TextReveal", "Snapcn-TextHighlight", "Rve-SplitScreen", "Rve-ProgressSteps", "Talkcraft-source-converge", "Snapcn-WordFlip"],
}




EXPANDED_ACTUAL_COMPONENTS = {
    "B07": ["Rve-ChartAnimation", "Talkcraft-typewriter-reveal", "Snapcn-TextHighlight", "Rve-QuoteCard", "Rve-StatCounter", "Rve-ProgressSteps", "Snapcn-WordFlip"],
    "B08": ["Rve-StatCounter", "Snapcn-TextBuild", "Snapcn-TextHighlight", "Rve-ChartAnimation", "Snapcn-WordFlip", "Talkcraft-ink-underline"],
    "B09": ["Rve-ComparisonChart", "Snapcn-TextSwap", "Snapcn-TextHighlight", "Rve-SplitScreen", "Rve-StatCounter", "Talkcraft-strike-and-replace"],
    "B10": ["Rve-ChartAnimation", "Snapcn-TextBuild", "Snapcn-TextHighlight", "Rve-StatCounter", "Rve-LineChart", "Talkcraft-ink-underline"],
    "B11": ["Rve-ProgressSteps", "Snapcn-TextBuild", "Snapcn-AnswerHighlight", "Rve-SplitScreen", "Rve-StatCounter", "Talkcraft-word-slot-cycle"],
    "B12": ["Rve-QuoteCard", "Snapcn-WordFlip", "Snapcn-TextHighlight", "Talkcraft-source-converge", "Rve-StatCounter", "Rve-ProgressSteps"],
    "B13": ["Rve-SplitScreen", "Snapcn-TextRewrite", "Snapcn-TextHighlight", "Snapcn-TextSwap", "Rve-StatCounter", "Talkcraft-error-retype", "Rve-QuoteCard", "Talkcraft-strike-and-replace"],
    "B14": ["Snapcn-AnswerStream", "Snapcn-SearchTyping", "Snapcn-AnswerHighlight", "Bits-ChatConversation", "Snapcn-TextBuild", "Rve-StatCounter"],
    "B15": ["Rve-QuoteCard", "Talkcraft-title-demote-to-label", "Snapcn-TextHighlight", "Rve-ProgressSteps", "Rve-StatCounter", "Rve-ChartAnimation", "Snapcn-TextBuild"],
    "B16": ["Rve-ProgressSteps", "Talkcraft-title-demote-to-label", "Talkcraft-keyword-pop-highlight", "Rve-StatCounter", "Snapcn-WordFlip", "Rve-QuoteCard", "Snapcn-TextHighlight"],
    "B17": ["Bits-ChatConversation", "Talkcraft-line-by-line-slide", "Snapcn-AnswerHighlight", "Rve-ProgressSteps", "Rve-StatCounter", "Snapcn-TextBuild"],
    "B18": ["Rve-ComparisonChart", "Snapcn-TextSwap", "Snapcn-TextHighlight", "Rve-SplitScreen", "Rve-ProgressSteps", "Talkcraft-strike-and-replace"],
}


def _b_rich_content(set_id):
    values = {
        "B01": {"title": "先问谁在聊", "body": "三条线索一起看，别只听对方解释。", "takeaway": "先核实身份", "items": ["账号是谁", "谁在收费", "谁要视频"], "metric": {"label": "演示线索", "value": "3项", "detail": "演示数字"}},
        "B02": {"title": "拆开陪聊链", "body": "文字、收费、视频不是同一个环节。", "takeaway": "分清机器真人", "items": ["AI写文字", "真人接视频", "平台收费用"], "metric": {"label": "演示环节", "value": "3段", "detail": "演示数字"}},
        "B03": {"title": "两边一起看", "body": "同单位数字只做演示，帮助组件对齐。", "takeaway": "看清转折点", "items": ["AI文字陪聊", "真人视频接管"], "numeric_items": ["文字:8次", "视频:2次"]},
        "B04": {"title": "费用先拆开", "body": "总数必须来自三项累加，方便看出口径。", "takeaway": "数字要问口径", "metric": {"label": "演示合计", "value": "399元", "detail": "演示数字"}, "numeric_items": ["会员:199元", "礼物:100元", "视频:100元"]},
        "B05": {"title": "三步停一下", "body": "流程、数字和解释同时出现，提醒先别急。", "takeaway": "别急着转账", "items": ["确认身份", "停下付款", "找人复核"], "metric": {"label": "演示步骤", "value": "3步", "detail": "演示数字"}, "supporting_items": ["先截图", "问家人", "再决定"]},
        "B06": {"title": "给家人提醒", "body": "用模拟聊天承接结尾建议，数字只说明条目数。", "takeaway": "先停再核实", "items": ["不私下转账", "截图发家人"], "metric": {"label": "演示提醒", "value": "2条", "detail": "演示数字"}, "supporting_items": ["对方:先充会员", "我:等家人看完"]},
    }
    return values[set_id]


def _b_content(set_id):
    base = {
        "B01": {"title": "先问一个问题", "body": "这件事到底是谁在聊天，谁在收钱。", "takeaway": "先核实身份"},
        "B02": {"title": "什么是AI陪聊", "body": "AI负责多数文字互动，真人接住机器做不好的环节。", "takeaway": "分清机器和真人"},
        "B03": {"title": "两种风险不同", "body": "同样是聊天，风险来自不同节点。", "takeaway": "看清转折点", "items": ["AI文字陪聊", "真人视频接管"]},
        "B04": {"title": "先看代价", "body": "演示数字只用来测试计数器，不代表真实统计。", "takeaway": "数字要问口径", "metric": {"label": "演示等待", "value": "7天", "detail": "演示数字"}},
        "B05": {"title": "三步判断", "body": "先确认身份，再看收费动作，最后问家人。", "takeaway": "别急着转账", "items": ["确认对方身份", "停下充值动作", "找家人复核"]},
        "B06": {"title": "给家人的提醒", "body": "看到陌生陪聊和视频请求，先把流程停下来。", "takeaway": "先停再核实", "items": ["不私下转账", "截图发给家人", "必要时报警"]},
    }
    return base[set_id]


@pytest.mark.parametrize("set_id", ["A01", "A02", "A03", "A04", "A05", "A06"])
def test_component_demo_node_builds_valid_plan_for_all_sets(tmp_path, set_id):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id=set_id, video=set_id == "A03")

    result = ComponentDemoNode(repo, service)(_state(job, asset, set_id))

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    assert current.status == "RUNNING"
    assert current.stage == "director"
    assert current.timeline is not None
    assert current.timeline.width == 1080 and current.timeline.height == 1920 and current.timeline.fps == 30
    assert current.timeline.audio_src is None and current.timeline.captions == []
    assert len(current.timeline.shots) == 1
    shot = current.timeline.shots[0]
    assert shot.asset_src == asset.timeline_src
    assert "样片" in shot.source_label or "模拟" in shot.source_label
    if set_id == "A02":
        assert shot.component_id == "Snapcn-PhoneFrame"
        assert len(shot.layers) == 1
    if set_id == "A03":
        assert shot.component_id == "video"
        assert current.timeline.duration_in_frames == 360
        assert shot.props["end_seconds"] == 12
    if set_id == "A05":
        assert shot.component_id == "evidence"
        assert shot.props["highlight"] == {"x": 0.08, "y": 0.40, "width": 0.84, "height": 0.12}

    artifacts = [artifact for artifact in current.artifacts if artifact.kind == "director_plan"]
    assert len(artifacts) == 1
    plan_path, _, owner = repo.artifact_path(artifacts[0].artifact_id)
    assert owner == job.job_id
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["origin"] == "component_demo"
    assert plan["component_demo_recipe"]["set_id"] == set_id
    assert plan["component_demo_recipe"]["version"] == "component-demo-v2"
    assert plan["component_demo_recipe"]["silent_visual_sample"] is True
    assert "不代表真实证据" in plan["component_demo_recipe"]["purpose"]
    assert plan["demo"] == {"start_frame": 0, "end_frame": current.timeline.duration_in_frames, "reason": plan["demo"]["reason"]}
    assert plan["component_usage"]["library_count"] >= 2
    _validate_director_plan_payload(plan, current, current.timeline)


@pytest.mark.parametrize(("set_id", "component_id", "title_id", "emphasis_id"), [
    ("B01", "Rve-QuoteCard", "Snapcn-TextReveal", "Snapcn-TextHighlight"),
    ("B02", "keyword", "Snapcn-TextRewrite", "Snapcn-TextHighlight"),
    ("B03", "Rve-SplitScreen", "Snapcn-TextReveal", "Snapcn-TextHighlight"),
    ("B04", "Rve-StatCounter", "Snapcn-TextReveal", "Snapcn-TextHighlight"),
    ("B05", "Rve-ProgressSteps", "Snapcn-TextBuild", "Snapcn-TextHighlight"),
    ("B06", "conclusion", "Snapcn-TextReveal", "Snapcn-TextBuild"),
])
def test_component_demo_node_builds_no_material_b_sets(tmp_path, set_id, component_id, title_id, emphasis_id):
    repo, service, job = _empty_job(tmp_path, set_id=set_id)

    result = ComponentDemoNode(repo, service)(_state(job, None, set_id, duration_seconds=8, content=_b_content(set_id)))

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    shot = current.timeline.shots[0]
    assert shot.component_id == component_id
    assert shot.asset_src is None
    assert shot.props["component_set"] == set_id
    assert [layer.component_id for layer in shot.layers] == [title_id, emphasis_id]
    assert shot.layers[0].role == "title"
    assert shot.layers[1].role == "emphasis"
    assert current.timeline.audio_src is None and current.timeline.captions == []
    artifacts = [artifact for artifact in current.artifacts if artifact.kind == "director_plan"]
    plan_path, _, _ = repo.artifact_path(artifacts[0].artifact_id)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["component_demo_recipe"]["version"] == "component-demo-v3"
    assert plan["component_demo_recipe"]["asset_id"] is None
    assert plan["component_demo_recipe"]["content"] == _b_content(set_id)
    assert plan["component_demo_recipe"]["no_external_material"] is True
    assert plan["segment_performances"][0]["visual_action"]
    validate_timeline(current.timeline, current, {})
    _validate_director_plan_payload(plan, current, current.timeline)


def test_component_demo_node_rejects_asset_for_no_material_set(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="B01")

    result = ComponentDemoNode(repo, service)(_state(job, asset, "B01", content=_b_content("B01")))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "不接受 asset_id" in current.pending_input["issues"][0]


@pytest.mark.parametrize(("set_id", "content", "expected"), [
    ("B01", {**_b_content("B01"), "items": ["多余", "参数"]}, "只接受"),
    ("B03", {**_b_content("B03"), "items": ["第一项", "第二项", "第三项"]}, "exactly 2"),
    ("B04", {**_b_content("B04"), "metric": {"label": "比例", "value": "80%", "detail": "演示数字"}}, "整数加 1 到 2 个汉字单位"),
    ("B04", {**_b_content("B04"), "metric": {"label": "数字", "value": "３９９元", "detail": "演示数字"}}, "整数加 1 到 2 个汉字单位"),
    ("B05", {**_b_content("B05"), "items": ["一步", "两步"]}, "exactly 3"),
    ("B06", {**_b_content("B06"), "items": ["第一项", "第二项", "第三项", "第四项"]}, "2 到 3"),
])
def test_component_demo_node_rejects_invalid_b_content(tmp_path, set_id, content, expected):
    repo, service, job = _empty_job(tmp_path, set_id=set_id)

    result = ComponentDemoNode(repo, service)(_state(job, None, set_id, content=content))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert expected in current.pending_input["issues"][0]


def test_component_demo_rejects_asset_from_other_job_scope(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A01", bad_owner=True)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A01"))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT"
    assert current.pending_input["retry_node"] == "component_demo"
    assert "不属于此视频任务" in current.pending_input["issues"][0]


def test_component_demo_rejects_short_a03_video(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A03", video=True, metadata_duration=7)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A03"))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT"
    assert current.pending_input["retry_node"] == "component_demo"
    assert "时长不足" in current.pending_input["issues"][0]


def test_component_demo_builds_guided_a02_tutorial_from_video_steps(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A02", video=True)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A02", duration_seconds=10, tutorial_steps=_steps()))

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    shot = current.timeline.shots[0]
    assert shot.component_id == "Snapcn-PhoneFrame"
    assert shot.source_label == ""
    assert shot.props["content_mode"] == "media"
    assert shot.props["asset_fit"] == "contain"
    assert shot.props["start_seconds"] == 0
    assert shot.props["end_seconds"] == 10
    assert shot.props["tutorial_source_size"] == {"width": 540, "height": 960}
    assert shot.props["tutorial_steps"] == _steps()
    assert len(shot.layers) == 1
    layer = shot.layers[0]
    assert layer.component_id == "Snapcn-TextReveal"
    assert layer.start_frame == 0 and layer.end_frame == 300
    assert layer.title == "输入提醒事项"
    assert layer.body == ""
    assert layer.accent_color == "#FB923C"
    plan_artifact = next(artifact for artifact in current.artifacts if artifact.kind == "director_plan")
    plan_path, _, _ = repo.artifact_path(plan_artifact.artifact_id)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["component_demo_recipe"]["guided_tutorial"] is True
    assert "橙色手绘圈" in plan["segment_performances"][0]["visual_action"]
    _validate_director_plan_payload(plan, current, current.timeline)


@pytest.mark.parametrize(("set_id", "video", "component_id"), [
    ("A03", True, "video"),
    ("A04", False, "Talkcraft-tilt-3d-page"),
    ("A05", False, "evidence"),
    ("A06", False, "image_focus"),
])
def test_component_demo_builds_focus_steps_for_material_sets(tmp_path, set_id, video, component_id):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id=set_id, video=video)

    result = ComponentDemoNode(repo, service)(_state(job, asset, set_id, duration_seconds=10, focus_steps=_focus_steps()))

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    shot = current.timeline.shots[0]
    assert shot.component_id == component_id
    assert shot.source_label == ""
    assert shot.accent_color == "#FB923C"
    assert shot.props["focus_steps"] == _focus_steps()
    assert shot.props["focus_source_size"] == ({"width": 540, "height": 960} if video else {"width": 1200, "height": 900})
    assert "highlight" not in shot.props
    assert "crop" not in shot.props
    assert "focal_x" not in shot.props and "focal_y" not in shot.props
    if set_id == "A03":
        assert shot.props["fit"] == "contain"
        assert shot.props["start_seconds"] == 0
        assert shot.props["end_seconds"] == 10
    if set_id == "A04":
        assert shot.props["asset_fit"] == "contain"
    assert len(shot.layers) == 1
    layer = shot.layers[0]
    assert layer.component_id == "Snapcn-TextReveal"
    assert layer.start_frame == 0 and layer.end_frame == 300
    assert layer.title == "先看主体"
    assert layer.accent_color == "#FB923C"
    plan_artifact = next(artifact for artifact in current.artifacts if artifact.kind == "director_plan")
    plan_path, _, _ = repo.artifact_path(plan_artifact.artifact_id)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["component_demo_recipe"]["guided_focus"] is True
    assert plan["component_demo_recipe"]["focus_steps"] == _focus_steps()
    assert plan["segment_performances"][0]["visual_action"]
    _validate_director_plan_payload(plan, current, current.timeline)


def test_component_demo_rejects_guided_steps_for_non_a02(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A03", video=True)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A03", duration_seconds=10, tutorial_steps=_steps()))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "只允许用于 A02" in current.pending_input["issues"][0]


def test_component_demo_rejects_guided_a02_image_asset(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A02", video=False)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A02", duration_seconds=10, tutorial_steps=_steps()))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "MP4" in current.pending_input["issues"][0]


def test_component_demo_rejects_focus_steps_for_a02(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A02", video=True)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A02", duration_seconds=10, focus_steps=_focus_steps()))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "A03-A06" in current.pending_input["issues"][0]


@pytest.mark.parametrize("steps, expected", [
    (_steps()[:1] + [{"start_frame": 120, "end_frame": 300, "instruction": "列表出现结果", "target": {"x": 0.1, "y": 0.3, "width": 0.8, "height": 0.2}}], "连续"),
    ([{**_steps()[0], "target": {"x": 0.8, "y": 0.3, "width": 0.4, "height": 0.2}}, *_steps()[1:]], "画面内"),
])
def test_component_demo_rejects_invalid_guided_steps(tmp_path, steps, expected):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A02", video=True)

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A02", duration_seconds=10, tutorial_steps=steps))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert expected in current.pending_input["issues"][0]


def _valid_guided_timeline_payload(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A02", video=True)
    result = ComponentDemoNode(repo, service)(_state(job, asset, "A02", duration_seconds=10, tutorial_steps=_steps()))
    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    metadata = {item.asset_id: repo.asset_metadata(item.asset_id) for item in current.assets}
    return current, current.timeline.model_dump(mode="json"), metadata


@pytest.mark.parametrize("mutate, expected", [
    (lambda raw: raw["shots"][0].update({"asset_src": None}), "MP4 录屏素材"),
    (lambda raw: raw["shots"][0].update({"layers": []}), "全时长标题层"),
    (lambda raw: raw["shots"][0]["layers"][0].update({"title": "错误口令"}), "第一步口令"),
    (lambda raw: raw["shots"][0]["layers"][0].update({"start_frame": 1}), "全时长 Snapcn-TextReveal"),
])
def test_guided_a02_timeline_rejects_semantic_mismatches(tmp_path, mutate, expected):
    current, raw, metadata = _valid_guided_timeline_payload(tmp_path)
    mutate(raw)

    with pytest.raises(ValueError, match=expected):
        validate_timeline(Timeline.model_validate(raw), current, metadata)


def test_guided_a02_timeline_requires_portrait_timeline(tmp_path):
    current, raw, metadata = _valid_guided_timeline_payload(tmp_path)
    raw["width"] = 1920
    raw["height"] = 1080
    landscape = current.model_copy(update={"brief": current.brief.model_copy(update={"width": 1920, "height": 1080})})

    with pytest.raises(ValueError, match="竖屏时间轴"):
        validate_timeline(Timeline.model_validate(raw), landscape, metadata)


def test_guided_a02_timeline_requires_measured_video_duration(tmp_path):
    current, raw, _ = _valid_guided_timeline_payload(tmp_path)
    metadata_without_duration = {current.assets[0].asset_id: {"width": 540, "height": 960}}

    with pytest.raises(ValueError, match="实测时长"):
        validate_timeline(Timeline.model_validate(raw), current, metadata_without_duration)


def _valid_focus_timeline_payload(tmp_path, *, set_id="A06"):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id=set_id, video=set_id == "A03")
    result = ComponentDemoNode(repo, service)(_state(job, asset, set_id, duration_seconds=10, focus_steps=_focus_steps()))
    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    metadata = {item.asset_id: repo.asset_metadata(item.asset_id) for item in current.assets}
    return current, current.timeline.model_dump(mode="json"), metadata


@pytest.mark.parametrize("mutate, expected", [
    (lambda raw: raw["shots"][0]["props"].update({"crop": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}}), "不能裁剪"),
    (lambda raw: raw["shots"][0]["props"].update({"focal_x": 0.5}), "旧 highlight 或焦点参数"),
    (lambda raw: raw["shots"][0]["props"].update({"highlight": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.1}}), "旧 highlight 或焦点参数"),
    (lambda raw: raw["shots"][0]["layers"][0].update({"title": "错误口令"}), "第一步口令"),
])
def test_focus_timeline_rejects_semantic_mismatches(tmp_path, mutate, expected):
    current, raw, metadata = _valid_focus_timeline_payload(tmp_path, set_id="A06")
    mutate(raw)

    with pytest.raises(ValueError, match=expected):
        validate_timeline(Timeline.model_validate(raw), current, metadata)


def test_focus_timeline_requires_asset_metadata_size_match(tmp_path):
    current, raw, metadata = _valid_focus_timeline_payload(tmp_path, set_id="A05")
    metadata[current.assets[0].asset_id]["width"] = 999

    with pytest.raises(ValueError, match="尺寸必须来自当前素材元数据"):
        validate_timeline(Timeline.model_validate(raw), current, metadata)


def test_focus_timeline_is_limited_to_component_samples(tmp_path):
    current, raw, metadata = _valid_focus_timeline_payload(tmp_path, set_id="A04")
    raw["presentation"] = "production"

    with pytest.raises(ValueError, match="组件样片时间轴"):
        validate_timeline(Timeline.model_validate(raw), current, metadata)


def _valid_b_timeline_payload(tmp_path, *, set_id="B03"):
    repo, service, job = _empty_job(tmp_path, set_id=set_id)
    result = ComponentDemoNode(repo, service)(_state(job, None, set_id, duration_seconds=8, content=_b_content(set_id)))
    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    return current, current.timeline.model_dump(mode="json")


@pytest.mark.parametrize("mutate, expected", [
    (lambda raw: raw["shots"][0].update({"asset_src": "videoagents/job/assets/fake.png"}), "不能带 asset_src"),
    (lambda raw: raw.update({"presentation": "production"}), "组件样片时间轴"),
    (lambda raw: raw["shots"][0].update({"component_id": "Rve-QuoteCard"}), "主组件不匹配"),
    (lambda raw: raw["shots"][0]["props"].update({"focus_steps": []}), "不能包含教学或重点圈选"),
    (lambda raw: raw["shots"][0]["props"].update({"items": ["只剩一个"]}), "数量或文字长度"),
])
def test_no_material_component_set_marker_is_strict(tmp_path, mutate, expected):
    current, raw = _valid_b_timeline_payload(tmp_path, set_id="B03")
    mutate(raw)

    with pytest.raises(ValueError, match=expected):
        validate_timeline(Timeline.model_validate(raw), current, {})


def test_no_material_component_set_marker_requires_portrait_timeline(tmp_path):
    current, raw = _valid_b_timeline_payload(tmp_path, set_id="B03")
    raw["width"] = 1920
    raw["height"] = 1080
    landscape = current.model_copy(update={"brief": current.brief.model_copy(update={"width": 1920, "height": 1080})})

    with pytest.raises(ValueError, match="竖屏时间轴"):
        validate_timeline(Timeline.model_validate(raw), landscape, {})


def test_component_demo_node_builds_rich_no_material_plan(tmp_path):
    repo, service, job = _empty_job(tmp_path, set_id="B04")

    result = ComponentDemoNode(repo, service)(_state(job, None, "B04", duration_seconds=16, content=_b_rich_content("B04"), composition="rich"))

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    shot = current.timeline.shots[0]
    assert shot.component_id == "Rve-StatCounter"
    assert shot.props["component_set"] == "B04"
    assert shot.props["composition"] == "rich"
    assert shot.props["rich_content"] == {
        "takeaway": "数字要问口径",
        "metric": {"label": "演示合计", "value": "399元", "detail": "演示数字"},
        "numeric_items": ["会员:199元", "礼物:100元", "视频:100元"],
    }
    assert [layer.component_id for layer in shot.layers] == ["Snapcn-TextRewrite", "Snapcn-TextHighlight"]
    plan_artifact = next(artifact for artifact in current.artifacts if artifact.kind == "director_plan")
    plan_path, _, _ = repo.artifact_path(plan_artifact.artifact_id)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["component_demo_recipe"]["version"] == "component-demo-v4"
    assert plan["component_demo_recipe"]["composition"] == "rich"
    assert plan["actual_composition_components"] == [
        "Rve-StatCounter",
        "Snapcn-TextRewrite",
        "Snapcn-TextHighlight",
        "Rve-ChartAnimation",
        "Snapcn-TextBuild",
    ]
    validate_timeline(current.timeline, current, {})
    _validate_director_plan_payload(plan, current, current.timeline)


def test_component_demo_node_rejects_rich_b04_metric_that_is_not_numeric_sum(tmp_path):
    repo, service, job = _empty_job(tmp_path, set_id="B04")
    content = {**_b_rich_content("B04"), "metric": {"label": "演示合计", "value": "400元", "detail": "演示数字"}}

    result = ComponentDemoNode(repo, service)(_state(job, None, "B04", duration_seconds=16, content=content, composition="rich"))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "同单位求和" in current.pending_input["issues"][0]


def test_component_demo_node_rejects_rich_for_material_sets(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A01")

    result = ComponentDemoNode(repo, service)(_state(job, asset, "A01", composition="rich"))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "只支持 basic" in current.pending_input["issues"][0]


@pytest.mark.parametrize("set_id", ["A07", "A08", "A09", "A10", "A11", "A12"])
def test_component_demo_node_builds_material_rich_sets(tmp_path, set_id):
    is_a09 = set_id == "A09"
    duration_seconds = 371 / 30 if is_a09 else 15
    repo, service, job, asset = _job_with_asset(
        tmp_path,
        set_id=set_id,
        video=is_a09,
        metadata_duration=371 / 30 if is_a09 else None,
        metadata_override={"frame_rate": 30.0, "width": 720, "height": 1440} if is_a09 else None,
    )

    result = ComponentDemoNode(repo, service)(
        _state(
            job,
            asset,
            set_id,
            duration_seconds=duration_seconds,
            content=_material_rich_content(set_id),
            composition="rich",
            focus_steps=_a09_focus_steps() if is_a09 else None,
        )
    )

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    shot = current.timeline.shots[0]
    expected_actual = MATERIAL_RICH_ACTUAL_COMPONENTS[set_id]
    assert current.timeline.presentation == "component_sample"
    assert current.timeline.duration_in_frames == (371 if is_a09 else 450)
    assert shot.component_id == expected_actual[0]
    assert shot.asset_src == asset.timeline_src
    assert shot.source_label.startswith(f"当前任务素材：{asset.name}")
    assert "example.test" in shot.source_label
    assert shot.title == _material_rich_content(set_id)["title"]
    assert shot.body == _material_rich_content(set_id)["body"]
    assert shot.props["component_set"] == set_id
    assert shot.props["composition"] == "rich"
    assert shot.props["rich_content"] == _material_rich_content(set_id)
    assert [layer.component_id for layer in shot.layers] == expected_actual[1:3]
    assert set(shot.props) == ({"component_set", "composition", "rich_content", "focus_steps", "focus_source_size"} if is_a09 else {"component_set", "composition", "rich_content"})
    if is_a09:
        assert shot.props["focus_steps"] == _a09_focus_steps()
        assert shot.props["focus_source_size"] == {"width": 720, "height": 1440}
    else:
        assert "focus_steps" not in shot.props
        assert "focus_source_size" not in shot.props

    plan_artifact = next(artifact for artifact in current.artifacts if artifact.kind == "director_plan")
    plan_path, _, owner = repo.artifact_path(plan_artifact.artifact_id)
    assert owner == job.job_id
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["component_demo_recipe"]["version"] == "component-demo-v5"
    assert plan["component_demo_recipe"]["set_id"] == set_id
    assert plan["component_demo_recipe"]["composition"] == "rich"
    assert plan["component_demo_recipe"]["asset_id"] == asset.asset_id
    assert plan["component_demo_recipe"]["content"] == _material_rich_content(set_id)
    assert plan["component_demo_recipe"]["no_external_material"] is False
    assert plan["actual_composition_components"] == expected_actual
    metadata = {item.asset_id: repo.asset_metadata(item.asset_id) for item in current.assets}
    validate_timeline(current.timeline, current, metadata)
    _validate_director_plan_payload(plan, current, current.timeline)


def test_component_demo_node_accepts_a09_legacy_upload_metadata_without_frame_count(tmp_path):
    repo, service, job, asset = _job_with_asset(
        tmp_path,
        set_id="A09",
        video=True,
        metadata_duration=12.366667,
        metadata_override={"frame_rate": 30.0, "width": 720, "height": 1440},
    )

    result = ComponentDemoNode(repo, service)(
        _state(
            job,
            asset,
            "A09",
            duration_seconds=371 / 30,
            content=_material_rich_content("A09"),
            composition="rich",
            focus_steps=_a09_focus_steps(),
        )
    )

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    metadata = {asset.asset_id: repo.asset_metadata(asset.asset_id)}
    assert "frame_count" not in metadata[asset.asset_id]
    validate_timeline(current.timeline, current, metadata)


@pytest.mark.parametrize(("set_id", "content", "focus_steps", "expected"), [
    ("A07", {**_material_rich_content("A07"), "metric": {"label": "多余", "value": "3项"}}, None, "不接受 metric"),
    ("A08", {**_material_rich_content("A08"), "items": ["一项", "两项"]}, None, "exactly 3"),
    ("A09", _material_rich_content("A09"), [{**_a09_focus_steps()[0], "instruction": "错的"}, *_a09_focus_steps()[1:]], "instruction"),
    ("A10", {**_material_rich_content("A10"), "metric": {"label": "三笔合计", "value": "400元", "detail": "133元+133元+133元"}}, None, "同单位求和"),
    ("A10", {**_material_rich_content("A10"), "numeric_items": ["第1笔:133元", "第2笔:133元", "第3笔:133美元"]}, None, "同一个单位"),
])
def test_component_demo_node_rejects_invalid_material_rich_content(tmp_path, set_id, content, focus_steps, expected):
    is_a09 = set_id == "A09"
    repo, service, job, asset = _job_with_asset(
        tmp_path,
        set_id=set_id,
        video=is_a09,
        metadata_duration=371 / 30 if is_a09 else None,
        metadata_override={"frame_count": 371, "frame_rate": 30.0, "width": 720, "height": 1440} if is_a09 else None,
    )

    result = ComponentDemoNode(repo, service)(
        _state(
            job,
            asset,
            set_id,
            duration_seconds=371 / 30 if is_a09 else 15,
            content=content,
            composition="rich",
            focus_steps=focus_steps if focus_steps is not None else (_a09_focus_steps() if is_a09 else None),
        )
    )

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert expected in current.pending_input["issues"][0]


def test_component_demo_rejects_material_rich_asset_from_other_job_scope(tmp_path):
    repo, service, job, asset = _job_with_asset(tmp_path, set_id="A07", bad_owner=True)

    result = ComponentDemoNode(repo, service)(
        _state(job, asset, "A07", duration_seconds=15, content=_material_rich_content("A07"), composition="rich")
    )

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "不属于此视频任务" in current.pending_input["issues"][0]


def _valid_material_rich_timeline_payload(tmp_path, *, set_id="A09"):
    is_a09 = set_id == "A09"
    repo, service, job, asset = _job_with_asset(
        tmp_path,
        set_id=set_id,
        video=is_a09,
        metadata_duration=371 / 30 if is_a09 else None,
        metadata_override={"frame_count": 371, "frame_rate": 30.0, "width": 720, "height": 1440} if is_a09 else None,
    )
    result = ComponentDemoNode(repo, service)(
        _state(
            job,
            asset,
            set_id,
            duration_seconds=371 / 30 if is_a09 else 15,
            content=_material_rich_content(set_id),
            composition="rich",
            focus_steps=_a09_focus_steps() if is_a09 else None,
        )
    )
    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    metadata = {item.asset_id: repo.asset_metadata(item.asset_id) for item in current.assets}
    return current, current.timeline.model_dump(mode="json"), metadata


@pytest.mark.parametrize("mutate, expected", [
    (lambda raw, metadata: raw["shots"][0].update({"asset_src": None}), "asset_src"),
    (lambda raw, metadata: raw["shots"][0]["props"].update({"extra": True}), "主组件参数"),
    (lambda raw, metadata: raw["shots"][0]["props"].update({"rich_content": {**raw["shots"][0]["props"]["rich_content"], "items": ["只剩一个"]}}), "exactly 3"),
    (lambda raw, metadata: raw["shots"][0]["props"]["focus_steps"][0].update({"instruction": "错误"}), "instruction"),
    (lambda raw, metadata: metadata["asset-a09"].update({"frame_count": 370}), "frame_count"),
    (lambda raw, metadata: metadata["asset-a09"].update({"width": 900}), "focus_source_size"),
])
def test_material_rich_component_set_marker_is_strict(tmp_path, mutate, expected):
    current, raw, metadata = _valid_material_rich_timeline_payload(tmp_path, set_id="A09")
    mutate(raw, metadata)

    with pytest.raises(ValueError, match=expected):
        validate_timeline(Timeline.model_validate(raw), current, metadata)

def _valid_rich_b_timeline_payload(tmp_path, *, set_id="B02"):
    repo, service, job = _empty_job(tmp_path, set_id=set_id)
    result = ComponentDemoNode(repo, service)(_state(job, None, set_id, duration_seconds=15, content=_b_rich_content(set_id), composition="rich"))
    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    return current, current.timeline.model_dump(mode="json")


@pytest.mark.parametrize("mutate, expected", [
    (lambda raw: raw["shots"][0]["props"].update({"keyword": "另一句话"}), "keyword 必须等于"),
    (lambda raw: raw["shots"][0]["props"].update({"rich_content": {**raw["shots"][0]["props"]["rich_content"], "metric": {"label": "演示环节", "value": "4段", "detail": "演示数字"}}}), "数字必须等于 items 条数"),
])
def test_rich_no_material_component_set_marker_is_strict(tmp_path, mutate, expected):
    current, raw = _valid_rich_b_timeline_payload(tmp_path, set_id="B02")
    mutate(raw)

    with pytest.raises(ValueError, match=expected):
        validate_timeline(Timeline.model_validate(raw), current, {})


@pytest.mark.parametrize("set_id", [f"B{index:02d}" for index in range(7, 19)])
def test_component_demo_node_builds_expanded_rich_no_material_sets(tmp_path, set_id):
    repo, service, job = _empty_job(tmp_path, set_id=set_id)

    result = ComponentDemoNode(repo, service)(_state(job, None, set_id, duration_seconds=18, content=_expanded_content(set_id), composition="rich"))

    assert result["route"] == "director_demo"
    current = repo.get_job(job.job_id)
    shot = current.timeline.shots[0]
    assert shot.asset_src is None
    assert shot.props["component_set"] == set_id
    assert set(shot.props) == {"component_set", "composition", "rich_content"}
    assert shot.props["composition"] == "rich"
    assert shot.props["rich_content"]["takeaway"] == _expanded_content(set_id)["takeaway"]
    assert current.timeline.duration_in_frames == 540
    assert len(shot.layers) == 2
    plan_artifact = next(artifact for artifact in current.artifacts if artifact.kind == "director_plan")
    plan_path, _, _ = repo.artifact_path(plan_artifact.artifact_id)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    actual = plan["actual_composition_components"]
    assert plan["component_demo_recipe"]["version"] == "component-demo-v4"
    assert plan["component_demo_recipe"]["composition"] == "rich"
    assert plan["component_demo_recipe"]["content"] == _expanded_content(set_id)
    assert actual == EXPANDED_ACTUAL_COMPONENTS[set_id]
    assert shot.component_id == actual[0]
    assert shot.layers[0].component_id in actual
    assert shot.layers[1].component_id in actual
    if set_id in {"B15", "B16"}:
        assert shot.layers[0].props["items"] == _expanded_content(set_id)["items"]
    validate_timeline(current.timeline, current, {})
    _validate_director_plan_payload(plan, current, current.timeline)


def test_component_demo_node_rejects_basic_for_expanded_no_material_set(tmp_path):
    repo, service, job = _empty_job(tmp_path, set_id="B07")

    result = ComponentDemoNode(repo, service)(_state(job, None, "B07", duration_seconds=18, content=_expanded_content("B07"), composition="basic"))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "只支持 rich" in current.pending_input["issues"][0]


def test_component_demo_node_rejects_expanded_wrong_numeric_difference(tmp_path):
    repo, service, job = _empty_job(tmp_path, set_id="B09")
    content = {**_expanded_content("B09"), "metric": {"label": "多出的核对动作", "value": "2步", "detail": "2步-1步"}}

    result = ComponentDemoNode(repo, service)(_state(job, None, "B09", duration_seconds=18, content=content, composition="rich"))

    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert "同单位差值" in current.pending_input["issues"][0]
