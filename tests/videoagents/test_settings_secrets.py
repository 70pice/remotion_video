"""Secret storage behavior: keychain references and moved-DB degradation."""

import base64

from videoagents.services import settings as settings_module
from videoagents.services.settings import SecretUnavailable, protect, unprotect


def test_darwin_protect_stores_reference_and_reads_through_keychain(monkeypatch):
    monkeypatch.setattr(settings_module.sys, "platform", "darwin", raising=False)
    store: dict[str, str] = {}
    monkeypatch.setattr(settings_module, "_keychain_write", lambda account, value: store.__setitem__(account, value))
    monkeypatch.setattr(settings_module, "_keychain_read", lambda account: store[account])

    stored = protect("zhipu_api_key", "plain-secret")
    assert stored == "keychain:zhipu_api_key" and "plain-secret" not in stored
    assert unprotect("zhipu_api_key", stored) == "plain-secret"


def test_local_rows_still_readable_after_upgrade(monkeypatch):
    # Existing installs stored base64 rows; they must keep working everywhere.
    legacy = "local:" + base64.b64encode("old-secret".encode()).decode()
    assert unprotect("voice_api_key", legacy) == "old-secret"


def test_dpapi_row_on_other_platform_is_unavailable_not_fatal(monkeypatch):
    monkeypatch.setattr(settings_module.os, "name", "posix", raising=False)
    try:
        unprotect("zhipu_api_key", "dpapi:" + base64.b64encode(b"x").decode())
    except SecretUnavailable as exc:
        assert "原用户" in str(exc)
    else:
        raise AssertionError("expected SecretUnavailable")


def test_keychain_reference_on_other_platform_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings_module.sys, "platform", "linux", raising=False)
    try:
        unprotect("zhipu_api_key", "keychain:zhipu_api_key")
    except SecretUnavailable:
        pass
    else:
        raise AssertionError("expected SecretUnavailable")


def test_internal_skips_unreadable_secret_instead_of_crashing(tmp_path, monkeypatch):
    from videoagents.storage import Repository

    def unavailable(name, value):
        raise SecretUnavailable("credential unavailable on this machine")

    monkeypatch.setattr(settings_module, "unprotect", unavailable)
    repo = Repository(tmp_path)
    repo.write_settings({"zhipu_api_key": "dpapi:" + base64.b64encode(b"moved").decode()})
    service = settings_module.SettingsService(repo)
    internal = service.internal()
    # The unreadable row behaves like unset: no crash, no value, public flag off.
    assert "zhipu_api_key" not in internal or internal["zhipu_api_key"] == ""
    assert service.public()["zhipu_api_key_configured"] is False
