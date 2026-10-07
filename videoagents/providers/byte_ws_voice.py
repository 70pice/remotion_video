"""Official bidirectional TTS frames with durable, conservative replay barriers.

Protocol: https://docs.volcengine.com/docs/DoubaoVoice/bidirectional-streaming-text-to-speech-websocket
Only a matched SessionFinished plus audio completes synthesis. Decodability,
text coverage and voice quality are checked by the downstream media pipeline.
"""

import http.client
import ipaddress
import json
import logging
import math
import os
import queue
import re
import socket
import ssl
import struct
import subprocess
import threading
import time
import uuid
import zlib
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable

from websockets.sync.client import connect

from videoagents.providers.byte_voice import SubmissionUnknown
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.settings import SettingsService, supports_voice_style, voice_fingerprint
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from worker.process_manager import RenderCancelled

ENDPOINT = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
HOST = "openspeech.bytedance.com"
_TUN_FAKE_NETWORK = ipaddress.ip_network("198.18.0.0/15")
_DOH_HOST = "cloudflare-dns.com"
_DOH_BOOTSTRAP_IP = "1.1.1.1"
_DOH_QUERY = "/dns-query?name=openspeech.bytedance.com&type=A"
_MAX_DOH_BYTES = 16 * 1024
CONNECT_TIMEOUT = 15.0
TOTAL_TIMEOUT = 180.0
RECV_POLL = 0.2
CLOSE_TIMEOUT = 1.0
MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_AUDIO_BYTES = 100 * 1024 * 1024
MAX_WIRE_BYTES = 128 * 1024 * 1024
MAX_SUBTITLE_WORDS = 20000
SUCCESS_CODE = 20000000
_LOGGER = logging.Logger("videoagents.byte_ws.transport", level=logging.CRITICAL + 1)
_LOGGER.disabled = True
_LOGGER.propagate = False


class Event(IntEnum):
    START_CONNECTION = 1
    FINISH_CONNECTION = 2
    CONNECTION_STARTED = 50
    CONNECTION_FAILED = 51
    CONNECTION_FINISHED = 52
    START_SESSION = 100
    CANCEL_SESSION = 101
    FINISH_SESSION = 102
    SESSION_STARTED = 150
    SESSION_CANCELLED = 151
    SESSION_FINISHED = 152
    SESSION_FAILED = 153
    USAGE_RESPONSE = 154
    TASK_REQUEST = 200
    SENTENCE_START = 350
    SENTENCE_END = 351
    AUDIO = 352
    SUBTITLE = 364


class ProtocolError(ValueError):
    pass


class ProviderError(ProtocolError):
    def __init__(self, code: int | None = None):
        super().__init__("provider_rejected_session")
        self.code = code


@dataclass(frozen=True)
class Frame:
    event: Event | None
    payload: dict[str, Any] | bytes
    session_id: str | None = None
    connection_id: str | None = None
    error_code: int | None = None


def encode_request(event: Event, payload: dict[str, Any], session_id: str | None = None) -> bytes:
    if not isinstance(payload, dict):
        raise ProtocolError("non_object_request")
    if event not in {Event.START_CONNECTION, Event.FINISH_CONNECTION, Event.START_SESSION,
                     Event.CANCEL_SESSION, Event.FINISH_SESSION, Event.TASK_REQUEST}:
        raise ProtocolError("invalid_client_event")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(body) > MAX_FRAME_BYTES - 1024:
        raise ProtocolError("request_size_limit")
    frame = b"\x11\x14\x10\x00" + struct.pack(">i", int(event))
    if event not in {Event.START_CONNECTION, Event.FINISH_CONNECTION}:
        if not session_id or len(session_id.encode("utf-8")) > 256:
            raise ProtocolError("invalid_session_id")
        identifier = session_id.encode("utf-8")
        frame += struct.pack(">I", len(identifier)) + identifier
    elif session_id is not None:
        raise ProtocolError("connection_event_has_session")
    return frame + struct.pack(">I", len(body)) + body


def _inflate(payload: bytes) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    result = decoder.decompress(payload, MAX_FRAME_BYTES + 1)
    if len(result) > MAX_FRAME_BYTES or decoder.unconsumed_tail:
        raise ProtocolError("decompressed_size_limit")
    result += decoder.flush(MAX_FRAME_BYTES + 1 - len(result))
    if len(result) > MAX_FRAME_BYTES or not decoder.eof or decoder.unused_data:
        raise ProtocolError("invalid_compressed_payload")
    return result


def _invalid_constant(_value):
    raise ProtocolError("invalid_json_number")


def decode_server(data: bytes) -> Frame:
    if not isinstance(data, bytes) or not 4 <= len(data) <= MAX_FRAME_BYTES:
        raise ProtocolError("invalid_binary_frame_size")
    if data[0] != 0x11 or data[3] != 0:
        raise ProtocolError("unsupported_protocol_header")
    message_type, flags = data[1] >> 4, data[1] & 15
    serialization, compression = data[2] >> 4, data[2] & 15
    if compression not in {0, 1}:
        raise ProtocolError("unsupported_compression")
    offset = 4
    def number(signed=False):
        nonlocal offset
        if offset + 4 > len(data):
            raise ProtocolError("truncated_frame")
        value = struct.unpack_from(">i" if signed else ">I", data, offset)[0]
        offset += 4
        return value
    def block(maximum):
        nonlocal offset
        length = number()
        if length > maximum or offset + length > len(data):
            raise ProtocolError("invalid_frame_length")
        value = data[offset:offset + length]
        offset += length
        return value
    event, session_id, connection_id, error_code = None, None, None, None
    if message_type == 15 and flags == 0 and serialization == 1:
        error_code = number()
    elif message_type in {9, 11} and flags == 4:
        try:
            event = Event(number(signed=True))
        except ValueError:
            raise ProtocolError("unknown_server_event") from None
        allowed = {Event.CONNECTION_STARTED, Event.CONNECTION_FAILED, Event.CONNECTION_FINISHED,
                   Event.SESSION_STARTED, Event.SESSION_CANCELLED, Event.SESSION_FINISHED, Event.SESSION_FAILED,
                   Event.USAGE_RESPONSE, Event.SENTENCE_START, Event.SENTENCE_END, Event.SUBTITLE}
        if message_type == 11:
            if event != Event.AUDIO or serialization != 0:
                raise ProtocolError("invalid_audio_event")
        elif event not in allowed or serialization != 1:
            raise ProtocolError("invalid_full_server_event")
        try:
            identifier = block(256).decode("utf-8")
        except UnicodeError:
            raise ProtocolError("invalid_identifier_utf8") from None
        if not identifier:
            raise ProtocolError("empty_server_identifier")
        if event in {Event.CONNECTION_STARTED, Event.CONNECTION_FAILED, Event.CONNECTION_FINISHED}:
            connection_id = identifier
        else:
            session_id = identifier
    else:
        raise ProtocolError("unsupported_server_message")
    payload = block(MAX_FRAME_BYTES)
    if offset != len(data):
        raise ProtocolError("trailing_frame_bytes")
    if compression == 1:
        try:
            payload = _inflate(payload)
        except zlib.error:
            raise ProtocolError("invalid_compressed_payload") from None
    if serialization == 1:
        try:
            payload = json.loads(payload, parse_constant=_invalid_constant)
        except (UnicodeError, json.JSONDecodeError, RecursionError):
            raise ProtocolError("invalid_json_payload") from None
        if not isinstance(payload, dict):
            raise ProtocolError("non_object_payload")
    return Frame(event, payload, session_id, connection_id, error_code)


def _check_cancelled(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise RenderCancelled("配音任务已取消")


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("voice_deadline")
    return remaining


def _resolve_doh_public_ips(deadline: float) -> list[str]:
    """Resolve only the fixed vendor host; never accept TUN placeholder IPs.

    This runs inside the bounded daemon resolver. Literal bootstrap and TLS
    hostname verification avoid depending on the intercepted system DNS again.
    No settings, credentials or narration are passed to this public query.
    """
    raw_socket, tls_socket, client, response = None, None, None, None
    try:
        raw_socket = socket.create_connection((_DOH_BOOTSTRAP_IP, 443), timeout=_remaining(deadline))
        raw_socket.settimeout(_remaining(deadline))
        tls_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=_DOH_HOST)
        client = http.client.HTTPConnection(_DOH_HOST, 443, timeout=_remaining(deadline))
        client.sock = tls_socket
        tls_socket.settimeout(_remaining(deadline))
        client.request("GET", _DOH_QUERY, headers={"Accept": "application/dns-json", "Connection": "close"})
        tls_socket.settimeout(_remaining(deadline))
        response = client.getresponse()
        # HTTPConnection does not follow redirects or consult proxy settings.
        if response.status != 200 or response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/dns-json":
            raise OSError("public_dns_invalid_response")
        body = bytearray()
        # HTTPResponse can close the TLS socket after its final body chunk
        # when Connection: close is used. Do not set a timeout on that closed
        # socket merely to perform another EOF read (WinError 10038).
        while not response.isclosed():
            tls_socket.settimeout(_remaining(deadline))
            chunk = response.read1(min(4096, _MAX_DOH_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > _MAX_DOH_BYTES:
                raise OSError("public_dns_response_limit")
        _remaining(deadline)
        payload = json.loads(body, parse_constant=_invalid_constant)
        if not isinstance(payload, dict) or type(payload.get("Status")) is not int or payload["Status"] != 0:
            raise OSError("public_dns_failed")
        if "TC" in payload and payload["TC"] is not False:
            raise OSError("public_dns_truncated_response")
        questions = payload.get("Question")
        if not isinstance(questions, list) or len(questions) != 1 or not isinstance(questions[0], dict):
            raise OSError("public_dns_question_mismatch")
        question = questions[0]
        if not isinstance(question.get("name"), str) or question["name"].removesuffix(".").lower() != HOST or type(question.get("type")) is not int or question["type"] != 1:
            raise OSError("public_dns_question_mismatch")
        answers = payload.get("Answer")
        if not isinstance(answers, list) or not answers:
            raise OSError("public_dns_empty_answer")
        ips = []
        for answer in answers:
            if not isinstance(answer, dict) or type(answer.get("type")) is not int:
                raise OSError("public_dns_invalid_answer")
            if answer["type"] == 5 and isinstance(answer.get("data"), str) and answer["data"]:
                continue  # An A query can include the actual CNAME chain.
            if answer["type"] != 1 or not isinstance(answer.get("data"), str):
                raise OSError("public_dns_invalid_answer")
            address = ipaddress.IPv4Address(answer["data"])
            if not address.is_global:
                raise OSError("non_public_destination")
            ips.append(str(address))
        if not ips:
            raise OSError("public_dns_empty_answer")
        return list(dict.fromkeys(ips))
    except (ValueError, RecursionError, http.client.HTTPException):
        raise OSError("public_dns_invalid_response") from None
    finally:
        for resource in (response, client, tls_socket, raw_socket):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass


def _resolve_public_ips(deadline: float, cancelled: Callable[[], bool]) -> list[str]:
    # getaddrinfo has no portable timeout. A daemon resolver holds only the
    # fixed hostname, never request headers, and cannot hold process exit open.
    results = queue.Queue(maxsize=1)
    def resolve():
        try:
            addresses = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
            ips = list(dict.fromkeys(address[4][0] for address in addresses))
            parsed = [ipaddress.ip_address(ip) for ip in ips]
            if parsed and all(address in _TUN_FAKE_NETWORK for address in parsed):
                ips = _resolve_doh_public_ips(deadline)
            if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
                raise OSError("non_public_destination")
            results.put((ips, None))
        except Exception as exc:
            results.put((None, type(exc).__name__))
    threading.Thread(target=resolve, name="byte-public-dns", daemon=True).start()
    while True:
        _check_cancelled(cancelled)
        try:
            ips, error = results.get(timeout=min(RECV_POLL, _remaining(deadline)))
            break
        except queue.Empty:
            continue
    if error:
        raise OSError("public_dns_failed")
    return ips


def _windows_physical_interface(deadline: float, cancelled: Callable[[], bool]) -> int | None:
    """只读查询有默认路由的物理网卡，不修改系统代理、TUN 或路由表。"""
    if os.name != "nt":
        return None
    _check_cancelled(cancelled)
    timeout = min(3.0, _remaining(deadline))
    command = (
        "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
        "$physical=@(Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} "
        "| Select-Object -ExpandProperty ifIndex); "
        "$routes=@(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' "
        "| Where-Object {$_.InterfaceIndex -in $physical} "
        "| Sort-Object @{Expression={$_.RouteMetric + $_.InterfaceMetric}}); "
        "if ($routes.Count -gt 0) {$routes[0].InterfaceIndex}"
    )
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                shell=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                encoding="ascii", check=True, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError, UnicodeError):
        _check_cancelled(cancelled)
        _remaining(deadline)
        return None
    _check_cancelled(cancelled)
    _remaining(deadline)
    value = result.stdout.strip()
    return int(value) if len(value) <= 8 and value.isascii() and value.isdecimal() and 0 < int(value) < 2 ** 24 else None


def _open_websocket(headers: dict[str, str], deadline: float, cancelled: Callable[[], bool]):
    connect_deadline = min(deadline, time.monotonic() + CONNECT_TIMEOUT)
    ips = _resolve_public_ips(connect_deadline, cancelled)
    raw_socket = None
    for ip in ips:
        _check_cancelled(cancelled)
        try:
            raw_socket = socket.create_connection((ip, 443), timeout=_remaining(connect_deadline))
            break
        except OSError:
            continue
    if raw_socket is None:
        raise OSError("public_connection_failed")
    connection = None
    def handshake():
        _check_cancelled(cancelled)
        return connect(ENDPOINT, sock=raw_socket, ssl=ssl.create_default_context(), server_hostname=HOST,
                       proxy=None, compression=None, additional_headers=headers,
                       open_timeout=_remaining(connect_deadline), close_timeout=CLOSE_TIMEOUT,
                       ping_interval=None, max_size=MAX_FRAME_BYTES, max_queue=4, logger=_LOGGER)
    try:
        try:
            connection = handshake()
        except ssl.SSLEOFError:
            # 某些 Windows TUN 在带官方域名的 TLS 握手时立即断开。
            # 仅为这个官方公网 IPv4 socket 选物理出口，再试一次连接；
            # 不放宽证书校验，不重试鉴权失败，也不重发任何配音正文。
            raw_socket.close()
            interface = _windows_physical_interface(connect_deadline, cancelled)
            if interface is None or ipaddress.ip_address(ip).version != 4:
                raise
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Winsock IP_UNICAST_IF=31，接口索引必须用网络字节序 DWORD。
            raw_socket.setsockopt(socket.IPPROTO_IP, 31, struct.pack("!I", interface))
            raw_socket.settimeout(_remaining(connect_deadline))
            _check_cancelled(cancelled)
            raw_socket.connect((ip, 443))
            connection = handshake()
        # Bound writes as well as reads. An idle socket timeout is conservative
        # failure, never permission to resubmit a text-bearing session.
        connection.socket.settimeout(min(CONNECT_TIMEOUT, _remaining(deadline)))
        return connection
    except Exception:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        else:
            raw_socket.close()
        raise


def _provider_code(payload: dict) -> int | None:
    value = payload.get("status_code")
    return value if type(value) is int else None


def _assert_success_status(frame: Frame) -> None:
    if frame.error_code is not None:
        raise ProviderError(frame.error_code)
    if isinstance(frame.payload, dict) and "status_code" in frame.payload:
        if _provider_code(frame.payload) != SUCCESS_CODE:
            raise ProviderError(_provider_code(frame.payload))


def _sentence(payload: dict[str, Any]) -> dict[str, Any] | None:
    words = payload.get("words")
    if not isinstance(words, list) or not words:
        return None
    result = []
    previous = 0.0
    for item in words:
        if not isinstance(item, dict) or not isinstance(item.get("word"), str) or not item["word"]:
            return None
        start, end = item.get("startTime"), item.get("endTime")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (start, end)):
            return None
        if start < previous or end <= start:
            return None
        word = {"word": item["word"], "startTime": start, "endTime": end}
        if "confidence" in item:
            confidence = item["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                return None
            word["confidence"] = confidence
        result.append(word)
        previous = end
    sentence = {"words": result}
    if isinstance(payload.get("text"), str):
        sentence["text"] = payload["text"]
    return sentence


def _trace_id(connection) -> str | None:
    response = getattr(connection, "response", None)
    value = response.headers.get("x-tt-logid") if response is not None else None
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,256}", value) else None


def _cleanup(connection, connection_id: str | None, session_id: str, session_started: bool, finish_sent: bool) -> None:
    # Cleanup never reclassifies a completed 152. Cancel is resource release,
    # not supplier-side refund or idempotency evidence.
    try:
        stream = getattr(connection, "socket", None)
        if stream is not None:
            stream.settimeout(CLOSE_TIMEOUT)
        if session_started and not finish_sent:
            connection.send(encode_request(Event.CANCEL_SESSION, {}, session_id))
        if connection_id:
            connection.send(encode_request(Event.FINISH_CONNECTION, {}))
            deadline = time.monotonic() + CLOSE_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    frame = decode_server(connection.recv(timeout=min(RECV_POLL, _remaining(deadline))))
                except TimeoutError:
                    continue
                if frame.event == Event.CONNECTION_FINISHED and frame.connection_id == connection_id:
                    break
    except Exception:
        pass
    finally:
        try:
            connection.close()
        except Exception:
            pass


def synthesize(repository: Repository, job_id: str, revision: int, text: str, command_id: str = "",
               cancelled: Callable[[], bool] = lambda: False, *, delivery_style: str = "",
               operation_key: str = "") -> dict[str, Any]:
    _check_cancelled(cancelled)
    if not isinstance(operation_key, str) or len(operation_key) > 200:
        raise CapabilityMissing("配音操作键必须是最多 200 字的文本", ["voice_operation"])
    config = dict(SettingsService(repository).internal())
    if config.get("voice_provider") != "byte_ws" or config.get("voice_endpoint") != ENDPOINT:
        raise CapabilityMissing("请选择字节 WebSocket 配音及官方接口地址", ["voice"])
    if not config.get("voice_api_key") or not config.get("voice_id") or not config.get("voice_resource_id"):
        raise CapabilityMissing("请配置 API Key、自有复刻音色和匹配的资源 ID", ["voice"])
    command_id = command_id or repository.active_command_id(job_id)
    for provider in ("byte_ws", "byte_http"):
        unsettled = repository.unsettled_operation(job_id, provider, revision)
        if unsettled:
            raise SubmissionUnknown("本版本已有未决配音提交，切换接口或音色不会再次提交；请对账或导入真实音频", ["voice_operation"],
                                    operation_id=unsettled["operation_id"], request_id=unsettled.get("request_id"))
    if not isinstance(text, str) or not text.strip():
        raise CapabilityMissing("请提供非空旁白正文后生成配音", ["script"])
    configured_style, rate = config.get("voice_style", ""), config.get("voice_speech_rate", 0)
    if not isinstance(configured_style, str) or len(configured_style) > 2000 or not isinstance(delivery_style, str):
        raise CapabilityMissing("配音风格必须是最多 2000 字的自然语言说明", ["voice_style"])
    if type(rate) is not int or not -50 <= rate <= 100:
        raise CapabilityMissing("配音语速必须为 -50 到 100 的整数", ["voice_speech_rate"])
    style = configured_style.strip()
    notes = delivery_style.strip()
    if notes:
        style = style + "\n" + notes if style else notes
    if len(style) > 2000:
        raise CapabilityMissing("用户风格与配音 Agent 指导合计超过 2000 字；请精简后继续，不能截掉指导。", ["voice_style", "voice_guidance"])
    if style and not supports_voice_style(config):
        raise CapabilityMissing("当前风格指导仅支持字节 WebSocket 的 seed-tts-2.0-expressive；standard 不会应用此风格", ["voice_model", "voice_style"])
    request = {"event": int(Event.START_SESSION), "namespace": "BidirectionalTTS", "req_params": {"model": config.get("voice_model", "seed-tts-2.0-expressive"),
               "speaker": config["voice_id"], "audio_params": {"format": "mp3", "sample_rate": 24000, "enable_subtitle": True}}}
    if style:
        # additions 是 JSON 对象的字符串，context_texts 只发送合并后的一条。
        request["req_params"]["additions"] = json.dumps({"context_texts": [style]}, ensure_ascii=False)
    if rate:
        request["req_params"]["audio_params"]["speech_rate"] = rate
    request_identity = {"text": text, "request": request, "resource_id": config["voice_resource_id"]}
    if operation_key:
        request_identity["operation_key"] = operation_key
    input_hash = fingerprint(request_identity)
    used_voice_fingerprint = voice_fingerprint(config)
    previous = repository.operation(job_id, input_hash, "byte_ws")
    if previous:
        if previous["status"] == "COMPLETED" and Path(previous.get("path", "")).is_file():
            return {**previous, "voice_fingerprint": previous.get("voice_fingerprint", used_voice_fingerprint)}
        if previous["status"] != "REJECTED" or not command_id or previous.get("command_id") == command_id:
            raise SubmissionUnknown("此配音输入已有提交记录，未自动再次付费；请核对记录或导入真实音频", ["voice_operation"],
                                    operation_status="UNKNOWN" if previous["status"] == "SUBMITTING" else previous["status"],
                                    operation_id=previous["operation_id"], request_id=previous.get("request_id"))
    ledger = {"request_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "revision": revision,
              "command_id": command_id, "phase": "connecting"}
    if operation_key:
        ledger["operation_key"] = operation_key
    if style or rate:
        ledger.update(voice_model=config.get("voice_model"), voice_style=style, voice_speech_rate=rate)
    try:
        task_frame = encode_request(Event.TASK_REQUEST, {"event": int(Event.TASK_REQUEST), "req_params": {"text": text}}, ledger["session_id"])
    except (TypeError, ValueError):
        raise CapabilityMissing("旁白正文超过字节帧限制或格式无效，请缩短后重新提交", ["script"]) from None
    _check_cancelled(cancelled)
    operation = repository.retry_rejected_operation(previous["operation_id"], command_id, ledger) if previous else repository.start_operation(job_id, input_hash, "byte_ws", ledger)
    if not operation.get("new"):
        raise SubmissionUnknown("此配音输入已被执行记录占用，请先对账", ["voice_operation"], operation_id=operation["operation_id"])
    ledger["attempt"] = operation.get("attempt", 1)
    connection, connection_id, session_started, finish_sent, submitted = None, None, False, False, False
    audio = bytearray()
    sentences, seen_sentences, usage = [], set(), None
    wire_bytes, subtitle_words = 0, 0
    deadline = time.monotonic() + TOTAL_TIMEOUT
    def persist(phase):
        ledger["phase"] = phase
        repository.finish_operation(operation["operation_id"], "SUBMITTING", ledger)
    def receive():
        nonlocal wire_bytes
        while True:
            _check_cancelled(cancelled)
            try:
                data = connection.recv(timeout=min(RECV_POLL, _remaining(deadline)))
                break
            except TimeoutError:
                _remaining(deadline)
        wire_bytes += len(data)
        if wire_bytes > MAX_WIRE_BYTES:
            raise ProtocolError("response_size_limit")
        frame = decode_server(data)
        _assert_success_status(frame)
        return frame
    try:
        headers = {"X-Api-Key": config["voice_api_key"], "X-Api-Resource-Id": config["voice_resource_id"],
                   "X-Api-Connect-Id": ledger["request_id"]}
        connection = _open_websocket(headers, deadline, cancelled)
        trace_id = _trace_id(connection)
        if trace_id:
            ledger["provider_trace_id"] = trace_id
        _check_cancelled(cancelled)
        connection.send(encode_request(Event.START_CONNECTION, {}))
        frame = receive()
        if frame.event != Event.CONNECTION_STARTED:
            raise ProviderError(_provider_code(frame.payload) if isinstance(frame.payload, dict) else None)
        connection_id = frame.connection_id
        persist("connection_started")
        _check_cancelled(cancelled)
        connection.send(encode_request(Event.START_SESSION, request, ledger["session_id"]))
        frame = receive()
        if frame.event != Event.SESSION_STARTED or frame.session_id != ledger["session_id"]:
            raise ProtocolError("unexpected_session_start")
        session_started = True
        persist("session_started")
        _check_cancelled(cancelled)
        repository.reserve_metric(job_id, revision, "voice_chars", len(text), config["max_voice_chars"])
        _check_cancelled(cancelled)
        # Durable write BEFORE send covers partial writes and process loss.
        persist("task_submitting")
        _check_cancelled(cancelled)
        submitted = True
        connection.send(task_frame)
        _check_cancelled(cancelled)
        connection.send(encode_request(Event.FINISH_SESSION, {}, ledger["session_id"]))
        finish_sent = True
        persist("draining")
        while True:
            frame = receive()
            if frame.session_id != ledger["session_id"]:
                raise ProtocolError("session_identity_mismatch")
            if frame.event == Event.AUDIO:
                audio.extend(frame.payload)
                if len(audio) > MAX_AUDIO_BYTES:
                    raise ProtocolError("audio_size_limit")
            elif frame.event in {Event.SENTENCE_START, Event.SENTENCE_END, Event.SUBTITLE}:
                if frame.event != Event.SENTENCE_START:
                    sentence = _sentence(frame.payload)
                    if sentence:
                        identity = fingerprint(sentence["words"])
                        if identity not in seen_sentences:
                            subtitle_words += len(sentence["words"])
                            if subtitle_words > MAX_SUBTITLE_WORDS:
                                raise ProtocolError("subtitle_size_limit")
                            sentences.append(sentence)
                            seen_sentences.add(identity)
            elif frame.event == Event.USAGE_RESPONSE:
                pass  # No published 154 usage shape; don't invent fields.
            elif frame.event == Event.SESSION_FINISHED:
                if not audio:
                    raise ProtocolError("empty_audio")
                value = frame.payload.get("usage")
                if isinstance(value, dict) and type(value.get("text_words")) is int and value["text_words"] >= 0:
                    usage = {"text_words": value["text_words"]}
                break
            elif frame.event == Event.SESSION_FAILED:
                raise ProviderError(_provider_code(frame.payload))
            else:
                raise ProtocolError("unexpected_session_event")
        ledger["phase"] = "session_finished"
        folder = repository.root / "jobs" / job_id / "operations"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (operation["operation_id"] + ".mp3")
        path.write_bytes(audio)
        result = {**ledger, "path": str(path), "sentences": sentences, "usage": usage, "input_hash": input_hash,
                  "origin": "byte_ws", "voice_fingerprint": used_voice_fingerprint,
                  "voice_model": request["req_params"]["model"], "voice_style": style, "voice_speech_rate": rate}
        repository.finish_operation(operation["operation_id"], "COMPLETED", result)
        return result
    except RenderCancelled:
        repository.finish_operation(operation["operation_id"], "UNKNOWN" if submitted else "REJECTED", ledger)
        raise
    except Exception as exc:
        message = "字节连接或会话未完成文本提交，请检查配置、网络或预算后以新命令重试"
        if ledger["phase"] == "connecting" and isinstance(exc, ssl.SSLError):
            ledger["failure_category"] = "tls_handshake"
            message = "字节 TLS 安全连接失败，尚未进入鉴权和音色校验、未提交配音正文；请检查网络代理、TUN 路由或证书后重试"
        if isinstance(exc, ProviderError) and exc.code is not None:
            ledger["provider_code"] = exc.code
        response = getattr(exc, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
            if type(status) is int and 100 <= status <= 599:
                ledger["http_status"] = status
                ledger["failure_category"] = "handshake_rejected"
                message = f"字节接口握手返回 HTTP {status}，未提交配音正文；请核对鉴权、资源权限及接口配置后重试"
            trace = _trace_id(exc)
            if trace:
                ledger["provider_trace_id"] = trace
        repository.finish_operation(operation["operation_id"], "UNKNOWN" if submitted else "REJECTED", ledger)
        if submitted:
            raise SubmissionUnknown("字节会话提交后的结果不确定，已阻止再次付费；请核对记录或导入真实音频", ["voice_operation"],
                                    operation_id=operation["operation_id"], request_id=ledger["request_id"]) from None
        raise CapabilityMissing(message, ["voice"],
                                operation_status="REJECTED", operation_id=operation["operation_id"], request_id=ledger["request_id"]) from None
    finally:
        if connection is not None:
            _cleanup(connection, connection_id, ledger["session_id"], session_started, finish_sent)
