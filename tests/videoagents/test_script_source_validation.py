from videoagents.contracts import Asset, Brief, Script, ScriptSegment
from videoagents.nodes.screenwriter import script_issues
from videoagents.services.jobs import JobService
from videoagents.storage import Repository

SOURCE_URL = "https://pewresearch.org/unit-report"
EVIDENCE_URL = "https://a16z.com/original-report"


def _script(source: str = SOURCE_URL) -> Script:
    return Script(
        title="研究来源校验",
        origin="model",
        revision=1,
        segments=[
            ScriptSegment(
                segment_id="s1",
                narration="这段引用的是素材节点实际读到的补充研究来源。",
                screen_text="补充研究来源",
                source_refs=[source],
                asset_ids=[],
            )
        ],
    )


def _job_with_registered_source(tmp_path, *, evidence: bool = True):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="补充研究来源", source_urls=[]))
    source_file = repo.root / "source.txt"
    source_file.write_text("冻结后的正文内容", encoding="utf-8")
    source_artifact = service.register_artifact(job, source_file, "source", "text/plain")
    assets = []
    if evidence:
        assets.append(Asset(
            asset_id="original-chart",
            name="原报告图表",
            role="evidence",
            mime_type="image/png",
            size_bytes=100,
            sha256="b" * 64,
            source_url=EVIDENCE_URL,
            license_note="UNIT TEST",
            artifact_id="chart-artifact",
            url="/api/artifacts/chart-artifact",
            timeline_src=f"videoagents/{job.job_id}/assets/chart.png",
        ))
    job = repo.update_job(job.job_id, job.revision, artifacts=[source_artifact], assets=assets)
    return repo, job, source_artifact


def _trusted_research(source_artifact, url: str = SOURCE_URL) -> dict:
    return {
        "schema_version": "3",
        "status": "COMPLETED",
        "sources": [
            {
                "url": url,
                "final_url": url,
                "title": "UNIT source",
                "text": "冻结后的正文内容",
                "platform": "web",
                "retrieved_at": "unit",
                "sha256": source_artifact.sha256,
                "knowledge_status": "skill_read",
                "artifact_id": source_artifact.artifact_id,
                "artifact_url": source_artifact.url,
                "asset_ids": [],
            }
        ],
        "visuals": [],
        "limitations": [],
    }


def test_script_can_reference_read_research_source_without_user_initial_url_or_own_asset(tmp_path):
    _, job, source_artifact = _job_with_registered_source(tmp_path)
    job = job.model_copy(update={"script": _script()})

    assert script_issues(job, _trusted_research(source_artifact)) == []


def test_unread_research_url_is_not_trusted_as_a_source(tmp_path):
    _, job, source_artifact = _job_with_registered_source(tmp_path)
    job = job.model_copy(update={"script": _script()})
    unread = _trusted_research(source_artifact)
    unread["sources"][0].pop("text")

    issues = script_issues(job, unread)

    assert any("来源不在用户来源或真实素材清单中" in issue for issue in issues)


def test_research_source_without_registered_artifact_is_not_trusted(tmp_path):
    _, job, source_artifact = _job_with_registered_source(tmp_path)
    job = job.model_copy(update={"script": _script(), "artifacts": []})

    issues = script_issues(job, _trusted_research(source_artifact))

    assert any("来源不在用户来源或真实素材清单中" in issue for issue in issues)


def test_research_source_with_different_digest_is_not_trusted(tmp_path):
    _, job, source_artifact = _job_with_registered_source(tmp_path)
    job = job.model_copy(update={"script": _script()})
    research = _trusted_research(source_artifact)
    research["sources"][0]["sha256"] = "c" * 64

    issues = script_issues(job, research)

    assert any("来源不在用户来源或真实素材清单中" in issue for issue in issues)


def test_read_research_source_without_any_evidence_asset_is_still_rejected(tmp_path):
    _, job, source_artifact = _job_with_registered_source(tmp_path, evidence=False)
    job = job.model_copy(update={"script": _script()})

    issues = script_issues(job, _trusted_research(source_artifact))

    assert issues == ["事实性文案需要带原始出处的真实证据图片、截图或视频"]


def test_research_url_with_credentials_is_rejected_even_if_receipt_shape_matches(tmp_path):
    source = "https://user:secret@example.com/report"
    _, job, source_artifact = _job_with_registered_source(tmp_path)
    job = job.model_copy(update={"script": _script(source)})

    issues = script_issues(job, _trusted_research(source_artifact, source))

    assert any("来源 URL 无效" in issue for issue in issues)
