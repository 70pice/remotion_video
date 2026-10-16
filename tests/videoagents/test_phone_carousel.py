"""Real imported images in one continuous PhoneFrame retain media boundaries."""

import copy

import pytest

from videoagents.contracts import Artifact, Asset, Brief, Job, Script, ScriptSegment, Timeline
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.tools.timeline import media_coverage_report, validate_timeline


def scene():
    images = [Asset(asset_id=f"image-{index}", name=f"{index}.png", role="evidence", mime_type="image/png",
                    size_bytes=20, sha256=str(index) * 64, source_url=f"https://example.com/{index}",
                    artifact_id=f"image-{index}", url=f"/api/artifacts/image-{index}",
                    timeline_src=f"videoagents/carousel/assets/{index}.png") for index in range(1, 3)]
    audio = Asset(asset_id="audio", name="voice.wav", role="audio", mime_type="audio/wav", size_bytes=20,
                  sha256="a" * 64, artifact_id="audio", url="/api/artifacts/audio",
                  timeline_src="videoagents/carousel/assets/voice.wav")
    script = Script(title="真实图片轮播", revision=1, segments=[
        ScriptSegment(segment_id="s1", narration="第一张图片。", asset_ids=[images[0].asset_id]),
        ScriptSegment(segment_id="s2", narration="第二张图片。", asset_ids=[images[1].asset_id]),
    ])
    job = Job(job_id="carousel", revision=1, status="DRAFT", stage="director", created_at="unit", updated_at="unit",
              message="unit", brief=Brief(topic=script.title), assets=[*images, audio], script=script)
    timeline = Timeline.model_validate({"schema_version": "1", "job_id": job.job_id, "revision": 1,
        "width": job.brief.width, "height": job.brief.height, "fps": 30, "duration_in_frames": 120,
        "audio_src": audio.timeline_src,
        "captions": [{"text": segment.narration, "start_ms": index * 2000, "end_ms": (index + 1) * 2000 - 100}
                     for index, segment in enumerate(script.segments)],
        "shots": [{"shot_id": "phone", "start_frame": 0, "end_frame": 120,
                   "component_id": "Snapcn-PhoneFrame", "title": "图片轮播", "source_label": "example.com",
                   "asset_src": images[0].timeline_src, "props": {"content_mode": "media",
                   "media_slides": [{"asset_src": image.timeline_src, "start_frame": index * 60, "asset_fit": "contain"}
                                    for index, image in enumerate(images)]}}]})
    return job, timeline


def test_carousel_keeps_one_shot_and_counts_each_images_actual_narration_window():
    job, timeline = scene()
    before = timeline.model_dump()
    validate_timeline(timeline, job)
    report = media_coverage_report(timeline, job)
    assert report["actual_media_frames"] == report["source_evidence_frames"] == 120
    assert timeline.model_dump() == before and len(timeline.shots) == 1


@pytest.mark.parametrize("change", ["missing", "foreign", "traversal", "video", "unsupported", "restricted"])
def test_every_slide_requires_a_renderable_image_registered_to_this_job(change):
    job, timeline = scene()
    second = timeline.shots[0].props["media_slides"][1]
    if change == "missing":
        second["asset_src"] = "videoagents/carousel/assets/not-imported.png"
    elif change == "foreign":
        second["asset_src"] = "videoagents/another-job/assets/2.png"
    elif change == "traversal":
        second["asset_src"] = "videoagents/carousel/../2.png"
    elif change == "video":
        job.assets[1].mime_type = "video/mp4"
    elif change == "unsupported":
        second["asset_src"] = job.assets[1].timeline_src = "videoagents/carousel/assets/2.svg"
    else:
        job.assets[1].license_note = "禁止使用"
    with pytest.raises(ValueError):
        validate_timeline(timeline, job)


@pytest.mark.parametrize("change", ["one", "nine", "first-start", "same-start", "past-end", "bool-start",
                                    "bad-fit", "bad-crop", "extra-key", "first-src", "component", "focus",
                                    "tutorial", "set-design", "transition-bool", "transition-large", "transition-alone"])
def test_carousel_shape_timing_and_exclusive_slot_are_checked(change):
    job, timeline = scene()
    shot = timeline.shots[0]
    slides = shot.props["media_slides"]
    if change == "one":
        slides.pop()
    elif change == "nine":
        shot.props["media_slides"] = [dict(slides[0], start_frame=index) for index in range(9)]
    elif change == "first-start":
        slides[0]["start_frame"] = 1
    elif change == "same-start":
        slides[1]["start_frame"] = 0
    elif change == "past-end":
        slides[1]["start_frame"] = 120
    elif change == "bool-start":
        slides[1]["start_frame"] = True
    elif change == "bad-fit":
        slides[1]["asset_fit"] = "fill"
    elif change == "bad-crop":
        slides[1]["asset_crop"] = {"x": 0.9, "y": 0, "width": 0.5, "height": 1}
    elif change == "extra-key":
        slides[1]["src"] = slides[1]["asset_src"]
    elif change == "first-src":
        slides[0]["asset_src"] = slides[1]["asset_src"]
    elif change == "component":
        shot.component_id = "Talkcraft-slow-push-in"
    elif change == "focus":
        shot.props["focus_steps"] = []
    elif change == "tutorial":
        shot.props["tutorial_steps"] = []
    elif change == "set-design":
        shot.props["component_set"] = "A08"
    elif change == "transition-bool":
        shot.props["carousel_transition_frames"] = True
    elif change == "transition-large":
        shot.props["carousel_transition_frames"] = 16
    else:
        shot.props.pop("media_slides")
        shot.props["carousel_transition_frames"] = 6
    with pytest.raises(ValueError):
        validate_timeline(timeline, job)


def test_carousel_later_image_cannot_borrow_first_images_semantic_approval():
    job, timeline = scene()
    job.script.segments[1].asset_ids = [job.assets[0].asset_id]
    with pytest.raises(ValueError, match="语义关联"):
        media_coverage_report(timeline, job)


def test_approved_context_projection_covers_unlinked_images_on_later_pages(monkeypatch):
    from videoagents.services import director_recovery
    from videoagents.services.context_media import approved_context_sources

    job, timeline = scene()
    job.script.segments[1].asset_ids = []
    timeline.shots[0].media_usage = "context_example"
    timeline.shots[0].source_label = "另案示例｜example.com｜同类示意｜非涉案"
    job.artifacts.append(Artifact(artifact_id="research", kind="research", name="research.json", mime_type="application/json",
                                  size_bytes=20, sha256="f" * 64, url="/api/artifacts/research", revision=1))
    projection = job.model_dump()
    research = {"sources": [{"url": asset.source_url, "asset_ids": [asset.asset_id]} for asset in job.assets[:2]],
                "visuals": [{"source_url": asset.source_url, "asset_id": asset.asset_id, "artifact_id": asset.artifact_id}
                            for asset in job.assets[:2]]}
    monkeypatch.setattr(director_recovery, "verify_director_recovery_inputs", lambda *args: {"approval_projection": projection})
    monkeypatch.setattr(director_recovery, "_json", lambda *args: research)
    proof = approved_context_sources(None, job, timeline)
    assert proof == {job.assets[1].timeline_src}
    validate_timeline(timeline, job, approved_context_sources=proof)
    assert media_coverage_report(timeline, job, approved_context_sources=proof)["actual_media_frames"] == 120
    job.assets[1].sha256 = "e" * 64
    assert approved_context_sources(None, job, timeline) == set()


@pytest.mark.parametrize("change", ["order", "timing", "crop", "transition", "image-receipt"])
def test_carousel_render_dependency_binds_all_slides_and_their_receipts(change):
    job, timeline = scene()
    job.timeline = timeline
    before = dependency_fingerprint(job)
    job = copy.deepcopy(job)
    slides = job.timeline.shots[0].props["media_slides"]
    if change == "order":
        slides.reverse()
    elif change == "timing":
        slides[1]["start_frame"] = 61
    elif change == "crop":
        slides[1]["asset_crop"] = {"x": 0, "y": 0, "width": 0.5, "height": 1}
    elif change == "transition":
        job.timeline.shots[0].props["carousel_transition_frames"] = 0
    else:
        job.assets[1].sha256 = "f" * 64
    assert dependency_fingerprint(job) != before
