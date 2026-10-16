"""Claude materials research uses fixed capabilities and job-owned files only."""

import hashlib
import io
import json
import os
import socket
import subprocess
import sys

import pytest

from videoagents.contracts import Brief, MaterialResearch, SettingsPatch
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools import claude_research as research

SOURCE = "https://evidence.example/article"
IMAGE = "https://evidence.example/photo.png"
PNG = b"\x89PNG\r\n\x1a\n" + b"image-test" * 10


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="AI 与普通人的生活"))
    workspace = repo.root / "jobs" / job.job_id / "revisions" / "1" / "skills-research"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))])
    return research.ResearchBridge(workspace, repo.root, job.job_id, job.revision)


def fetch_source(monkeypatch, bridge):
    calls = []

    def download(url, **kwargs):
        calls.append(url)
        return ("<title>真实案例</title><p>读取到的正文。</p><script>隐藏代码</script>"
                '<img src="/photo.png" alt="案例画面">').encode(), "text/html", url

    monkeypatch.setattr("videoagents.tools.sources.safe_get", download)
    result = bridge.call("source", {"url": SOURCE, "platform": "web"})
    return result, calls


def media_probe(monkeypatch, *, width=64, height=48):
    def probe(_path):
        return {"streams": [{"codec_type": "video", "width": width, "height": height,
                             "avg_frame_rate": "30/1", "duration": "12.5"}],
                "format": {"duration": "12.5"}}

    monkeypatch.setattr(research, "probe", probe)
    monkeypatch.setattr("videoagents.tools.media.probe", probe)


def test_source_saves_parsed_utf8_text_with_real_digest_and_contract(bridge, monkeypatch):
    result, calls = fetch_source(monkeypatch, bridge)
    path = bridge.workspace / result["source"]["text_file"]
    assert "读取到的正文" in path.read_text(encoding="utf-8")
    assert "<p>" not in path.read_text(encoding="utf-8")
    assert "隐藏代码" not in path.read_text(encoding="utf-8")
    assert result["source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["images"] == [{"url": IMAGE, "source_url": SOURCE, "description": "案例画面"}]
    MaterialResearch(sources=[result["source"]], visuals=[], limitations=[])
    assert bridge.call("source", {"url": SOURCE, "platform": "web"}) == result
    assert calls == [SOURCE]
    assert len(list(bridge.workspace.iterdir())) == 1


@pytest.mark.parametrize("url", ["http://127.0.0.1/config", "https://localhost/config", "https://u:p@example.com/",
                                  "file:///C:/secret", "https://example.com/a#fragment"])
def test_source_rejects_unsafe_urls_before_fetch(bridge, monkeypatch, url):
    monkeypatch.setattr(research, "fetch_source", lambda *_: pytest.fail("must not fetch"))
    with pytest.raises(ValueError):
        bridge.call("source", {"url": url, "platform": "web"})


def test_source_rejects_dns_private_address(bridge, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.7", 443))])
    monkeypatch.setattr(research, "fetch_source", lambda *_: pytest.fail("must not fetch"))
    with pytest.raises(ValueError, match="私网"):
        bridge.call("source", {"url": SOURCE, "platform": "web"})


@pytest.mark.parametrize("relative", ["../other", "nested", "../../outside"])
def test_workspace_must_match_owned_job_revision(bridge, relative):
    with pytest.raises(ValueError, match="workspace"):
        research.ResearchBridge(bridge.workspace / relative, bridge.runtime, bridge.job_id, bridge.revision)


def test_workspace_symlink_cannot_redirect_writes(bridge, tmp_path):
    bridge.workspace.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        bridge.workspace.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable for this Windows account")
    with pytest.raises(ValueError, match="linked"):
        bridge.call("skill", {"name": "agent-reach"})
    assert list(outside.iterdir()) == []


def test_generated_files_reject_linked_existing_entries(bridge, tmp_path):
    target = tmp_path / "secret"
    target.write_text("not a research output", encoding="utf-8")
    try:
        (bridge.workspace / "linked.txt").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable for this Windows account")
    with pytest.raises(ValueError, match="linked"):
        bridge._space(1)
    assert target.read_text(encoding="utf-8") == "not a research output"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
@pytest.mark.parametrize("ancestor", [False, True])
def test_windows_junction_cannot_redirect_workspace_or_parent(bridge, tmp_path, ancestor):
    bridge.workspace.rmdir()
    path = bridge.workspace
    outside = tmp_path / "outside-junction"
    outside.mkdir()
    if ancestor:
        bridge.workspace.parent.rmdir()
        bridge.workspace.parent.parent.rmdir()
        path = bridge.workspace.parent.parent.parent
        path.rmdir()
        (outside / "revisions" / "1" / "skills-research").mkdir(parents=True)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(outside)],
                            capture_output=True, timeout=5, check=False)
    assert result.returncode == 0, "could not create Windows test junction"
    try:
        with pytest.raises(ValueError, match="linked"):
            bridge.call("skill", {"name": "agent-reach"})
        assert not list(outside.rglob("*.txt"))
    finally:
        # rmdir removes only this known junction, without traversing its target.
        path.rmdir()


def test_source_cap_and_download_cap_are_enforced(bridge, monkeypatch):
    bridge.settings["research_max_sources"] = 1
    fetch_source(monkeypatch, bridge)
    with pytest.raises(ValueError, match="source_budget"):
        bridge.call("source", {"url": "https://evidence.example/second", "platform": "web"})
    monkeypatch.setattr(research, "MAX_WORKSPACE_BYTES", 1)
    with pytest.raises(ValueError, match="download_budget"):
        bridge._space(0)


@pytest.mark.parametrize("arguments", [{"name": "../../secret"}, {"name": "agent-reach", "path": "secret"}])
def test_skill_cannot_choose_path_or_read_unknown_guide(bridge, arguments):
    with pytest.raises(ValueError):
        bridge.call("skill", arguments)


def test_skill_reads_only_catalogue_entry(bridge, tmp_path, monkeypatch):
    path = tmp_path / "SKILL.md"
    path.write_text("只读检索指南", encoding="utf-8")
    monkeypatch.setattr(research, "research_skill_catalog", lambda: [
        {"name": "agent-reach", "installed": True, "path": str(path)}])
    assert bridge.call("skill", {"name": "agent-reach"}) == {"name": "agent-reach", "guidance": "只读检索指南"}


def test_search_native_failure_and_fallback_share_cumulative_configured_budget(bridge, monkeypatch):
    from videoagents.tools import research as discovery

    SettingsService(bridge.repo).patch(SettingsPatch(search_provider="tavily", search_api_key="test-search-key",
                                                    research_platforms=["youtube"], research_max_searches=2))
    bridge.settings = SettingsService(bridge.repo).internal()
    monkeypatch.setattr(discovery, "_command_prefix", lambda name: ["test-yt-dlp"] if name == "yt-dlp" else None)
    monkeypatch.setitem(discovery.NATIVE_HANDLERS, "youtube", ("yt-dlp", lambda *_: (_ for _ in ()).throw(RuntimeError())))
    calls = []

    def search(_repo, query, _job, _revision, *, domains, limit):
        calls.append((query, domains, limit))
        return {"results": [{"url": "https://www.youtube.com/watch?v=test", "title": "真实采访"}]}

    monkeypatch.setattr(discovery, "search", search)
    result = bridge.call("search", {"query": "真实采访", "platforms": ["youtube"]})
    assert calls == [("真实采访", ["youtube.com", "youtu.be"], bridge.settings["research_results_per_platform"])]
    assert [item["status"] for item in result["tools"]] == ["error", "ok"]
    assert bridge.searches == 2
    with pytest.raises(ValueError, match="search_budget"):
        bridge.call("search", {"query": "更多采访", "platforms": ["youtube"]})
    with pytest.raises(ValueError, match="platform_disabled"):
        bridge.call("search", {"query": "更多采访", "platforms": ["reddit"]})
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["cancel", "revision"])
def test_inactive_job_prevents_network_and_file_changes(bridge, monkeypatch, change):
    job = bridge.repo.get_job(bridge.job_id)
    if change == "cancel":
        bridge.repo.update_job(job.job_id, job.revision, status="CANCELLED")
    else:
        bridge.repo.edit_job(job.job_id, job.revision, lambda item: item.model_copy(update={"revision": 2}))
    monkeypatch.setattr(research, "fetch_source", lambda *_: pytest.fail("must not fetch"))
    with pytest.raises(ValueError, match="inactive"):
        bridge.call("source", {"url": SOURCE, "platform": "web"})
    assert list(bridge.workspace.iterdir()) == []


def test_cancellation_during_source_fetch_does_not_publish_partial_text(bridge, monkeypatch):
    def fetch(_url, path):
        path.write_text("raw evidence", encoding="utf-8")
        bridge.repo.update_job(bridge.job_id, bridge.revision, status="CANCELLED")
        return {"text": "parsed evidence", "title": "case", "images": [], "final_url": SOURCE}

    monkeypatch.setattr(research, "fetch_source", fetch)
    with pytest.raises(ValueError, match="inactive"):
        bridge.call("source", {"url": SOURCE, "platform": "web"})
    assert list(bridge.workspace.iterdir()) == []


def test_visual_requires_read_source_then_returns_real_file_manifest(bridge, monkeypatch):
    monkeypatch.setattr(research, "safe_get", lambda *_args, **_kwargs: (PNG, "image/png", IMAGE))
    media_probe(monkeypatch)
    args = {"source_url": SOURCE, "url": IMAGE, "kind": "image", "description": "支撑案例结果的原图"}
    with pytest.raises(ValueError, match="source_not_read"):
        bridge.call("visual", args)
    source, _ = fetch_source(monkeypatch, bridge)
    result = bridge.call("visual", args)
    path = bridge.workspace / result["visual"]["file"]
    assert path.read_bytes() == PNG
    assert result["visual"]["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert result["metadata"] == {"width": 64, "height": 48}
    MaterialResearch(sources=[source["source"]], visuals=[result["visual"]], limitations=[])
    bridge.settings["research_download_images"] = False
    with pytest.raises(ValueError, match="images_disabled"):
        bridge.call("visual", args)


def test_video_has_actual_probed_duration_and_honest_direct_mp4_requirement(bridge, monkeypatch):
    fetch_source(monkeypatch, bridge)
    media_probe(monkeypatch)
    data = b"\0\0\0\x20ftypisom" + b"test-video" * 4
    monkeypatch.setattr(research, "safe_get", lambda *_args, **_kwargs: (data, "video/mp4", SOURCE))
    result = bridge.call("visual", {"source_url": SOURCE, "url": SOURCE + ".mp4", "kind": "video",
                                    "description": "实际操作过程；可用区间需摄影结合内容确认"})
    assert result["metadata"] == {"duration_seconds": 12.5, "width": 64, "height": 48, "frame_rate": 30.0}
    assert result["visual"]["media_url"] == SOURCE + ".mp4"
    monkeypatch.setattr(research, "safe_get", lambda *_args, **_kwargs: (b"<html>video link only</html>", "text/html", SOURCE))
    with pytest.raises(ValueError):
        bridge.call("visual", {"source_url": SOURCE, "url": SOURCE, "kind": "video", "description": "视频页面"})
    assert len(list(bridge.workspace.iterdir())) == 2


def test_invalid_image_is_removed_and_screenshot_respects_switch(bridge, monkeypatch):
    fetch_source(monkeypatch, bridge)
    monkeypatch.setattr(research, "safe_get", lambda *_args, **_kwargs: (PNG, "image/png", IMAGE))
    media_probe(monkeypatch, width=1)
    with pytest.raises(ValueError, match="decodable"):
        bridge.call("visual", {"source_url": SOURCE, "url": IMAGE, "kind": "image", "description": "证据图"})
    assert len(list(bridge.workspace.iterdir())) == 1
    media_probe(monkeypatch)
    bridge.settings["capture_enabled"] = False
    monkeypatch.setattr(research, "capture_source", lambda *_: pytest.fail("must not capture"))
    with pytest.raises(ValueError, match="screenshots_disabled"):
        bridge.call("screenshot", {"source_url": SOURCE, "description": "新闻页面"})
    bridge.settings["capture_enabled"] = True
    monkeypatch.setattr(research, "capture_source", lambda _url, path: path.write_bytes(PNG))
    result = bridge.call("screenshot", {"source_url": SOURCE, "description": "新闻页面"})
    assert result["visual"]["kind"] == "screenshot"
    assert result["visual"]["sha256"] == hashlib.sha256(PNG).hexdigest()


def rpc(method, identity=1, params=None):
    value = {"jsonrpc": "2.0", "method": method, "id": identity}
    if params is not None:
        value["params"] = params
    return json.dumps(value, ensure_ascii=False).encode() + b"\n"


def tool_result(bridge, name, arguments):
    output = io.StringIO()
    incoming = rpc("initialize") + rpc("tools/call", 2, {"name": name, "arguments": arguments})
    research.serve(bridge, io.BytesIO(incoming), output)
    return json.loads(output.getvalue().splitlines()[-1])["result"]


@pytest.mark.parametrize("failure", ["skill", "platform", "search_budget", "inactive"])
def test_stdio_known_failures_identify_safe_code_and_specific_recovery(bridge, monkeypatch, failure):
    if failure == "skill":
        monkeypatch.setattr(research, "research_skill_catalog", lambda: [])
        name, arguments = "skill", {"name": "missing-skill"}
        code, recovery_terms = "research_skill_unavailable", ["search", "source"]
    elif failure == "platform":
        bridge.settings["research_platforms"] = ["web"]
        name, arguments = "search", {"query": "公开证据", "platforms": ["reddit"]}
        code, recovery_terms = "research_platform_disabled", ["configured", "platforms"]
    elif failure == "search_budget":
        bridge.searches = bridge.settings["research_max_searches"]
        name, arguments = "search", {"query": "公开证据", "platforms": ["web"]}
        code, recovery_terms = "research_search_budget_exhausted", ["Stop", "limitations"]
    else:
        bridge.repo.update_job(bridge.job_id, bridge.revision, status="CANCELLED")
        name, arguments = "source", {"url": SOURCE, "platform": "web"}
        code, recovery_terms = "inactive_research_revision", ["Stop", "revision"]
    result = tool_result(bridge, name, arguments)
    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload["error_code"] == code
    assert all(term in payload["recovery"] for term in recovery_terms)
    assert not list(bridge.workspace.iterdir())


@pytest.mark.parametrize("error", [ValueError("arbitrary-secret"),
                                  ValueError("research_skill_unavailable", "arbitrary-secret"),
                                  ValueError("research_search_budget_exhausted\narbitrary-secret"),
                                  RuntimeError("research_skill_unavailable"),
                                  RuntimeError("research_skill_unavailable arbitrary-secret")])
def test_stdio_unknown_exception_args_never_become_error_codes_or_recovery(bridge, monkeypatch, error):
    def fail(*_args):
        raise error
    monkeypatch.setattr(bridge, "call", fail)
    result = tool_result(bridge, "source", {})
    payload = json.loads(result["content"][0]["text"])
    assert payload["error_code"] == "research_tool_failed"
    assert "arbitrary-secret" not in json.dumps(result)
    assert "ValueError" not in json.dumps(result) and "RuntimeError" not in json.dumps(result)


def test_writer_bridge_advertises_only_read_tools_and_rejects_visual_collection(bridge, monkeypatch):
    writer = research.ResearchBridge(bridge.workspace, bridge.runtime, bridge.job_id, bridge.revision,
                                     allowed_tools={"skill", "search", "source"})
    assert writer.tool_names == {"skill", "search", "source"}
    monkeypatch.setattr(research, "safe_get", lambda *a, **k: pytest.fail("must not download"))
    result = tool_result(writer, "visual", {"source_url": SOURCE, "url": IMAGE,
                                          "kind": "image", "description": "禁止下载"})
    assert result["isError"] is True
    assert json.loads(result["content"][0]["text"])["error_code"] == "unknown_research_tool"
    assert not list(bridge.workspace.iterdir())


def test_stdio_sanitizes_errors_and_does_not_emit_tool_prints(bridge, monkeypatch):
    secret = "test-secret-must-not-appear"

    def bad_call(*_args):
        print(secret)
        raise RuntimeError(secret)

    monkeypatch.setattr(bridge, "call", bad_call)
    output = io.StringIO()
    incoming = (rpc("initialize", params={"protocolVersion": "2025-11-25"})
                + b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
                + rpc("tools/list", 2) + rpc("tools/call", 3, {"name": "source", "arguments": {}}))
    research.serve(bridge, io.BytesIO(incoming), output)
    assert secret not in output.getvalue()
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(responses) == 3
    assert {item["name"] for item in responses[1]["result"]["tools"]} == research.TOOL_NAMES
    assert responses[-1]["result"]["isError"] is True


def test_stdio_drains_oversized_frame_and_requires_initialization(bridge):
    output = io.StringIO()
    incoming = (b"x" * (research.MAX_MESSAGE_BYTES + 100) + b"\n" + rpc("tools/list")
                + rpc("initialize", 2, {"protocolVersion": "unknown"}) + rpc("unknown", 3))
    research.serve(bridge, io.BytesIO(incoming), output)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [item.get("error", {}).get("code") for item in responses] == [-32700, -32000, None, -32601]
    assert responses[2]["result"]["protocolVersion"] == "2025-11-25"


def test_stdio_invalid_json_and_params_are_protocol_errors(bridge):
    output = io.StringIO()
    incoming = b"{invalid-json\n" + rpc("initialize", 2, [])
    research.serve(bridge, io.BytesIO(incoming), output)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [item["error"]["code"] for item in responses] == [-32700, -32602]


@pytest.mark.parametrize("character", ["\U0001f600", "\x01"])
def test_bounded_long_source_survives_utf8_file_and_single_cli_event(bridge, monkeypatch, character):
    from videoagents.providers.cli_runner import MAX_EVENT_BYTES
    from videoagents.tools.sources import MAX_SOURCE_TEXT_CHARS

    text = character * MAX_SOURCE_TEXT_CHARS
    monkeypatch.setattr("videoagents.tools.sources.safe_get", lambda *_args, **_kwargs:
                        (f"<p>{text}</p>".encode(), "text/html", SOURCE))
    output = io.StringIO()
    incoming = (rpc("initialize", params={"protocolVersion": "2025-11-25"})
                + rpc("tools/call", 2, {"name": "source", "arguments": {"url": SOURCE, "platform": "web"}}))

    research.serve(bridge, io.BytesIO(incoming), output)

    response = json.loads(output.getvalue().splitlines()[-1])
    content = response["result"]["content"]
    payload = json.loads(content[0]["text"])
    path = bridge.workspace / payload["source"]["text_file"]
    assert payload["text"] == text
    assert path.read_text(encoding="utf-8") == text
    assert path.stat().st_size <= 1024 * 1024
    assert payload["source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    event = {"type": "user", "message": {"content": [{"type": "tool_result", "content": content}]}}
    assert len(json.dumps(event, ensure_ascii=False).encode()) < MAX_EVENT_BYTES


def test_real_module_startup_and_tools_list_are_stdio_only(bridge):
    result = subprocess.run([sys.executable, "-m", "videoagents.tools.claude_research", "--workspace", str(bridge.workspace),
                             "--runtime", str(bridge.runtime), "--job-id", bridge.job_id, "--revision", str(bridge.revision)],
                            input=rpc("initialize", params={"protocolVersion": "2025-03-26"}) + rpc("tools/list", 2),
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[0]["result"]["protocolVersion"] == "2025-03-26"
    assert {item["name"] for item in responses[1]["result"]["tools"]} == research.TOOL_NAMES
