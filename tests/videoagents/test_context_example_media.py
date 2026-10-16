import copy

import pytest

from videoagents.contracts import Asset, Brief, Job, Script, ScriptSegment, Timeline
from videoagents.tools.timeline import media_coverage_report, validate_media_coverage, validate_timeline


def scene_fixture():
    def image(asset_id, source):
        return Asset(asset_id=asset_id, name=asset_id + ".png", role="evidence", mime_type="image/png",
                     size_bytes=10, sha256="a" * 64, source_url=source, license_note="unit",
                     artifact_id=asset_id, url="/api/artifacts/" + asset_id,
                     timeline_src=f"videoagents/context-test/assets/{asset_id}.png")

    report = image("report", "https://report.example/official")
    profile = image("profile", "https://www.thepaper.cn/domestic-case")
    call = image("call", profile.source_url)
    script = Script(title="独立案件不能混成同一事件", revision=1, segments=[
        ScriptSegment(segment_id="s1", narration="视频里是真人，打字的可能是AI。",
                      source_refs=[report.source_url], asset_ids=[report.asset_id]),
        ScriptSegment(segment_id="s2", narration="这是警方公布的另一起国内案件。",
                      source_refs=[profile.source_url], asset_ids=[profile.asset_id, call.asset_id]),
    ])
    job = Job(job_id="context-test", revision=1, status="DRAFT", stage="director", created_at="unit",
              updated_at="unit", message="unit", brief=Brief(topic=script.title, width=1080, height=1920, fps=30),
              script=script, assets=[report, profile, call])
    raw = {
        "job_id": job.job_id, "revision": 1, "width": 1080, "height": 1920, "fps": 30,
        "duration_in_frames": 120, "audio_src": "videoagents/context-test/assets/voice.wav",
        "captions": [{"text": script.segments[0].narration, "start_ms": 0.0, "end_ms": 1900.0},
                     {"text": script.segments[1].narration, "start_ms": 2000.0, "end_ms": 3900.0}],
        "shots": [
            {"shot_id": "scene", "start_frame": 0, "end_frame": 60, "component_id": "Snapcn-PhoneFrame",
             "title": "视频里的真人，等于打字也是真人？", "body": "", "asset_src": profile.timeline_src,
             "source_label": "另案示例｜thepaper.cn｜警方供图", "media_usage": "context_example",
             "props": {"content_mode": "media"}},
            {"shot_id": "domestic", "start_frame": 60, "end_frame": 120, "component_id": "evidence",
             "title": "国内独立案件", "body": "", "asset_src": call.timeline_src,
             "source_label": "thepaper.cn", "props": {}},
        ],
    }
    audio = Asset(asset_id="voice", name="voice.wav", role="audio", mime_type="audio/wav", size_bytes=10,
                  sha256="b" * 64, artifact_id="voice", url="/api/artifacts/voice",
                  timeline_src=raw["audio_src"])
    job.assets.append(audio)
    return job, raw


def test_labeled_same_video_other_case_can_establish_opening_without_changing_script():
    job, raw = scene_fixture()
    before = job.script.model_dump(mode="json")
    candidate = Timeline.model_validate(raw)
    validate_timeline(candidate, job)
    report = validate_media_coverage(candidate, job)
    assert report["actual_media_frames"] == 120
    assert report["source_evidence_frames"] == 60
    assert report["context_example_frames"] == 60
    assert candidate.captions[0].start_ms == 0.0
    assert job.script.model_dump(mode="json") == before
    assert candidate.shots[0].model_dump()["media_usage"] == "context_example"


def test_default_fact_evidence_still_cannot_use_another_cases_source():
    job, raw = scene_fixture()
    raw["shots"][0].pop("media_usage")
    with pytest.raises(ValueError, match="语义关联"):
        media_coverage_report(Timeline.model_validate(raw), job)


@pytest.mark.parametrize("label", ["thepaper.cn｜警方供图", "另案示例｜警方供图", "另案示例｜unrelated.example"])
def test_context_example_requires_visible_case_separation_and_matching_source_domain(label):
    job, raw = scene_fixture()
    raw["shots"][0]["source_label"] = label
    with pytest.raises(ValueError, match="另案示例"):
        validate_timeline(Timeline.model_validate(raw), job)
    with pytest.raises(ValueError, match="另案示例"):
        media_coverage_report(Timeline.model_validate(raw), job)


@pytest.mark.parametrize("component", ["evidence", "title", "comparison"])
def test_context_example_cannot_masquerade_as_fact_evidence(component):
    job, raw = scene_fixture()
    raw["shots"][0]["component_id"] = component
    with pytest.raises(ValueError, match="另案示例.*(只能|不能)"):
        validate_timeline(Timeline.model_validate(raw), job)


@pytest.mark.parametrize("change", ["unreferenced", "decoration", "missing_source", "missing_media"])
def test_context_example_rejects_media_outside_this_scripts_grounded_material(change):
    job, raw = scene_fixture()
    profile = job.assets[1]
    if change == "unreferenced":
        profile.source_url = "https://www.thepaper.cn/unrelated-story"
        job.script.segments[1].asset_ids.remove(profile.asset_id)
    elif change == "decoration":
        profile.role = "decoration"
    elif change == "missing_source":
        profile.source_url = ""
    else:
        raw["shots"][0]["asset_src"] = None
    with pytest.raises(ValueError, match="另案示例必须"):
        validate_timeline(Timeline.model_validate(raw), job)


def test_context_usage_never_relaxes_task_media_path_ownership():
    job, raw = scene_fixture()
    foreign = "videoagents/another-job/assets/profile.png"
    job.assets[1].timeline_src = foreign
    raw["shots"][0]["asset_src"] = foreign
    with pytest.raises(ValueError, match="任务.*路径|路径.*任务|素材.*路径|任务身份|分镜素材"):
        validate_timeline(Timeline.model_validate(raw), job)


@pytest.mark.parametrize("approved_only", [False, True])
def test_context_video_ranges_cannot_repeat_to_inflate_media_coverage(approved_only):
    job, raw = scene_fixture()
    video = job.assets[1]
    video.mime_type = "video/mp4"
    video.timeline_src = "videoagents/context-test/assets/profile.mp4"
    if approved_only:
        video.source_url = "https://context.example/similar-product"
        job.script.segments[1].asset_ids.remove(video.asset_id)
        raw["shots"][0]["source_label"] = "另案示例｜context.example｜同类示意｜非涉案"
    second = copy.deepcopy(raw["shots"][0])
    second.update(shot_id="scene-again", start_frame=60, end_frame=120)
    raw["shots"] = [raw["shots"][0], second]
    for shot in raw["shots"]:
        shot["component_id"] = "video"
        shot["asset_src"] = video.timeline_src
        shot["props"] = {"start_seconds": 0, "end_seconds": 2, "fit": "contain"}
    with pytest.raises(ValueError, match="重复使用相同截取区间"):
        media_coverage_report(Timeline.model_validate(raw), job, {video.asset_id: {"duration_seconds": 4}},
                              approved_context_sources={video.timeline_src} if approved_only else None)


def test_approved_context_keeps_video_duration_and_task_path_constraints():
    job, raw = scene_fixture()
    video = job.assets[1]
    video.mime_type = "video/mp4"
    video.timeline_src = "videoagents/context-test/assets/profile.mp4"
    video.source_url = "https://context.example/similar-product"
    job.script.segments[1].asset_ids.remove(video.asset_id)
    shot = raw["shots"][0]
    shot.update(component_id="video", asset_src=video.timeline_src,
                source_label="另案示例｜context.example｜同类示意｜非涉案")
    shot["props"] = {"start_seconds": 0, "end_seconds": 2, "fit": "contain"}
    proof = {video.timeline_src}
    validate_timeline(Timeline.model_validate(raw), job, {video.asset_id: {"duration_seconds": 2}},
                      approved_context_sources=proof)
    shot["props"]["start_seconds"], shot["props"]["end_seconds"] = 1, 3
    with pytest.raises(ValueError, match="实测时长"):
        validate_timeline(Timeline.model_validate(raw), job, {video.asset_id: {"duration_seconds": 2}},
                          approved_context_sources=proof)
    shot["props"]["start_seconds"], shot["props"]["end_seconds"] = 0, 2
    video.timeline_src = "videoagents/other-job/assets/profile.mp4"
    shot["asset_src"] = video.timeline_src
    with pytest.raises(ValueError, match="路径不属于"):
        validate_timeline(Timeline.model_validate(raw), job, {video.asset_id: {"duration_seconds": 2}},
                          approved_context_sources={video.timeline_src})
