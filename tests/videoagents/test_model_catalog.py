"""Read-only local catalog fixtures; no model generation or credential reads."""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from videoagents.providers import model_catalog
from videoagents.providers.model_catalog import ModelCatalogService, read_codex_models, read_trae_models

CACHE_TIME = "2026-10-03T07:00:00Z"


def choice(slug="fixture-model", *, hidden=False, default=False):
    return {"slug": slug, "display_name": "Fixture " + slug, "description": "Local cache fixture",
            "visibility": "hide" if hidden else "list", "is_default": default}


def write_cache(path, models=None, *, fetched_at=CACHE_TIME):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": fetched_at, "client_version": "unit-fixture-different-version",
                               "models": [choice()] if models is None else models}, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def local_cache(tmp_path, monkeypatch):
    home = tmp_path / "isolated-codex-cache"
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setattr(model_catalog, "executable_prefix", lambda provider: ["unit-fixture-never-executed"])
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("fixture CLI has no catalog command")
    monkeypatch.setattr(subprocess, "run", unavailable)
    return home / "models_cache.json"


def test_active_cli_catalog_wins_over_cache_written_by_older_client(local_cache, monkeypatch):
    write_cache(local_cache, [choice("old-client-model")])
    calls = []
    def query(arguments, **kwargs):
        calls.append(arguments)
        assert kwargs["timeout"] <= 15
        assert kwargs.get("shell", False) is False
        return subprocess.CompletedProcess(arguments, 0, json.dumps({"models": [
            choice("gpt-6.1-sol"), choice("gpt-reserve", hidden=True),
        ]}).encode(), b"")
    monkeypatch.setattr(subprocess, "run", query)
    service = ModelCatalogService(cache_seconds=300)
    first = service.get("codex_cli", refresh=True)
    assert [item.id for item in first.models] == ["gpt-6.1-sol", "gpt-reserve"]
    assert first.models[1].hidden is True
    assert "CLI" in first.message and "查询" in first.message
    assert calls == [["unit-fixture-never-executed", "debug", "models"]]
    write_cache(local_cache, [choice("overwritten-again")])
    assert service.get("codex_cli").models[0].id == "gpt-6.1-sol"
    assert len(calls) == 1
    assert service.get("codex_cli", refresh=True).models[0].id == "gpt-6.1-sol"
    assert len(calls) == 2


def test_trae_catalog_uses_models_json_and_preserves_exact_model_id(monkeypatch):
    calls = []

    def query(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, json.dumps([
            {
                "name": "Doubao-Seed-2.1-Pro",
                "real_name": "Seed-2.1-Pro",
                "provider": "trae",
                "description": "184K context window, support reasoning.",
                "context_window": 184000,
                "supported_mime_types": ["image/*"],
            },
        ]).encode(), b"")

    monkeypatch.setattr(subprocess, "run", query)
    models, fetched_at = read_trae_models(["traecli"])
    assert [item.id for item in models] == ["Doubao-Seed-2.1-Pro"]
    assert models[0].display_name == "Seed-2.1-Pro"
    assert models[0].description == "184K context window, support reasoning."
    assert datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert calls == [["traecli", "models", "--json", "-c", "hooks.state={}"]]


def test_trae_catalog_service_does_not_fall_back_to_codex_cache(local_cache, monkeypatch):
    write_cache(local_cache, [choice("must-not-leak")])
    monkeypatch.setattr(model_catalog, "executable_prefix", lambda provider: ["traecli"])
    monkeypatch.setattr(model_catalog, "read_trae_models", lambda prefix: (
        [model_catalog.ModelChoice(
            id="Doubao-Seed-2.1-Pro", display_name="Seed-2.1-Pro",
            description="short-video model",
        )],
        CACHE_TIME,
    ))
    result = ModelCatalogService().get("trae_cli", refresh=True)
    assert result.status == "ready"
    assert [item.id for item in result.models] == ["Doubao-Seed-2.1-Pro"]
    assert "TRAE CLI" in result.message


@pytest.mark.parametrize("failure", [
    subprocess.TimeoutExpired(["fixture", "debug", "models"], 12),
    subprocess.CalledProcessError(1, ["fixture", "debug", "models"], stderr=b"private-token"),
])
def test_cli_query_failure_falls_back_to_cache_without_exposing_errors(local_cache, monkeypatch, failure):
    write_cache(local_cache)
    def query(*args, **kwargs):
        raise failure
    monkeypatch.setattr(subprocess, "run", query)
    result = ModelCatalogService().get("codex_cli", refresh=True)
    assert result.status == "ready" and result.models[0].id == "fixture-model"
    assert result.fetched_at == CACHE_TIME
    assert "回退" in result.message and "缓存" in result.message
    assert "private-token" not in result.model_dump_json()


@pytest.mark.parametrize("output", [b"not-json", b"{}", b"[]", b"x" * (4 * 1024 * 1024 + 1)],
                         ids=["malformed", "missing-models", "wrong-root", "oversized"])
def test_invalid_cli_catalog_falls_back_to_valid_cache(local_cache, monkeypatch, output):
    write_cache(local_cache)
    monkeypatch.setattr(subprocess, "run", lambda arguments, **kwargs:
                        subprocess.CompletedProcess(arguments, 0, output, b""))
    result = ModelCatalogService().get("codex_cli", refresh=True)
    assert result.status == "ready" and result.models[0].id == "fixture-model"
    assert "回退" in result.message


def test_cache_preserves_hidden_opaque_models_and_first_duplicate(tmp_path):
    path = tmp_path / "models_cache.json"
    opaque = "future/provider:model ;$(ignored) 中文"
    first = choice(opaque, hidden=True)
    first.pop("is_default")  # Missing default is never inferred from position.
    first["description"] = None  # Nullable in the official cache shape.
    entries = [first, choice("listed-default", default=True)]
    entries.extend(choice("future-model-" + str(index), hidden=index % 2 == 0) for index in range(8))
    duplicate = dict(first, display_name="Duplicate must not replace first", visibility="list")
    write_cache(path, entries + [duplicate])
    models, fetched_at = read_codex_models(path)
    assert len(models) == 10
    assert [item.id for item in models] == [item["slug"] for item in entries]
    assert models[0].id == opaque and models[0].hidden is True
    assert models[0].display_name == first["display_name"] and models[0].is_default is False
    assert models[0].description == ""
    assert models[1].is_default is True and models[1].hidden is False
    assert datetime.fromisoformat(fetched_at.replace("Z", "+00:00")) == datetime.fromisoformat(CACHE_TIME.replace("Z", "+00:00"))


@pytest.mark.parametrize("visibility", ["future-unlisted", None])
def test_nonlisted_visibility_is_retained_as_hidden(tmp_path, visibility):
    entry = choice("opaque-unrecognized")
    if visibility is None:
        entry.pop("visibility")
    else:
        entry["visibility"] = visibility
    path = write_cache(tmp_path / "models_cache.json", [entry])
    models, _ = read_codex_models(path)
    assert len(models) == 1 and models[0].id == "opaque-unrecognized" and models[0].hidden is True


@pytest.mark.parametrize("invalid", [
    {}, {"slug": "bad", "display_name": None, "visibility": "list"},
    dict(choice(), slug=""), dict(choice("valid-first"), is_default="false"),
])
def test_invalid_row_rejects_entire_catalog_instead_of_partial_success(tmp_path, invalid):
    path = write_cache(tmp_path / "models_cache.json", [choice("valid-first"), invalid])
    with pytest.raises((ValueError, OSError)):
        read_codex_models(path)


@pytest.mark.parametrize("timestamp", ["not-an-ISO-time", "2026-10-03", "2026-10-03T07:00:00", "2026-10-03T15:00:00+08:00", 42])
def test_cache_timestamp_must_be_explicit_utc(tmp_path, timestamp):
    path = write_cache(tmp_path / "models_cache.json", fetched_at=timestamp)
    with pytest.raises((ValueError, OSError)):
        read_codex_models(path)


@pytest.mark.parametrize("contents", [b"not JSON", b"[]", b'{"fetched_at":"2026-10-03T07:00:00Z","models":{}}'])
def test_corrupt_root_fails_closed(tmp_path, contents):
    path = tmp_path / "models_cache.json"
    path.write_bytes(contents)
    with pytest.raises((ValueError, OSError)):
        read_codex_models(path)


def test_missing_file_and_oversized_cache_fail_closed(tmp_path):
    path = tmp_path / "models_cache.json"
    with pytest.raises((ValueError, OSError)):
        read_codex_models(path)
    # A valid JSON file just beyond 4 MiB proves this is a size boundary,
    # independent of malformed JSON validation.
    text = json.dumps({"fetched_at": CACHE_TIME, "models": [choice()]})
    path.write_bytes(text.encode() + b" " * (4 * 1024 * 1024 + 1 - len(text.encode())))
    with pytest.raises((ValueError, OSError)):
        read_codex_models(path)


def test_service_cache_refresh_reloads_without_replacing_cache_timestamp(local_cache):
    write_cache(local_cache, [choice("before-refresh")])
    service = ModelCatalogService(cache_seconds=300)
    first = service.get("codex_cli")
    assert first.status == "ready" and first.models[0].id == "before-refresh"
    assert first.fetched_at == CACHE_TIME
    later = "2026-10-03T08:00:00Z"
    write_cache(local_cache, [choice("after-refresh", hidden=True)], fetched_at=later)
    unchanged = service.get("codex_cli")
    assert unchanged.models[0].id == "before-refresh" and unchanged.fetched_at == CACHE_TIME
    refreshed = service.get("codex_cli", refresh=True)
    assert refreshed.models[0].id == "after-refresh" and refreshed.models[0].hidden is True
    assert refreshed.fetched_at == later
    assert "缓存" in refreshed.message
    assert "权限" in refreshed.message and "CLI" in refreshed.message


def test_unavailable_error_and_other_provider_are_sanitized(local_cache, monkeypatch):
    service = ModelCatalogService(cache_seconds=300)
    absent = service.get("codex_cli")
    assert absent.status == "unavailable" and absent.models == []
    write_cache(local_cache)
    valid = service.get("codex_cli", refresh=True)
    assert valid.status == "ready"
    private = "private raw exception D:\\private\\auth.json secret-token"
    def fail(*args):
        raise OSError(private)
    monkeypatch.setattr(model_catalog, "read_codex_models", fail)
    error = service.get("codex_cli", refresh=True)
    assert error.status == "error" and error.models == []
    assert private not in error.model_dump_json() and "secret-token" not in error.message
    assert str(local_cache) not in error.message
    # Claude has no automatic cache catalog and must not inherit Codex entries.
    claude = service.get("claude_code_cli", refresh=True)
    assert claude.provider == "claude_code_cli" and claude.status == "unavailable" and claude.models == []
    monkeypatch.setattr(model_catalog, "executable_prefix", lambda _: None)
    missing_cli = service.get("codex_cli", refresh=True)
    assert missing_cli.status == "unavailable" and missing_cli.models == []


def test_deeply_nested_json_returns_sanitized_error_without_partial_models(local_cache):
    local_cache.parent.mkdir(parents=True)
    local_cache.write_bytes(b"[" * 1500 + b"0" + b"]" * 1500)
    result = ModelCatalogService().get("codex_cli", refresh=True)
    assert result.status == "error" and result.models == []
    assert "RecursionError" not in result.message and str(local_cache) not in result.message


def test_returned_catalog_mutation_does_not_poison_cached_results(local_cache):
    write_cache(local_cache)
    service = ModelCatalogService(cache_seconds=300)
    original = service.get("codex_cli")
    original.models.clear()
    again = service.get("codex_cli")
    assert [model.id for model in again.models] == ["fixture-model"]


def test_catalog_never_opens_auth_config_or_launches_generation(local_cache, monkeypatch):
    write_cache(local_cache)
    for name in ("auth.json", "config.toml"):
        (local_cache.parent / name).write_text("test-only-sensitive-file", encoding="utf-8")
    original_open = Path.open
    def read_only_catalog(path, *args, **kwargs):
        assert path.name not in {"auth.json", "config.toml"}, "catalog tried to read account/config data"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", read_only_catalog)
    monkeypatch.setattr("videoagents.providers.cli_runner.run_cli", lambda *a, **k: pytest.fail("catalog attempted paid generation"))
    result = ModelCatalogService().get("codex_cli", refresh=True)
    assert result.status == "ready" and result.models[0].id == "fixture-model"
