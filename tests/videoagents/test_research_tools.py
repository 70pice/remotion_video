import sys

import httpx
import pytest

from videoagents.contracts import Brief, SettingsPatch
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools.research import PLATFORM_CATALOG, discover, platform_catalog
from worker.process_manager import RenderCancelled


def test_platform_catalog_is_honest_about_indexed_and_login_bound_tools(tmp_path):
    repo = Repository(tmp_path / "runtime")
    catalog = platform_catalog(SettingsService(repo).internal())
    ids = {item["id"] for item in PLATFORM_CATALOG}

    assert {"web", "google", "x", "youtube", "zhihu", "reddit", "bilibili", "xiaohongshu", "github", "wikimedia"} <= ids
    assert next(item for item in catalog if item["id"] == "reddit")["status"] in {"login_required", "search_unconfigured"}
    assert next(item for item in catalog if item["id"] == "zhihu")["detail"]


def test_discover_uses_site_filtered_search_and_keeps_partial_failures(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    calls = []
    monkeypatch.setattr("videoagents.tools.research._command_prefix", lambda name: None)

    def fake_search(repository, query, job_id="", revision=1, *, domains=None, limit=5):
        calls.append((query, tuple(domains or ()), limit))
        if domains and "reddit.com" in domains:
            raise RuntimeError("unit failure")
        return {"results": [
            {"url": "https://www.youtube.com/watch?v=unit", "title": "Muse", "content": "视频资料"},
            {"url": "https://evil.example/not-youtube", "title": "Bad", "content": "wrong host"},
        ], "images": [{"url": "https://i.ytimg.com/unit.jpg", "source_url": "https://www.youtube.com/watch?v=unit",
                       "description": "thumbnail"}]}

    monkeypatch.setattr("videoagents.tools.research.search", fake_search)
    result = discover(repo, "Muse是什么", ["youtube", "reddit"], job_id=job.job_id,
                      revision=job.revision, per_platform=2, max_searches=4)

    assert calls[0][1] == ("youtube.com", "youtu.be")
    assert result["results"] == [{
        "url": "https://www.youtube.com/watch?v=unit", "title": "Muse", "snippet": "视频资料",
        "platform": "youtube", "backend": "tavily",
        "images": [{"url": "https://i.ytimg.com/unit.jpg", "source_url": "https://www.youtube.com/watch?v=unit",
                    "description": "thumbnail"}],
    }]
    assert any(item["platform"] == "reddit" and item["status"] == "error" and item["results_count"] == 0
               for item in result["tools"])


def test_opencli_google_searches_platform_through_site_filtered_index(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="opencli_google", research_platforms=["zhihu"]))
    job = repo.create_job(Brief(topic="Muse是什么"))
    calls = []
    monkeypatch.setattr("videoagents.tools.research._command_prefix", lambda name: ["unit-opencli"] if name == "opencli" else None)

    def fake_google(query, limit, *args):
        calls.append((query, limit))
        return [
            {"url": "https://www.zhihu.com/question/unit", "title": "Muse 是什么", "snippet": "知乎资料", "platform": "google", "backend": "opencli", "images": []},
            {"url": "https://example.com/not-zhihu", "title": "Bad", "snippet": "wrong host", "platform": "google", "backend": "opencli", "images": []},
        ]

    monkeypatch.setattr("videoagents.tools.research._google", fake_google)
    result = discover(repo, "Muse是什么", ["zhihu"], job_id=job.job_id,
                      revision=job.revision, per_platform=2, max_searches=4)

    assert calls == [("Muse是什么 (site:zhihu.com)", 2)]
    assert result["results"] == [{
        "url": "https://www.zhihu.com/question/unit", "title": "Muse 是什么", "snippet": "知乎资料",
        "platform": "zhihu", "backend": "opencli_google_indexed", "images": [],
    }]
    assert result["tools"] == [{"platform": "zhihu", "backend": "opencli_google_indexed", "status": "ok", "results_count": 1}]



def test_discover_counts_native_failure_and_fallback_against_budget(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="opencli_google"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    google_calls = []
    monkeypatch.setattr("videoagents.tools.research._command_prefix",
                        lambda name: ["unit-cli"] if name in {"yt-dlp", "opencli"} else None)

    def fail_youtube(*args, **kwargs):
        raise RuntimeError("unit native failure")

    def fake_google(*args, **kwargs):
        google_calls.append(args)
        return []

    import videoagents.tools.research as research

    monkeypatch.setitem(research.NATIVE_HANDLERS, "youtube", ("yt-dlp", fail_youtube))
    monkeypatch.setattr("videoagents.tools.research._google", fake_google)
    result = discover(repo, "Muse是什么", ["youtube", "zhihu"], job_id=job.job_id,
                      revision=job.revision, per_platform=2, max_searches=1)

    assert google_calls == []
    assert result["tools"] == [
        {"platform": "youtube", "backend": "yt-dlp", "status": "error", "results_count": 0,
         "error": "RuntimeError"},
        {"platform": "youtube", "backend": "opencli_google_indexed", "status": "skipped",
         "results_count": 0, "error": "search_budget_exhausted"},
        {"platform": "zhihu", "backend": "opencli_google_indexed", "status": "skipped",
         "results_count": 0, "error": "search_budget_exhausted"},
    ]


def test_discover_only_attaches_images_with_explicit_or_nested_ownership(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    monkeypatch.setattr("videoagents.tools.research._command_prefix", lambda name: None)

    def fake_search(*args, **kwargs):
        return {
            "results": [
                {"url": "https://example.com/a", "title": "A", "content": "A",
                 "images": [{"url": "https://img.example.com/nested.jpg", "description": "nested"}]},
                {"url": "https://example.com/b", "title": "B", "content": "B"},
            ],
            "images": [
                {"url": "https://img.example.com/no-owner.jpg", "description": "global no owner"},
                {"url": "https://img.example.com/wrong.jpg", "source_url": "https://example.com/other",
                 "description": "wrong owner"},
                {"url": "https://img.example.com/a.jpg", "source_url": "https://example.com/a",
                 "description": "owned a"},
            ],
        }

    monkeypatch.setattr("videoagents.tools.research.search", fake_search)
    result = discover(repo, "Muse是什么", ["web"], job_id=job.job_id,
                      revision=job.revision, per_platform=2, max_searches=1)

    assert result["results"][0]["images"] == [
        {"url": "https://img.example.com/nested.jpg", "source_url": "https://example.com/a", "description": "nested"},
        {"url": "https://img.example.com/a.jpg", "source_url": "https://example.com/a", "description": "owned a"},
    ]
    assert result["results"][1]["images"] == []
    assert {image["url"] for image in result["images"]} == {"https://img.example.com/nested.jpg",
                                                              "https://img.example.com/a.jpg"}


def test_native_cancellation_is_not_reported_as_platform_failure(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="opencli_google"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    monkeypatch.setattr("videoagents.tools.research._command_prefix", lambda name: ["unit-opencli"] if name == "opencli" else None)
    monkeypatch.setattr("videoagents.tools.research._google", lambda *args, **kwargs: (_ for _ in ()).throw(RenderCancelled("unit")))

    with pytest.raises(RenderCancelled):
        discover(repo, "Muse是什么", ["zhihu"], job_id=job.job_id,
                 revision=job.revision, per_platform=1, max_searches=1)


def test_native_cli_rejects_dash_prefixed_query_before_launch(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="opencli_google"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    monkeypatch.setattr("videoagents.tools.research._command_prefix", lambda name: ["unit-opencli"] if name == "opencli" else None)

    result = discover(repo, "-Muse", ["zhihu"], job_id=job.job_id,
                      revision=job.revision, per_platform=1, max_searches=1)

    assert result["tools"] == [{"platform": "zhihu", "backend": "opencli_google_indexed", "status": "error",
                                "results_count": 0, "error": "CapabilityMissing"}]


def test_partial_native_hits_leave_budget_for_next_platform(tmp_path, monkeypatch):
    import videoagents.tools.research as research

    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="opencli_google"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    monkeypatch.setattr(research, "_command_prefix", lambda name: ["unit"] if name == "opencli" else None)
    calls = []

    def google(query, *args):
        calls.append(query)
        return [{"url": "https://example.com/muse", "title": "Muse", "snippet": "", "images": [],
                 "platform": "google", "backend": "opencli"}]

    monkeypatch.setitem(research.NATIVE_HANDLERS, "google", ("opencli", google))
    monkeypatch.setattr(research, "_google", google)
    data = discover(repo, "Muse是什么", ["google", "reddit"], job_id=job.job_id,
                    revision=1, per_platform=3, max_searches=2)
    assert len(calls) == 2
    assert "site:reddit.com" in calls[1]
    assert not any(item["status"] == "skipped" for item in data["tools"])


def test_native_empty_google_does_not_repeat_identical_backend(tmp_path, monkeypatch):
    import videoagents.tools.research as research

    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="opencli_google"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    monkeypatch.setattr(research, "_command_prefix", lambda name: ["unit"] if name == "opencli" else None)
    calls = []
    monkeypatch.setitem(research.NATIVE_HANDLERS, "google", ("opencli", lambda *a: calls.append(a) or []))
    data = discover(repo, "Muse是什么", ["google"], job_id=job.job_id, revision=1, max_searches=4)
    assert len(calls) == 1
    assert len(data["tools"]) == 1


def test_native_process_is_stopped_on_cancel(tmp_path, monkeypatch):
    import videoagents.tools.research as research

    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="Muse是什么"))
    original = research.subprocess.Popen
    processes = []

    def start(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        repo.update_job(job.job_id, job.revision, status="CANCELLED")
        return process

    monkeypatch.setattr(research.subprocess, "Popen", start)
    with pytest.raises(RenderCancelled):
        research._run([sys.executable, "-c", "import time; time.sleep(30)"], repository=repo, job_id=job.job_id)
    assert processes[0].poll() is not None


@pytest.mark.parametrize("status", ["UNKNOWN", "SUBMITTING"])
def test_search_unknown_scope_survives_limit_changes_without_blocking_other_platforms(tmp_path, monkeypatch, status):
    from videoagents.providers.llm import CapabilityMissing
    from videoagents.providers.search import search
    from videoagents.storage.repository import fingerprint

    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret"))
    job = repo.create_job(Brief(topic="Muse是什么"))
    ledger = {"revision": 1, "search_scope": fingerprint({"query": "Muse是什么", "domains": ["reddit.com"]})}
    op = repo.start_operation(job.job_id, "old-limit-fingerprint", "tavily", ledger)
    repo.finish_operation(op["operation_id"], status, ledger)
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(200, json={"results": [], "images": []})

    monkeypatch.setattr("videoagents.providers.search.public_transport", lambda: httpx.MockTransport(handler))
    with pytest.raises(CapabilityMissing, match="未决提交"):
        search(repo, "Muse是什么", job.job_id, domains=["reddit.com"], limit=5)
    assert calls == []
    assert search(repo, "Muse是什么", job.job_id, domains=["zhihu.com"], limit=2)["results"] == []
    assert calls == ["api.tavily.com"]
