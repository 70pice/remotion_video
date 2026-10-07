"""Write-only credentials persisted with Windows DPAPI for this user's account."""

import base64
import ctypes
import json
import os
from copy import deepcopy
from ctypes import wintypes
from typing import Any

from videoagents.contracts import RoleModels, SettingsPatch
from videoagents.default_config import DEFAULT_SETTINGS, SECRET_FIELDS
from videoagents.providers.network import validate_url
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint


def voice_fingerprint(config: dict[str, Any]) -> str:
    identity = {"voice_id": config.get("voice_id"), "resource_id": config.get("voice_resource_id")}
    if config.get("voice_provider") == "byte_ws":
        identity.update(provider="byte_ws", model=config.get("voice_model"))
    else:
        identity["app_id"] = config.get("voice_app_id")
    style, rate = config.get("voice_style", "").strip(), config.get("voice_speech_rate", 0)
    if style or rate:
        # 空风格和默认语速保持旧指纹，兼容已有音频；新配置使旧配音失效。
        identity.update(style=style, speech_rate=rate)
    return fingerprint(identity)


def supports_voice_style(config: dict[str, Any]) -> bool:
    # standard 不保证应用 context_texts 的风格指导，不能声称已生效。
    return config.get("voice_provider") == "byte_ws" and config.get("voice_model") == "seed-tts-2.0-expressive"


def enforce_fixed_role_settings(role_models: dict[str, Any]) -> dict[str, Any]:
    roles = RoleModels.model_validate(role_models).model_dump()
    roles["voice"]["enabled"] = True
    return roles


def protect(value: str) -> str:
    if os.name != "nt":
        return "local:" + base64.b64encode(value.encode()).decode()
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    raw = value.encode("utf-8")
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, target = Blob(len(raw), buffer), Blob()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), "VideoAgents credential", None, None, None, 1, ctypes.byref(target)):
        raise OSError("Windows 凭据加密失败")
    try:
        return "dpapi:" + base64.b64encode(ctypes.string_at(target.pbData, target.cbData)).decode()
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def unprotect(value: str) -> str:
    kind, raw = value.split(":", 1)
    data = base64.b64decode(raw)
    if kind == "local":
        return data.decode("utf-8")
    if os.name != "nt":
        raise OSError("Windows 保护的凭据只能由原用户恢复")
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), buffer), Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError("无法读取当前用户的 Windows 凭据")
    try:
        return ctypes.string_at(target.pbData, target.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


class SettingsService:
    def __init__(self, repository: Repository):
        self.repo = repository

    def internal(self) -> dict[str, Any]:
        result = deepcopy(DEFAULT_SETTINGS)
        stored = self.repo.setting_values()
        for key, value in stored.items():
            if key in {"llm_api_key", "llm_base_url", "llm_model"}:
                # Preserve old encrypted rows without decrypting unused HTTP
                # credentials, including after moving a DB to another user.
                continue
            result[key] = unprotect(value) if key in SECRET_FIELDS else json.loads(value)
        # 新 WebSocket 制作默认原速；旧 HTTP 不支持该参数，也沿用原速。
        if result["voice_provider"] == "byte_http" and "voice_speech_rate" not in stored:
            result["voice_speech_rate"] = 0
        for key in SECRET_FIELDS:
            if key == "llm_api_key":
                continue
            env_name = "VIDEOAGENTS_" + key.upper()
            if os.getenv(env_name):
                result[key] = os.environ[env_name]
        result["role_models"] = enforce_fixed_role_settings(result["role_models"])
        return result

    def public(self) -> dict[str, Any]:
        settings = self.internal()
        from videoagents.providers.cli_runner import cli_availability
        from videoagents.tools.research import platform_catalog
        from videoagents.tools.research_skills import research_skill_catalog
        result = {key: settings[key] for key in DEFAULT_SETTINGS}
        tools = platform_catalog(settings)
        result.update({
            "llm_configured": any(value["enabled"] for value in settings["role_models"].values()),
            "ark_api_key_configured": bool(settings.get("ark_api_key")),
            "cli_availability": cli_availability(),
            "search_configured": (settings.get("search_provider") == "opencli_google" and any(
                item["id"] == "google" and item["status"] in {"native_installed", "native_ready"} for item in tools)) or bool(settings.get("search_api_key")) and (
                settings.get("search_provider") == "tavily" or (
                    settings.get("search_provider") == "google_cse" and bool(settings.get("google_search_engine_id")))),
            "research_tools": tools,
            "research_skills": research_skill_catalog(),
            "voice_api_key_configured": bool(settings.get("voice_api_key")),
            "voice_access_token_configured": bool(settings.get("voice_access_token")),
            "voice_configured": settings.get("voice_provider") in {"byte_http", "byte_ws"}
            and bool(settings.get("voice_id")) and bool(settings.get("voice_resource_id")) and bool(
                settings.get("voice_api_key") or (settings.get("voice_provider") == "byte_http"
                                                 and settings.get("voice_app_id") and settings.get("voice_access_token"))),
            "aligner_configured": bool(settings.get("aligner_url")),
        })
        return result

    def patch(self, patch: SettingsPatch) -> dict[str, Any]:
        values = patch.model_dump(exclude_none=True, exclude_unset=True)
        values.pop("script_discussion_enabled", None)
        if "role_models" in values:
            roles = self.internal()["role_models"]
            for role, updates in values["role_models"].items():
                roles[role].update(updates)
            values["role_models"] = enforce_fixed_role_settings(roles)
        for key in {"aligner_url"}:
            if values.get(key):
                validate_url(values[key], local_provider=True)
        if "voice_endpoint" in values or "voice_provider" in values:
            voice = {**self.internal(), **values}
            ws_endpoint = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
            http_endpoints = {"https://openspeech.bytedance.com/api/v3/tts/unidirectional",
                              "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"}
            if "voice_endpoint" not in values:
                if voice["voice_provider"] == "byte_ws" and voice["voice_endpoint"] != ws_endpoint:
                    values["voice_endpoint"] = ws_endpoint
                elif voice["voice_provider"] == "byte_http" and voice["voice_endpoint"] not in http_endpoints:
                    values["voice_endpoint"] = DEFAULT_SETTINGS["voice_endpoint"]
                voice.update(values)
            allowed = {ws_endpoint} if voice["voice_provider"] == "byte_ws" else http_endpoints
            if voice["voice_provider"] == "none":
                allowed |= {ws_endpoint}
            if voice["voice_endpoint"] not in allowed:
                raise ValueError("字节接口必须使用与所选配音服务匹配的官方 HTTP 或 WebSocket 地址")
        self.repo.write_settings({key: protect(value) if key in SECRET_FIELDS else json.dumps(value, ensure_ascii=False)
                                  for key, value in values.items()})
        if os.name != "nt":
            os.chmod(self.repo.db, 0o600)
            for suffix in ("-wal", "-shm"):
                path = self.repo.db.with_name(self.repo.db.name + suffix)
                if path.exists():
                    os.chmod(path, 0o600)
        return self.public()
