import pytest

from videoagents.contracts import (
    Artifact,
    Asset,
    Brief,
    DraftRequest,
    Script,
    ScriptCritique,
    ScriptDiscussion,
    ScriptSegment,
    SettingsPatch,
)
from videoagents.graph import VideoProductionGraph
from videoagents.providers.cli_runner import CliFailure
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools.media import sha256
from worker.runner import Worker

SOURCE_URL = "https://example.test/source"


def _enqueue(repo: Repository, job, key: str = "discussion-command", action: str = "produce"):
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": action, "idempotency_key": key})
    return repo.claim(12345)


def _resume(repo: Repository, job, key: str = "discussion-resume"):
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "resume", "decision": "confirm",
                              "note": "UNIT TEST: reviewer model is now configured",
                              "pending_token": job.pending_input["pending_token"], "idempotency_key": key})


def _job(tmp_path, *, evidence: bool = True, text: str = "事实：这条文案有真实来源。"):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    SettingsService(repo).patch(SettingsPatch(capture_enabled=False, research_download_images=False))
    job = repo.create_job(Brief(topic="文案讨论测试", script_text=text, source_urls=[] if text else [SOURCE_URL],
                                target_seconds=2, width=240, height=426, fps=15, usage="personal"))
    if evidence:
        path = repo.root / "unit-evidence.png"
        path.write_bytes(b"not-a-real-image-but-valid-discussion-evidence-receipt")
        artifact = Artifact(artifact_id="unit-evidence-artifact", kind="asset", name="unit-evidence.png",
                            mime_type="image/png", size_bytes=path.stat().st_size, sha256=sha256(path),
                            url="/api/artifacts/unit-evidence-artifact", revision=job.revision)
        repo.put_artifact(job.job_id, artifact, path)
        asset = Asset(asset_id="asset-evidence", name="unit-evidence.png", role="evidence",
                      mime_type="image/png", size_bytes=artifact.size_bytes, sha256=artifact.sha256,
                      source_url=SOURCE_URL, license_note="UNIT TEST", artifact_id=artifact.artifact_id,
                      url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/unit-evidence.png")
        job = repo.update_job(job.job_id, job.revision, assets=[asset], artifacts=[artifact])
    service.write_json(repo.get_job(job.job_id), "research.json", {
        "schema_version": "3",
        "status": "COMPLETED",
        "sources": [{"url": SOURCE_URL, "title": "UNIT source", "text": "unit source text", "asset_ids": []}],
        "visuals": [{"asset_id": "asset-evidence", "source_url": SOURCE_URL}] if evidence else [],
        "limitations": [],
    }, "research")
    return repo, service, repo.get_job(job.job_id)


def _model_script():
    return {"title": "模型初稿", "origin": "model", "revision": 1,
            "segments": [{"segment_id": "s1", "narration": "事实：模型初稿保留真实来源。",
                          "screen_text": "模型初稿", "source_refs": [SOURCE_URL],
                          "asset_ids": ["asset-evidence"]}]}


def _enable_discussion(repo: Repository, *, rounds: int = 2, screenwriter: bool = True, reviewer: bool = True):
    roles = {}
    if screenwriter:
        roles["screenwriter"] = {"enabled": True, "model": "unit-writer"}
    if reviewer:
        roles["script_reviewer"] = {"enabled": True, "model": "unit-reviewer"}
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=True,
                                              script_discussion_max_rounds=rounds,
                                              role_models=roles or None))


def _critique(decision: str, *, segment_id: str = "s1"):
    if decision == "APPROVE":
        return {"decision": "APPROVE", "summary": "文案已经解决审查问题。", "strengths": ["来源清楚"], "issues": []}
    return {"decision": "REVISE", "summary": "需要压缩开头并补足画面承接。", "strengths": ["主题明确"],
            "issues": [{"segment_id": segment_id, "category": "hook", "concern": "开头冲击力不足。",
                        "suggestion": "第一句直接抛出冲突。"}]}


def _rewrite():
    return {"script": {"title": "改稿后文案", "origin": "model", "revision": 1,
                       "segments": [{"segment_id": "s1", "narration": "事实：改成更有冲击力的开头。",
                                     "screen_text": "冲击力开头", "source_refs": [SOURCE_URL],
                                     "asset_ids": ["asset-evidence"]}]},
            "response": "已按审查意见重写开头，并保留原始来源。"}


def _rewrite_with_narration(index: int):
    value = _rewrite()
    value["script"]["segments"][0]["narration"] = f"事实：第 {index} 次改稿仍保留真实来源。"
    value["response"] = f"第 {index} 次回应审查意见。"
    return value


def test_script_discussion_default_disabled_never_calls_reviewer(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: pytest.fail("discussion called a model"))
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "default-off"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "voice"
    assert current.script_discussion is None
    assert current.script.segments[0].narration == "事实：这条文案有真实来源。"


def test_script_discussion_revise_then_approve_updates_script_and_history(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, context))
        assert set(context) == {"brief", "script", "script_discussion", "research", "assets"}
        if role == "script_reviewer" and len(calls) == 1:
            return _critique("REVISE")
        if role == "screenwriter":
            assert "每段 source_refs 必须有真实来源" in instruction
            assert "narration 必须以“观点：”或“个人感受：”开头" in instruction
            assert "不能只写“我建议”" in instruction
            return _rewrite()
        if role == "script_reviewer":
            turn = context["script_discussion"]["rounds"][-1]
            assert turn["response"] == "已按审查意见重写开头，并保留原始来源。"
            assert turn["script"]["segments"][0]["narration"] == "事实：改成更有冲击力的开头。"
            return _critique("APPROVE")
        raise AssertionError(role)

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "revise-approve"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert [item[0] for item in calls] == ["script_reviewer", "screenwriter", "script_reviewer"]
    assert current.status == "NEEDS_INPUT" and current.stage == "voice"
    assert current.script.segments[0].narration == "事实：改成更有冲击力的开头。"
    assert current.script_discussion.status == "APPROVED"
    assert [item.round for item in current.script_discussion.rounds] == [1, 2]
    assert current.script_discussion.rounds[0].critique.decision == "REVISE"
    assert current.script_discussion.rounds[1].response == "已按审查意见重写开头，并保留原始来源。"
    assert {item.kind for item in current.artifacts} >= {"script", "script_discussion"}


def test_script_discussion_exhaustion_never_auto_approves(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo, rounds=1)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: _critique("REVISE"))
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "exhaust"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert current.script_discussion.status == "EXHAUSTED"
    assert len(current.script_discussion.rounds) == 1
    assert "仍未通过" in current.message


def test_missing_reviewer_model_pauses_and_resume_reuses_saved_draft(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo, reviewer=False)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "missing-reviewer"})

    assert Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.stage == "script"
    assert len(paused.script_discussion.rounds) == 1
    assert paused.script_discussion.rounds[0].critique is None

    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        return _critique("APPROVE")

    SettingsService(repo).patch(SettingsPatch(role_models={"script_reviewer": {"enabled": True, "model": "unit-reviewer"}}))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    _resume(repo, paused)

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert calls == ["script_reviewer"]
    assert len(current.script_discussion.rounds) == 1
    assert current.script_discussion.status == "APPROVED"


def test_first_writer_pause_freezes_discussion_policy_before_settings_change(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path, text="")
    _enable_discussion(repo, screenwriter=False, reviewer=True)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "writer-missing"})

    assert Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.stage == "script"
    assert paused.script_discussion.enabled is True
    assert paused.script_discussion.rounds == []

    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False,
                                              role_models={"screenwriter": {"enabled": True, "model": "unit-writer"}}))
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        return _model_script() if role == "screenwriter" else _critique("APPROVE")

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    _resume(repo, paused, "writer-missing-resume")

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert calls == ["screenwriter", "script_reviewer"]
    assert current.script_discussion.enabled is True
    assert current.script_discussion.status == "APPROVED"
    assert len(current.script_discussion.rounds) == 1


@pytest.mark.parametrize("segment_id", ["missing", "s1–s8", "s1–s5", "s1,s2"])
def test_bad_critique_segment_id_blocks_discussion(monkeypatch, tmp_path, segment_id):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: _critique("REVISE", segment_id=segment_id))
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "bad-segment"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert "不存在的段落 ID" in current.message
    assert current.script_discussion.rounds[0].critique is None


@pytest.mark.parametrize("segment_ids,issue_id", [(["s1", "s2"], "s2"), (["opening", "closing"], "")])
def test_reviewer_schema_and_instruction_use_only_current_draft_ids(monkeypatch, tmp_path, segment_ids, issue_id):
    repo, service, job = _job(tmp_path)
    script = Script(title="当前稿件", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id=segment_id, narration="事实：有真实来源的文案。",
                                            source_refs=[SOURCE_URL], asset_ids=["asset-evidence"])
                              for segment_id in segment_ids])
    repo.update_job(job.job_id, job.revision, script=script)
    _enable_discussion(repo, rounds=1)
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, instruction, context, output_schema))
        return _critique("REVISE", segment_id=issue_id)

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "exact-draft-ids"})

    assert Worker(repo, service.project_root).once()

    assert len(calls) == 1 and calls[0][0] == "script_reviewer"
    _, instruction, context, schema = calls[0]
    draft = context["script_discussion"]["rounds"][-1]["script"]
    assert [item["segment_id"] for item in draft["segments"]] == segment_ids
    assert schema["$defs"]["ScriptCritiqueIssue"]["properties"]["segment_id"]["enum"] == ["", *segment_ids]
    assert "script_discussion.rounds[-1].script.segments" in instruction and "逐字" in instruction
    assert "全稿问题使用空字符串" in instruction and "不得使用范围" in instruction and "新 ID" in instruction
    # Each call narrows its own transport schema, without changing the shared contract.
    assert "enum" not in ScriptCritique.model_json_schema()["$defs"]["ScriptCritiqueIssue"]["properties"]["segment_id"]
    current = repo.get_job(job.job_id)
    assert current.script_discussion.status == "EXHAUSTED"
    assert current.script_discussion.rounds[0].critique.issues[0].segment_id == issue_id


@pytest.mark.parametrize("value", [
    {"decision": "APPROVE", "summary": "自相矛盾：通过但仍列问题。", "strengths": [],
     "issues": [{"segment_id": "s1", "category": "logic", "concern": "仍有问题。", "suggestion": "继续修改。"}]},
    {"decision": "REVISE", "summary": "自相矛盾：要求修改但无问题。", "strengths": [], "issues": []},
])
def test_contradictory_critique_contract_blocks_discussion(monkeypatch, tmp_path, value):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: value)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce",
                              "idempotency_key": "contradictory-critique-" + value["decision"]})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert "通过时不能保留未解决问题" in current.message or "要求修改必须指出具体问题" in current.message
    assert current.script_discussion.rounds[0].critique is None


def test_rewrite_with_fake_source_is_rejected_before_second_round(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        if role == "script_reviewer":
            return _critique("REVISE")
        rewrite = _rewrite()
        rewrite["script"]["segments"][0]["source_refs"] = ["https://fake-source.example/unit"]
        return rewrite

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "fake-source-rewrite"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert calls == ["script_reviewer", "screenwriter"]
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert "讨论改稿未通过来源检查" in current.message
    assert len(current.script_discussion.rounds) == 1
    assert current.script_discussion.rounds[0].critique.decision == "REVISE"


@pytest.mark.parametrize("narration", ["我建议先核对原始来源。", "事实：这个结论没有提供来源。"])
def test_rewrite_without_source_or_opinion_prefix_is_rejected(monkeypatch, tmp_path, narration):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        if role == "script_reviewer":
            return _critique("REVISE")
        rewrite = _rewrite()
        rewrite["script"]["segments"][0].update(narration=narration, source_refs=[])
        return rewrite

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "unmarked-rewrite"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert calls == ["script_reviewer", "screenwriter"]
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert "讨论改稿未通过来源检查" in current.message and "缺少事实来源" in current.message
    assert len(current.script_discussion.rounds) == 1
    assert current.script_discussion.rounds[0].critique.decision == "REVISE"
    assert current.script.segments[0].narration == job.brief.script_text


def test_script_discussion_honors_five_round_limit(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo, rounds=5)
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        return _critique("REVISE") if role == "script_reviewer" else _rewrite_with_narration(calls.count("screenwriter"))

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "five-rounds"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert current.script_discussion.max_rounds == 5
    assert current.script_discussion.status == "EXHAUSTED"
    assert len(current.script_discussion.rounds) == 5
    assert calls.count("script_reviewer") == 5
    assert calls.count("screenwriter") == 4


def test_paused_discussion_keeps_frozen_max_rounds_after_settings_change(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo, rounds=1, reviewer=False)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "freeze-rounds"})

    assert Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.script_discussion.max_rounds == 1

    SettingsService(repo).patch(SettingsPatch(script_discussion_max_rounds=5,
                                              role_models={"script_reviewer": {"enabled": True, "model": "unit-reviewer"}}))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: _critique("REVISE"))
    _resume(repo, paused, "freeze-rounds-resume")

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.script_discussion.max_rounds == 1
    assert current.script_discussion.status == "EXHAUSTED"
    assert len(current.script_discussion.rounds) == 1


def test_unknown_reviewer_submission_blocks_model_switch_resubmission(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo, reviewer=True)
    run_cli_calls = []

    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda provider: ["unit-cli"])

    def unknown(*args, **kwargs):
        run_cli_calls.append(args)
        raise CliFailure("submitted_without_result", submitted=True)

    monkeypatch.setattr("videoagents.providers.llm.run_cli", unknown)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "unknown-reviewer"})

    assert Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.stage == "script"
    assert paused.pending_input["operation_status"] == "UNKNOWN"
    assert len(run_cli_calls) == 1

    SettingsService(repo).patch(SettingsPatch(role_models={"script_reviewer": {"enabled": True, "model": "switched-model"}}))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("UNKNOWN operation was resubmitted"))
    _resume(repo, paused, "unknown-reviewer-resume")

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert current.pending_input["operation_status"] == "UNKNOWN"
    assert len(run_cli_calls) == 1


def test_model_approval_cannot_bypass_source_gate(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path, evidence=False)
    job.brief.source_urls = [SOURCE_URL]
    repo.update_job(job.job_id, job.revision, brief=job.brief)
    _enable_discussion(repo)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: _critique("APPROVE"))
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "source-gate"})

    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "script"
    assert current.script_discussion.status == "APPROVED"
    assert "真实证据图片" in current.message


def test_saved_writer_turn_replays_without_appending_or_recalls(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    command = _enqueue(repo, job, "writer-sql-before-checkpoint")
    original = __import__("videoagents.nodes.screenwriter", fromlist=["save_discussion"]).save_discussion
    calls = []

    def crash_after_save(repository, state, discussion):
        original(repository, state, discussion)
        raise SystemExit("UNIT TEST crash after writer SQL commit")

    monkeypatch.setattr("videoagents.nodes.screenwriter.save_discussion", crash_after_save)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: (calls.append(a[3]), _critique("APPROVE"))[1])
    with VideoProductionGraph(repo, service.project_root) as graph, pytest.raises(SystemExit):
        graph.execute(command)

    saved = repo.get_job(job.job_id)
    assert len(saved.script_discussion.rounds) == 1
    assert saved.script_discussion.rounds[0].critique is None

    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)

    current = repo.get_job(job.job_id)
    assert len(current.script_discussion.rounds) == 1
    assert current.script_discussion.rounds[0].critique.decision == "APPROVE"
    assert len(calls) == 1


def test_saved_rewrite_turn_replays_without_duplicate_writer_call(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    command = _enqueue(repo, job, "rewrite-sql-before-checkpoint")
    original = __import__("videoagents.nodes.screenwriter", fromlist=["save_discussion"]).save_discussion
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        if role == "script_reviewer" and calls.count("script_reviewer") == 1:
            return _critique("REVISE")
        if role == "screenwriter":
            return _rewrite()
        if role == "script_reviewer":
            return _critique("APPROVE")
        raise AssertionError(role)

    def crash_after_second_writer_save(repository, state, discussion):
        original(repository, state, discussion)
        if len(discussion.rounds) == 2 and discussion.rounds[-1].critique is None:
            raise SystemExit("UNIT TEST crash after rewrite SQL commit")

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    monkeypatch.setattr("videoagents.nodes.screenwriter.save_discussion", crash_after_second_writer_save)
    with VideoProductionGraph(repo, service.project_root) as graph, pytest.raises(SystemExit):
        graph.execute(command)

    saved = repo.get_job(job.job_id)
    assert len(saved.script_discussion.rounds) == 2
    assert saved.script_discussion.rounds[0].critique.decision == "REVISE"
    assert saved.script_discussion.rounds[1].critique is None

    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)

    current = repo.get_job(job.job_id)
    assert calls == ["script_reviewer", "screenwriter", "script_reviewer"]
    assert len(current.script_discussion.rounds) == 2
    assert current.script_discussion.status == "APPROVED"


def test_saved_reviewer_turn_replays_without_duplicate_review_call(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    command = _enqueue(repo, job, "reviewer-sql-before-checkpoint")
    original = __import__("videoagents.nodes.script_reviewer", fromlist=["save_discussion"]).save_discussion
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        return _critique("APPROVE")

    def crash_after_save(repository, state, discussion):
        original(repository, state, discussion)
        raise SystemExit("UNIT TEST crash after reviewer SQL commit")

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    monkeypatch.setattr("videoagents.nodes.script_reviewer.save_discussion", crash_after_save)
    with VideoProductionGraph(repo, service.project_root) as graph, pytest.raises(SystemExit):
        graph.execute(command)

    assert repo.get_job(job.job_id).script_discussion.rounds[0].critique.decision == "APPROVE"

    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)

    current = repo.get_job(job.job_id)
    assert calls == ["script_reviewer"]
    assert current.script_discussion.status == "APPROVED"


def test_new_revision_clears_old_discussion(tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    discussion = {"run_id": "old-run", "revision": job.revision, "enabled": True, "max_rounds": 2,
                  "status": "APPROVED", "rounds": [{"round": 1, "script": {
                      "title": "旧稿", "origin": "user", "revision": job.revision,
                      "segments": [{"segment_id": "s1", "narration": "事实：旧稿。", "screen_text": "",
                                    "source_refs": [SOURCE_URL], "asset_ids": ["asset-evidence"]}]},
                      "response": "", "critique": _critique("APPROVE")}]}
    repo.update_job(job.job_id, job.revision, script_discussion=ScriptDiscussion.model_validate(discussion))
    current = repo.get_job(job.job_id)
    request = {"base_revision": current.revision,
               "script": Script(title="人工新版", revision=current.revision, origin="user",
                                segments=[ScriptSegment(segment_id="s1", narration="事实：人工新版。",
                                                        source_refs=[SOURCE_URL], asset_ids=["asset-evidence"])])}

    result = service.draft(job.job_id, request=DraftRequest.model_validate(request))

    assert result.revision == 2
    assert result.script_discussion is None
    assert result.script.revision == 2


def test_automatic_rewrite_removes_old_media_and_reports_from_current_job(monkeypatch, tmp_path):
    repo, service, job = _job(tmp_path)
    _enable_discussion(repo)
    obsolete = {"preview", "final", "cover", "timeline", "review", "package", "captions", "storyboard"}
    artifacts = list(job.artifacts)
    for kind in obsolete:
        path = repo.root / f"unit-old-{kind}.bin"
        path.write_bytes(b"UNIT TEST old output metadata; not a real video")
        artifact = Artifact(artifact_id=f"unit-old-{kind}", kind=kind, name=path.name,
                            mime_type="application/octet-stream", size_bytes=path.stat().st_size,
                            sha256=sha256(path), url=f"/api/artifacts/unit-old-{kind}", revision=job.revision)
        repo.put_artifact(job.job_id, artifact, path)
        artifacts.append(artifact)
    repo.update_job(job.job_id, job.revision, script=Script.model_validate(_model_script()), artifacts=artifacts)
    reviews = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if role == "screenwriter":
            return _rewrite()
        reviews.append(context["script_discussion"]["rounds"][-1]["script"])
        current_kinds = {item.kind for item in repo.get_job(job_id).artifacts}
        if len(reviews) == 1:
            assert obsolete <= current_kinds  # Unchanged initial draft keeps valid media.
            return _critique("REVISE")
        assert not obsolete.intersection(current_kinds)
        return _critique("APPROVE")

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "old-media-rewrite"})
    assert Worker(repo, service.project_root).once()

    current = repo.get_job(job.job_id)
    assert current.revision == job.revision
    assert current.script_discussion.status == "APPROVED"
    assert not obsolete.intersection(item.kind for item in current.artifacts)
    assert current.assets == job.assets
    assert repo.artifact_path("unit-old-final")[0].read_bytes().startswith(b"UNIT TEST")
