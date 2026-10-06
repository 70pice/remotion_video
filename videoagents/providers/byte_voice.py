"""ByteDance HTTP streaming voice synthesis, guarded by a durable operation ledger.

Request ID is tracing metadata, not a promised supplier idempotency mechanism.
The official success terminator must be observed before accepting audio.
"""

import base64
import json
import uuid
from pathlib import Path
from typing import Any, Iterator

import httpx

from videoagents.providers.llm import CapabilityMissing
from videoagents.providers.network import public_transport
from videoagents.services.settings import SettingsService, voice_fingerprint
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from worker.process_manager import RenderCancelled


class SubmissionUnknown(CapabilityMissing):
    def __init__(self, message, fields=None, **kwargs):
        kwargs.setdefault("operation_status", "UNKNOWN")
        super().__init__(message, fields, **kwargs)


def decode_objects(chunks: Iterator[str]) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        if len(buffer) > 16 * 1024 * 1024:
            raise ValueError("字节响应块超过限制")
        while buffer.strip():
            buffer = buffer.lstrip()
            try:
                value, offset = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                break
            buffer = buffer[offset:]
            if not isinstance(value, dict):
                raise ValueError("字节响应必须为 JSON 对象")
            yield value
    if buffer.strip():
        raise ValueError("字节响应不完整")


def synthesize(repository: Repository, job_id: str, revision: int, text: str, command_id: str = "",
               cancelled=lambda: False, *, delivery_style: str = "", operation_key: str = "") -> dict[str, Any]:
    if cancelled():
        raise RenderCancelled("任务已取消")
    if not isinstance(operation_key, str) or len(operation_key) > 200:
        raise CapabilityMissing("配音操作键必须是最多 200 字的文本", ["voice_operation"])
    config = SettingsService(repository).internal()
    if config.get("voice_provider") == "byte_ws":
        from videoagents.providers.byte_ws_voice import synthesize as synthesize_ws
        options = {"delivery_style": delivery_style} if delivery_style else {}
        if operation_key:
            options["operation_key"] = operation_key
        return synthesize_ws(repository, job_id, revision, text, command_id, cancelled=cancelled, **options)
    for provider in ("byte_http", "byte_ws"):
        unsettled = repository.unsettled_operation(job_id, provider, revision)
        if unsettled:
            raise SubmissionUnknown("当前版本的配音提交状态未知；切换接口或音色不会重提，请对账或导入已取得音频", ["voice_operation"],
                                    operation_id=unsettled["operation_id"], request_id=unsettled.get("request_id"))
    if config.get("voice_style", "").strip() or delivery_style:
        raise CapabilityMissing("当前风格指导仅支持字节 WebSocket 的 seed-tts-2.0-expressive，请切换服务与模型", ["voice_provider", "voice_model", "voice_style"])
    if config.get("voice_speech_rate", 0):
        raise CapabilityMissing("当前语速设置仅接入字节 WebSocket，请切换服务或恢复默认语速", ["voice_provider", "voice_speech_rate"])
    if config.get("voice_provider") != "byte_http" or not config.get("voice_id") or not config.get("voice_resource_id"):
        raise CapabilityMissing("请配置你自己的字节复刻音色和匹配的资源 ID，或导入真实音频与实测时间轴", ["voice", "audio", "alignment"])
    if not config.get("voice_api_key") and not (config.get("voice_app_id") and config.get("voice_access_token")):
        raise CapabilityMissing("字节配音鉴权尚未配置", ["voice"])
    request_identity = {"text": text, "voice_id": config["voice_id"], "resource_id": config["voice_resource_id"],
                        "format": "mp3", "sample_rate": 24000}
    if operation_key:
        request_identity["operation_key"] = operation_key
    input_hash = fingerprint(request_identity)
    previous = repository.operation(job_id, input_hash, "byte_http")
    if previous:
        if previous["status"] == "COMPLETED" and Path(previous.get("path", "")).is_file():
            return {**previous, "voice_fingerprint": previous.get("voice_fingerprint", voice_fingerprint(config))}
        if previous["status"] != "REJECTED" or not command_id or previous.get("command_id") == command_id:
            raise SubmissionUnknown("此配音输入已有未决或失败提交，不能自动再次付费；请核对供应商记录或导入已取得的音频", ["voice_operation"],
                                    operation_status="UNKNOWN" if previous["status"] == "SUBMITTING" else previous["status"], operation_id=previous["operation_id"], request_id=previous.get("request_id"))
    repository.reserve_metric(job_id, revision, "voice_chars", len(text), config["max_voice_chars"])
    request_id = str(uuid.uuid4())
    operation_body = {"request_id": request_id, "command_id": command_id, "attempt": 1, "revision": revision}
    if operation_key:
        operation_body["operation_key"] = operation_key
    operation = repository.retry_rejected_operation(previous["operation_id"], command_id, operation_body) if previous else repository.start_operation(job_id, input_hash, "byte_http", operation_body)
    if not operation.get("new"):
        raise SubmissionUnknown("相同配音输入已由其他执行记录受理，请先对账", ["voice_operation"], operation_id=operation["operation_id"], request_id=operation.get("request_id"))
    headers = {"X-Api-Resource-Id": config["voice_resource_id"], "X-Api-Request-Id": request_id,
               "X-Control-Require-Usage-Tokens-Return": "*", "Content-Type": "application/json"}
    if config.get("voice_api_key"):
        headers["X-Api-Key"] = config["voice_api_key"]
    else:
        headers.update({"X-Api-App-Id": config["voice_app_id"], "X-Api-Access-Key": config["voice_access_token"]})
    request = {"user": {"uid": "videoagents-local"}, "req_params": {
        "text": text, "speaker": config["voice_id"], "audio_params": {
            "format": "mp3", "sample_rate": 24000, "enable_subtitle": True,
        },
    }}
    folder = repository.root / "jobs" / job_id / "operations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (operation["operation_id"] + ".mp3")
    received_success, sentences, usage, trace_id = False, [], None, None
    ledger = {"request_id": request_id, "command_id": command_id, "attempt": operation.get("attempt", 1), "revision": revision}
    audio_bytes = bytearray()
    try:
        with httpx.Client(timeout=httpx.Timeout(180, connect=15), trust_env=False, transport=public_transport()) as client:
            with client.stream("POST", config["voice_endpoint"], headers=headers, json=request) as response:
                trace_id = response.headers.get("x-tt-logid")
                ledger["provider_trace_id"] = trace_id
                if response.is_error:
                    uncertain = response.status_code >= 500 or response.status_code == 408
                    repository.finish_operation(operation["operation_id"], "UNKNOWN" if uncertain else "REJECTED", {**ledger, "http_status": response.status_code})
                    if uncertain:
                        raise SubmissionUnknown(f"字节返回 HTTP {response.status_code}，无法证明未受理；禁止自动重提", ["voice_operation"], operation_id=operation["operation_id"], request_id=request_id)
                    raise CapabilityMissing(f"字节拒绝提交（HTTP {response.status_code}），修正配置后可用新的显式命令重试", ["voice"])
                if config["voice_endpoint"].endswith("/sse"):
                    objects = (json.loads(line[5:].strip()) for line in response.iter_lines() if line.startswith("data:") and line[5:].strip())
                else:
                    objects = decode_objects(response.iter_text())
                for value in objects:
                    code = value.get("code")
                    if code == 20000000:
                        received_success, usage = True, value.get("usage")
                        break
                    if code not in (0, None):
                        # The documented nonzero final error terminates failure;
                        # retain the explicit supplier code for reconciliation.
                        repository.finish_operation(operation["operation_id"], "REJECTED", {**ledger, "provider_code": code})
                        raise CapabilityMissing(f"字节配音返回错误码 {code}，未接受为有效音频", ["voice"])
                    if value.get("data"):
                        audio_bytes.extend(base64.b64decode(value["data"], validate=True))
                        if len(audio_bytes) > 100 * 1024 * 1024:
                            raise ValueError("配音输出超过限制")
                    if value.get("sentence"):
                        sentences.append(value["sentence"])
        if not received_success or not audio_bytes:
            raise SubmissionUnknown("配音连接结束但未收到官方成功结束码，受理状态未知，禁止自动重提", ["voice_operation"], operation_id=operation["operation_id"], request_id=request_id)
        path.write_bytes(audio_bytes)
        result = {**ledger, "path": str(path), "sentences": sentences, "usage": usage,
                  "input_hash": input_hash, "origin": "byte_http", "voice_fingerprint": voice_fingerprint(config)}
        repository.finish_operation(operation["operation_id"], "COMPLETED", result)
        return result
    except CapabilityMissing:
        existing = repository.operation(job_id, input_hash, "byte_http")
        if existing and existing["status"] == "SUBMITTING":
            repository.finish_operation(operation["operation_id"], "UNKNOWN", ledger)
        raise
    except Exception as exc:
        repository.finish_operation(operation["operation_id"], "UNKNOWN", {**ledger, "reason": type(exc).__name__})
        raise SubmissionUnknown("配音提交后的网络或协议状态未知；已保留请求 ID，不会自动重复付费", ["voice_operation"], operation_id=operation["operation_id"], request_id=request_id) from exc
