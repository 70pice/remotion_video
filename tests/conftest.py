"""Shared test fixtures."""

import pytest

from videoagents.services import settings as settings_module


@pytest.fixture(autouse=True)
def fake_keychain(monkeypatch):
    """Never touch the real macOS Keychain from tests.

    ``protect`` on darwin writes secrets into the login keychain via the
    ``security`` CLI. Tests that PATCH settings through the API would otherwise
    create real keychain items on the developer's machine.
    """
    store: dict[str, str] = {}
    monkeypatch.setattr(settings_module, "_keychain_write", lambda account, value: store.__setitem__(account, value))

    def read(account: str) -> str:
        if account not in store:
            raise settings_module.SecretUnavailable(f"钥匙串中没有凭据 {account} 或当前用户无法读取；请重新保存")
        return store[account]

    monkeypatch.setattr(settings_module, "_keychain_read", read)
    yield store
