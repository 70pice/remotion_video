"""Official binary golden frames and local transport fixtures; no paid calls.

Audio fixture bytes are intentionally not decodable production audio. These
tests verify protocol/ledger behavior; real ffprobe checks remain downstream.
"""

import gzip
import json
import socket
import struct
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from videoagents.providers import byte_ws_voice as ws
from videoagents.providers.byte_voice import SubmissionUnknown
from videoagents.providers.llm import CapabilityMissing
from videoagents.storage import Repository
from worker.process_manager import RenderCancelled

FAKE_AUDIO = b"UNIT TEST FAKE AUDIO NOT A REAL MP3"
WORDS = [{"word": "测试", "startTime": 0.125, "endTime": 0.875, "confidence": 0.98}]


def server_frame(event, session="s", payload=None, *, audio=False, compressed=False):
    data = payload if audio else json.dumps({} if payload is None else payload, ensure_ascii=False).encode()
    if compressed:
        data = gzip.compress(data)
    header = bytes([0x11, 0xB4 if audio else 0x94, (0 if audio else 0x10) | int(compressed), 0])
    identifier = session.encode()
    return header + struct.pack(">iI", int(event), len(identifier)) + identifier + struct.pack(">I", len(data)) + data


def error_frame(code=12345):
    payload = json.dumps({"message": "raw server secret must not escape"}).encode()
    return b"\x11\xf0\x10\x00" + struct.pack(">II", code, len(payload)) + payload


def client_request(data):
    event = struct.unpack_from(">i", data, 4)[0]
    offset, session = 8, None
    if event not in (1, 2):
        size = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        session = data[offset:offset + size].decode()
        offset += size
    size = struct.unpack_from(">I", data, offset)[0]
    return event, session, json.loads(data[offset + 4:offset + 4 + size])


class FakeSocket:
    def __init__(self):
        self.timeouts, self.closed = [], False
    def settimeout(self, timeout):
        self.timeouts.append(timeout)
    def close(self):
        self.closed = True


class FixtureConnection:
    def __init__(self, mode="success", *, repo=None, cancel_flag=None):
        self.mode, self.repo, self.cancel_flag = mode, repo, cancel_flag
        self.sent, self.incoming, self.recv_timeouts = [], [], []
        self.closed, self.session = False, None
        self.socket = FakeSocket()
        self.response = SimpleNamespace(headers={"x-tt-logid": "unit-trace-123", "other": "secret-header"})
    def send(self, data):
        request = client_request(data)
        self.sent.append(request)
        event, session, _ = request
        if event == 1:
            self.incoming.append(server_frame(51 if self.mode == "connection_failed" else 50, "connection", {"status_code": 41001} if self.mode == "connection_failed" else {}))
        elif event == 100:
            self.session = session
            self.incoming.append(server_frame(150, "wrong-session" if self.mode == "bad_start" else session))
        elif event == 200:
            if self.repo:
                with self.repo.connection() as db:
                    status, body = db.execute("SELECT status,body FROM operations WHERE provider='byte_ws'").fetchone()
                assert status == "SUBMITTING" and json.loads(body)["phase"] == "task_submitting"
            if self.mode == "partial_send":
                raise OSError("secret-key raw partial-send error")
            if self.cancel_flag is not None and self.mode == "cancel_after_text":
                self.cancel_flag[0] = True
        elif event == 102:
            if self.mode == "timeout":
                return
            if self.mode == "server_error":
                self.incoming.append(error_frame())
                return
            if self.mode == "text_frame":
                self.incoming.append("raw server secret text frame")
                return
            if self.mode == "bad_order":
                self.incoming.append(server_frame(150, session))
                return
            if self.mode == "empty":
                self.incoming.append(server_frame(152, session))
                return
            self.incoming.append(server_frame(352, "wrong-session" if self.mode == "mismatch" else session, FAKE_AUDIO, audio=True))
            if self.mode == "missing_finish":
                self.incoming.append(ConnectionError("raw secret EOF"))
                return
            if self.mode == "truncated":
                self.incoming.append(b"\x11\x94\x10\x00\x01")
                return
            self.incoming.append(server_frame(350, session, {"words": []}))
            if self.mode != "no_words":
                self.incoming.append(server_frame(364, session, {"text": "测试", "words": WORDS}))
                # Compatibility end event can duplicate 2.0 subtitle words.
                self.incoming.append(server_frame(351, session, {"text": "测试。", "words": WORDS}))
            else:
                self.incoming.append(server_frame(364, session, {"text": "测试"}))
            self.incoming.append(server_frame(154, session, {"future_charge_metadata": True}))
            finished = {"usage": {"text_words": 2, "untrusted_extra": "raw secret"}}
            if self.mode == "bad_success":
                finished["status_code"] = 0
            elif self.mode == "old_success":
                finished["status_code"] = 20000000
            self.incoming.append(server_frame(152, session, finished))
        elif event == 101:
            self.incoming.append(server_frame(151, session))
        elif event == 2:
            if self.mode == "lost_close":
                return
            self.incoming.append(server_frame(52, "connection"))
    def recv(self, timeout):
        self.recv_timeouts.append(timeout)
        if self.incoming:
            value = self.incoming.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        time.sleep(min(timeout, 0.002))
        raise TimeoutError("fixture no data")
    def close(self):
        self.closed = True


@pytest.fixture
def configured(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    # Test-only config injection avoids reading any real credentials/settings.
    config = {"voice_provider": "byte_ws", "voice_endpoint": ws.ENDPOINT, "voice_api_key": "TEST ONLY FAKE KEY",
        "voice_id": "unit-owned-voice", "voice_resource_id": "seed-icl-2.0", "voice_model": "seed-tts-2.0-standard", "max_voice_chars": 1000}
    monkeypatch.setattr(ws.SettingsService, "internal", lambda self: config)
    monkeypatch.setattr(ws, "CLOSE_TIMEOUT", 0.02)
    return repo, config


def fixture_transport(monkeypatch, connection):
    calls = []
    def open_transport(headers, deadline, cancelled):
        calls.append((headers, deadline))
        return connection
    monkeypatch.setattr(ws, "_open_websocket", open_transport)
    return calls


def operation(repo):
    with repo.connection() as db:
        row = db.execute("SELECT operation_id,status,body FROM operations WHERE provider='byte_ws'").fetchone()
    return {"operation_id": row[0], "status": row[1], **json.loads(row[2])} if row else None


def metric(repo):
    with repo.connection() as db:
        return db.execute("SELECT value FROM run_metrics WHERE metric='voice_chars'").fetchone()


def test_expressive_style_additions_are_a_json_string_and_narration_is_unchanged(configured, monkeypatch):
    repo, config = configured
    config.update(voice_model="seed-tts-2.0-expressive", voice_style="自然有情绪，开头有疑问。", voice_speech_rate=-12)
    connection = FixtureConnection()
    fixture_transport(monkeypatch, connection)
    result = ws.synthesize(repo, "unit-job", 1, "测试", "command-one", delivery_style="重点词稍重，句末自然收束。")
    params = connection.sent[1][2]["req_params"]
    assert isinstance(params["additions"], str)
    assert json.loads(params["additions"]) == {"context_texts": ["自然有情绪，开头有疑问。\n重点词稍重，句末自然收束。"]}
    assert params["audio_params"]["speech_rate"] == -12
    assert connection.sent[2][2]["req_params"] == {"text": "测试"}
    assert result["voice_fingerprint"] == ws.voice_fingerprint(config)
    assert result["voice_model"] == "seed-tts-2.0-expressive"
    assert result["voice_style"] == "自然有情绪，开头有疑问。\n重点词稍重，句末自然收束。"
    assert result["voice_speech_rate"] == -12


@pytest.mark.parametrize("rate", [-50, 100])
def test_speech_rate_accepts_documented_integer_boundaries(configured, monkeypatch, rate):
    repo, config = configured
    config["voice_speech_rate"] = rate
    connection = FixtureConnection()
    fixture_transport(monkeypatch, connection)
    ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert connection.sent[1][2]["req_params"]["audio_params"]["speech_rate"] == rate


@pytest.mark.parametrize("change", [{"voice_style": "有情绪起伏。"}, {"voice_speech_rate": -15}])
def test_performance_change_cannot_reuse_completed_flat_receipt(configured, monkeypatch, change):
    repo, config = configured
    config["voice_model"] = "seed-tts-2.0-expressive"
    calls = fixture_transport(monkeypatch, FixtureConnection())
    flat = ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    config.update(change)
    expressive = ws.synthesize(repo, "unit-job", 1, "测试", "command-two")
    assert len(calls) == 2 and expressive["path"] != flat["path"]
    assert expressive["voice_fingerprint"] != flat["voice_fingerprint"]


def test_unknown_barrier_survives_style_and_rate_change(configured, monkeypatch):
    repo, config = configured
    config["voice_model"] = "seed-tts-2.0-expressive"
    calls = fixture_transport(monkeypatch, FixtureConnection("partial_send"))
    with pytest.raises(SubmissionUnknown) as first:
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    config.update(voice_style="新的朗读风格。", voice_speech_rate=20)
    with pytest.raises(SubmissionUnknown) as second:
        ws.synthesize(repo, "unit-job", 1, "测试", "command-two", delivery_style="新的建议。")
    assert first.value.operation_id == second.value.operation_id and len(calls) == 1


def test_standard_model_does_not_silently_ignore_explicit_style(configured, monkeypatch):
    repo, config = configured
    config["voice_style"] = "有情绪起伏。"
    monkeypatch.setattr(ws, "_open_websocket", lambda *a: pytest.fail("unsupported style reached provider"))
    with pytest.raises(CapabilityMissing, match="expressive"):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert operation(repo) is None and metric(repo) is None


def test_user_style_has_priority_when_guidance_exceeds_length_limit(configured, monkeypatch):
    repo, config = configured
    config.update(voice_model="seed-tts-2.0-expressive", voice_style="用户风格" * 400)
    connection = FixtureConnection()
    fixture_transport(monkeypatch, connection)
    ws.synthesize(repo, "unit-job", 1, "测试", "command-one", delivery_style="额外建议" * 3000)
    style = json.loads(connection.sent[1][2]["req_params"]["additions"])["context_texts"]
    assert len(style) == 1 and style[0].startswith(config["voice_style"]) and len(style[0]) <= 2000


def test_request_fingerprint_records_performance_config_snapshot(configured, monkeypatch):
    repo, config = configured
    config.update(voice_model="seed-tts-2.0-expressive", voice_style="原风格。", voice_speech_rate=-10)
    actual_fingerprint = ws.voice_fingerprint(config)
    connection = FixtureConnection()
    def open_transport(*args):
        config.update(voice_style="请求期间改变的风格。", voice_speech_rate=30)
        return connection
    monkeypatch.setattr(ws, "_open_websocket", open_transport)
    result = ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    params = connection.sent[1][2]["req_params"]
    assert json.loads(params["additions"])["context_texts"] == ["原风格。"]
    assert params["audio_params"]["speech_rate"] == -10
    assert result["voice_fingerprint"] == actual_fingerprint != ws.voice_fingerprint(config)


def test_official_golden_binary_frames_and_event_fields():
    assert ws.encode_request(ws.Event.START_CONNECTION, {}).hex() == "1114100000000001000000027b7d"
    fixtures = [
        ("11941000000000320000000163000000027b7d", ws.Event.CONNECTION_STARTED, "c", {}),
        ("11941000000000960000000173000000027b7d", ws.Event.SESSION_STARTED, "s", {}),
        ("11b4000000000160000000017300000003010203", ws.Event.AUDIO, "s", b"\x01\x02\x03"),
        ("11941000000000980000000173000000027b7d", ws.Event.SESSION_FINISHED, "s", {}),
    ]
    for raw, event, identifier, payload in fixtures:
        frame = ws.decode_server(bytes.fromhex(raw))
        assert frame.event == event and (frame.connection_id or frame.session_id) == identifier and frame.payload == payload
    assert ws.decode_server(error_frame(123)).error_code == 123


@pytest.mark.parametrize("raw", [b"", b"\x11\x94\x10", b"\x21\x94\x10\x00", b"\x11\x91\x10\x00", b"\x11\x94\x20\x00",
    bytes.fromhex("11941000000000980000000173000000027b7d") + b"trailing"])
def test_malformed_or_unsupported_frames_fail_closed(raw):
    with pytest.raises(ws.ProtocolError):
        ws.decode_server(raw)


def test_gzip_is_bounded_and_unknown_events_rejected(monkeypatch):
    assert ws.decode_server(server_frame(364, "s", {"words": WORDS}, compressed=True)).payload["words"] == WORDS
    with pytest.raises(ws.ProtocolError):
        ws.decode_server(server_frame(999, "s"))
    monkeypatch.setattr(ws, "MAX_FRAME_BYTES", 128)
    with pytest.raises(ws.ProtocolError):
        ws.decode_server(server_frame(352, "s", b"x" * 1000, audio=True, compressed=True))


@pytest.mark.parametrize("mode", ["success", "old_success", "no_words", "lost_close"])
def test_matched_finish_audio_and_real_subtitles_complete_and_cache(configured, monkeypatch, mode):
    repo, config = configured
    connection = FixtureConnection(mode, repo=repo)
    calls = fixture_transport(monkeypatch, connection)
    result = ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert Path(result["path"]).read_bytes() == FAKE_AUDIO and result["origin"] == "byte_ws"
    assert result["usage"] == {"text_words": 2}
    if mode == "no_words":
        assert result["sentences"] == []
    else:
        assert result["sentences"][0]["words"] == WORDS
    assert result["voice_fingerprint"] == ws.voice_fingerprint(config)
    assert len(result["sentences"]) == (0 if mode == "no_words" else 1)
    assert operation(repo)["status"] == "COMPLETED" and connection.closed
    assert [item[0] for item in connection.sent] == [1, 100, 200, 102, 2]
    start = connection.sent[1][2]
    assert start["namespace"] == "BidirectionalTTS"
    assert start["req_params"]["model"] == "seed-tts-2.0-standard"
    assert start["req_params"]["audio_params"] == {"format": "mp3", "sample_rate": 24000, "enable_subtitle": True}
    assert connection.sent[2][2]["req_params"]["text"] == "测试"
    assert set(calls[0][0]) == {"X-Api-Key", "X-Api-Resource-Id", "X-Api-Connect-Id"}
    assert calls[0][0]["X-Api-Connect-Id"] == result["request_id"]
    replay = ws.synthesize(repo, "unit-job", 1, "测试", "command-two")
    assert replay["path"] == result["path"] and len(calls) == 1 and metric(repo)[0] == 2


@pytest.mark.parametrize("record_fingerprint", [None, "recorded-actual-voice-fingerprint"])
def test_completed_replay_preserves_recorded_voice_fingerprint_or_backfills_legacy(configured, monkeypatch, record_fingerprint):
    repo, config = configured
    calls = fixture_transport(monkeypatch, FixtureConnection())
    result = ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    legacy_body = dict(result)
    if record_fingerprint is None:
        legacy_body.pop("voice_fingerprint")
    else:
        legacy_body["voice_fingerprint"] = record_fingerprint
    repo.finish_operation(operation(repo)["operation_id"], "COMPLETED", legacy_body)
    replay = ws.synthesize(repo, "unit-job", 1, "测试", "command-two")
    assert replay["voice_fingerprint"] == (record_fingerprint or ws.voice_fingerprint(config))
    assert replay["path"] == result["path"] and len(calls) == 1


def test_operation_key_keeps_identical_script_segments_distinct(configured, monkeypatch):
    repo, _ = configured
    calls = fixture_transport(monkeypatch, FixtureConnection())
    first = ws.synthesize(
        repo, "unit-job", 1, "测试", "command-one", operation_key="script-segment:s1"
    )
    second = ws.synthesize(
        repo, "unit-job", 1, "测试", "command-one", operation_key="script-segment:s2"
    )
    assert first["path"] != second["path"] and len(calls) == 2
    with repo.connection() as db:
        rows = db.execute("SELECT body FROM operations WHERE provider='byte_ws' ORDER BY operation_id").fetchall()
    assert {json.loads(row[0])["operation_key"] for row in rows} == {
        "script-segment:s1", "script-segment:s2",
    }
    replay = ws.synthesize(
        repo, "unit-job", 1, "测试", "command-two", operation_key="script-segment:s1"
    )
    assert replay["path"] == first["path"] and len(calls) == 2


def test_voice_fingerprint_binds_config_snapshot_used_for_request(configured, monkeypatch):
    repo, config = configured
    actual_fingerprint = ws.voice_fingerprint(config)
    connection = FixtureConnection()
    def open_transport(*args):
        config["voice_id"] = "changed-while-request-in-flight"
        config["voice_model"] = "changed-model"
        return connection
    monkeypatch.setattr(ws, "_open_websocket", open_transport)
    result = ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert result["voice_fingerprint"] == actual_fingerprint
    assert result["voice_fingerprint"] != ws.voice_fingerprint(config)
    assert connection.sent[1][2]["req_params"]["speaker"] == "unit-owned-voice"
    assert connection.sent[1][2]["req_params"]["model"] == "seed-tts-2.0-standard"


def test_handshake_status_is_numeric_and_raw_response_never_persisted(configured, monkeypatch):
    repo, config = configured
    class HandshakeFailure(Exception):
        response = SimpleNamespace(status_code=403, headers={"x-tt-logid": "safe-trace-403", "X-Api-Key": config["voice_api_key"]},
                                   body=b"secret resource permission failure")
    def fail(*args):
        raise HandshakeFailure("raw secret response")
    monkeypatch.setattr(ws, "_open_websocket", fail)
    with pytest.raises(CapabilityMissing) as failure:
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    record = operation(repo)
    assert record["status"] == "REJECTED" and record["http_status"] == 403
    assert record["provider_trace_id"] == "safe-trace-403"
    assert "secret" not in json.dumps(record) and "secret" not in str(failure.value)
    assert config["voice_api_key"] not in json.dumps(record)
    assert metric(repo) is None


@pytest.mark.parametrize("boundary", ["reserve_metric", "task_persist"])
def test_cancel_during_database_wait_before_text_never_sends_task(configured, monkeypatch, boundary):
    repo, _ = configured
    flag = [False]
    connection = FixtureConnection()
    fixture_transport(monkeypatch, connection)
    if boundary == "reserve_metric":
        original = repo.reserve_metric
        def reserve(*args, **kwargs):
            result = original(*args, **kwargs)
            flag[0] = True
            return result
        monkeypatch.setattr(repo, "reserve_metric", reserve)
    else:
        original = repo.finish_operation
        def persist(operation_id, status, body):
            result = original(operation_id, status, body)
            if status == "SUBMITTING" and body.get("phase") == "task_submitting":
                flag[0] = True
            return result
        monkeypatch.setattr(repo, "finish_operation", persist)
    with pytest.raises(RenderCancelled):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one", cancelled=lambda: flag[0])
    assert operation(repo)["status"] == "REJECTED"
    assert 200 not in [request[0] for request in connection.sent]
    assert connection.closed


def test_oversized_local_text_never_connects_or_creates_paid_record(configured, monkeypatch):
    repo, _ = configured
    monkeypatch.setattr(ws, "MAX_FRAME_BYTES", 2048)
    monkeypatch.setattr(ws, "_open_websocket", lambda *a: pytest.fail("invalid local text connected"))
    with pytest.raises(CapabilityMissing):
        ws.synthesize(repo, "unit-job", 1, "字" * 1000, "command-one")
    assert operation(repo) is None and metric(repo) is None


@pytest.mark.parametrize("mode", ["partial_send", "missing_finish", "mismatch", "server_error", "bad_success", "empty", "text_frame", "bad_order", "truncated"])
def test_uncertain_after_text_is_unknown_sanitized_and_never_replayed(configured, monkeypatch, mode):
    repo, config = configured
    connection = FixtureConnection(mode, repo=repo)
    calls = fixture_transport(monkeypatch, connection)
    with pytest.raises(SubmissionUnknown) as failure:
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert "secret" not in str(failure.value) and config["voice_api_key"] not in str(failure.value)
    record = operation(repo)
    assert record["status"] == "UNKNOWN" and connection.closed
    assert record["provider_trace_id"] == "unit-trace-123"
    assert "secret" not in json.dumps(record) and config["voice_api_key"] not in json.dumps(record)
    if mode == "server_error":
        assert record["provider_code"] == 12345
    config["voice_id"], config["voice_model"] = "changed-voice", "changed-model"
    with pytest.raises(SubmissionUnknown):
        ws.synthesize(repo, "unit-job", 1, "different input", "new-command")
    assert len(calls) == 1 and metric(repo)[0] == 2


@pytest.mark.parametrize("mode", ["connection_failed", "bad_start"])
def test_pre_text_rejection_has_no_budget_and_only_new_command_can_retry(configured, monkeypatch, mode):
    repo, _ = configured
    bad = FixtureConnection(mode)
    calls = fixture_transport(monkeypatch, bad)
    with pytest.raises(CapabilityMissing) as failure:
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert failure.value.operation_status == "REJECTED" and operation(repo)["status"] == "REJECTED"
    assert metric(repo) is None and not any(item[0] == 200 for item in bad.sent)
    with pytest.raises(SubmissionUnknown):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert len(calls) == 1
    good = FixtureConnection()
    fixture_transport(monkeypatch, good)
    result = ws.synthesize(repo, "unit-job", 1, "测试", "command-two")
    assert result["attempt"] == 2 and operation(repo)["status"] == "COMPLETED"
    assert good.session != bad.session and good.closed


def test_control_connection_failure_and_budget_failure_leave_rejected(configured, monkeypatch):
    repo, config = configured
    def fail(*args):
        raise OSError("private raw key must not be persisted")
    monkeypatch.setattr(ws, "_open_websocket", fail)
    with pytest.raises(CapabilityMissing):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert operation(repo)["status"] == "REJECTED" and metric(repo) is None
    connection = FixtureConnection()
    fixture_transport(monkeypatch, connection)
    config["max_voice_chars"] = 1
    with pytest.raises(CapabilityMissing):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-two")
    assert operation(repo)["status"] == "REJECTED" and operation(repo)["phase"] == "session_started"
    assert metric(repo) is None and 200 not in [item[0] for item in connection.sent]
    assert connection.closed


def test_tls_failure_is_reported_before_authentication_without_raw_exception(configured, monkeypatch):
    repo, config = configured
    def fail(*args):
        raise ws.ssl.SSLEOFError("raw secret TLS failure " + config["voice_api_key"])
    monkeypatch.setattr(ws, "_open_websocket", fail)
    with pytest.raises(CapabilityMissing) as failure:
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    record = operation(repo)
    assert record["failure_category"] == "tls_handshake"
    assert record["phase"] == "connecting" and record["status"] == "REJECTED"
    assert "TLS" in str(failure.value) and "尚未进入鉴权和音色校验" in str(failure.value)
    assert "secret" not in json.dumps(record) and "secret" not in str(failure.value)
    assert config["voice_api_key"] not in json.dumps(record) and metric(repo) is None


def test_timeout_after_task_is_unknown_with_short_receives(configured, monkeypatch):
    repo, _ = configured
    connection = FixtureConnection("timeout")
    fixture_transport(monkeypatch, connection)
    monkeypatch.setattr(ws, "TOTAL_TIMEOUT", 0.02)
    start = time.monotonic()
    with pytest.raises(SubmissionUnknown):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert time.monotonic() - start < 1
    assert operation(repo)["status"] == "UNKNOWN" and connection.closed
    assert all(value <= ws.RECV_POLL for value in connection.recv_timeouts)


def test_cancellation_before_start_does_not_read_settings_or_reserve(configured, monkeypatch):
    repo, _ = configured
    monkeypatch.setattr(ws.SettingsService, "internal", lambda *_: pytest.fail("initial cancellation read settings"))
    monkeypatch.setattr(ws, "_open_websocket", lambda *a: pytest.fail("initial cancellation connected"))
    with pytest.raises(RenderCancelled):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one", cancelled=lambda: True)
    assert operation(repo) is None and metric(repo) is None


@pytest.mark.parametrize("after_text", [False, True])
def test_mid_session_cancel_raises_cancelled_and_records_submission_boundary(configured, monkeypatch, after_text):
    repo, _ = configured
    flag = [False]
    connection = FixtureConnection("cancel_after_text" if after_text else "success", cancel_flag=flag)
    original_send = connection.send
    def send(data):
        original_send(data)
        if not after_text and client_request(data)[0] == 100:
            flag[0] = True
    connection.send = send
    fixture_transport(monkeypatch, connection)
    with pytest.raises(RenderCancelled):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one", cancelled=lambda: flag[0])
    assert operation(repo)["status"] == ("UNKNOWN" if after_text else "REJECTED")
    assert (metric(repo) is not None) is after_text
    assert connection.closed


def test_http_unknown_is_a_cross_transport_barrier(configured, monkeypatch):
    repo, _ = configured
    old = repo.start_operation("unit-job", "old-http-input", "byte_http", {"request_id": "http-request", "revision": 1})
    repo.finish_operation(old["operation_id"], "UNKNOWN", {"request_id": "http-request", "revision": 1})
    monkeypatch.setattr(ws, "_open_websocket", lambda *a: pytest.fail("HTTP unknown bypassed via WS"))
    with pytest.raises(SubmissionUnknown) as failure:
        ws.synthesize(repo, "unit-job", 1, "测试", "new-command")
    assert failure.value.operation_id == old["operation_id"] and failure.value.request_id == "http-request"
    assert operation(repo) is None and metric(repo) is None


@pytest.mark.parametrize("limit", ["MAX_AUDIO_BYTES", "MAX_WIRE_BYTES"])
def test_audio_and_wire_limits_close_without_accepting_partial_output(configured, monkeypatch, limit):
    repo, _ = configured
    connection = FixtureConnection()
    fixture_transport(monkeypatch, connection)
    monkeypatch.setattr(ws, limit, 4 if limit == "MAX_AUDIO_BYTES" else 100)
    with pytest.raises(SubmissionUnknown):
        ws.synthesize(repo, "unit-job", 1, "测试", "command-one")
    assert operation(repo)["status"] == "UNKNOWN" and connection.closed
    assert not list((repo.root / "jobs" / "unit-job").glob("operations/*.mp3"))


def test_missing_or_alias_subtitle_fields_never_create_fake_timings():
    assert ws._sentence({"text": "测试"}) is None
    assert ws._sentence({"words": [{"text": "测试", "start": 0, "end": 1}]}) is None
    assert ws._sentence({"words": [{"word": "测试", "startTime": 0, "endTime": 1}]}) == {
        "words": [{"word": "测试", "startTime": 0, "endTime": 1}]}
    assert ws._sentence({"words": [{"word": "测试", "startTime": True, "endTime": 1}]}) is None


def test_pinned_public_socket_tls_proxy_and_private_logger(monkeypatch):
    resolutions, targets, kwargs_seen = [], [], []
    def resolve(host, port, **kwargs):
        resolutions.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    monkeypatch.setattr(ws.socket, "getaddrinfo", resolve)
    raw = FakeSocket()
    monkeypatch.setattr(ws.socket, "create_connection", lambda target, **kwargs: targets.append(target) or raw)
    connection = FixtureConnection()
    def connect(uri, **kwargs):
        assert uri == ws.ENDPOINT
        kwargs_seen.append(kwargs)
        return connection
    monkeypatch.setattr(ws, "connect", connect)
    result = ws._open_websocket({"X-Api-Key": "TEST ONLY KEY"}, time.monotonic() + 1, lambda: False)
    assert result is connection and resolutions == [ws.HOST] and targets == [("93.184.216.34", 443)]
    options = kwargs_seen[0]
    assert options["proxy"] is None and options["server_hostname"] == ws.HOST and options["sock"] is raw
    assert options["ssl"].check_hostname and options["ssl"].verify_mode != 0
    assert options["logger"].disabled and not options["logger"].propagate
    assert options["max_size"] == ws.MAX_FRAME_BYTES and options["max_queue"] == 4
    monkeypatch.setattr(ws.socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(OSError):
        ws._open_websocket({}, time.monotonic() + 1, lambda: False)
    assert len(targets) == 1


def test_tls_eof_retries_only_vendor_socket_on_physical_interface(monkeypatch):
    monkeypatch.setattr(ws, "_resolve_public_ips", lambda *a: ["93.184.216.34"])
    monkeypatch.setattr(ws, "_windows_physical_interface", lambda *a: 11, raising=False)
    default = FakeSocket()
    events, options = [], []
    class RoutedSocket(FakeSocket):
        def setsockopt(self, *args):
            events.append(("interface", args))
        def connect(self, target):
            events.append(("connect", target))
    routed = RoutedSocket()
    monkeypatch.setattr(ws.socket, "create_connection", lambda *a, **k: default)
    monkeypatch.setattr(ws.socket, "socket", lambda *a: routed)
    connection = FixtureConnection()
    def connect(uri, **kwargs):
        options.append(kwargs)
        if len(options) == 1:
            raise ws.ssl.SSLEOFError("synthetic TUN EOF")
        assert default.closed
        return connection
    monkeypatch.setattr(ws, "connect", connect)
    assert ws._open_websocket({}, time.monotonic() + 2, lambda: False) is connection
    assert events == [("interface", (socket.IPPROTO_IP, 31, struct.pack("!I", 11))),
                      ("connect", ("93.184.216.34", 443))]
    assert len(options) == 2 and options[1]["sock"] is routed
    assert all(o["server_hostname"] == ws.HOST and o["ssl"].check_hostname
               and o["ssl"].verify_mode != 0 and o["proxy"] is None for o in options)


def test_certificate_failure_never_uses_physical_interface_fallback(monkeypatch):
    monkeypatch.setattr(ws, "_resolve_public_ips", lambda *a: ["93.184.216.34"])
    monkeypatch.setattr(ws, "_windows_physical_interface", lambda *a: pytest.fail("certificate error retried"), raising=False)
    raw = FakeSocket()
    monkeypatch.setattr(ws.socket, "create_connection", lambda *a, **k: raw)
    def fail(*args, **kwargs):
        raise ws.ssl.SSLCertVerificationError("synthetic untrusted certificate")
    monkeypatch.setattr(ws, "connect", fail)
    with pytest.raises(ws.ssl.SSLCertVerificationError):
        ws._open_websocket({}, time.monotonic() + 2, lambda: False)
    assert raw.closed


def test_failed_physical_connection_closes_both_sockets(monkeypatch):
    monkeypatch.setattr(ws, "_resolve_public_ips", lambda *a: ["93.184.216.34"])
    monkeypatch.setattr(ws, "_windows_physical_interface", lambda *a: 11)
    default = FakeSocket()
    class RoutedSocket(FakeSocket):
        def setsockopt(self, *args):
            pass
        def connect(self, target):
            raise OSError("synthetic physical connection failure")
    routed = RoutedSocket()
    monkeypatch.setattr(ws.socket, "create_connection", lambda *a, **k: default)
    monkeypatch.setattr(ws.socket, "socket", lambda *a: routed)
    def fail(*args, **kwargs):
        raise ws.ssl.SSLEOFError("synthetic TUN EOF")
    monkeypatch.setattr(ws, "connect", fail)
    with pytest.raises(OSError, match="physical connection failure"):
        ws._open_websocket({}, time.monotonic() + 2, lambda: False)
    assert default.closed and routed.closed


def test_cancelled_physical_discovery_does_not_start_process(monkeypatch):
    monkeypatch.setattr(ws, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(ws.subprocess, "run", lambda *a, **k: pytest.fail("cancelled discovery started process"))
    with pytest.raises(RenderCancelled):
        ws._windows_physical_interface(time.monotonic() + 1, lambda: True)


def test_cancellation_during_failed_interface_query_is_preserved(monkeypatch):
    monkeypatch.setattr(ws, "os", SimpleNamespace(name="nt"))
    cancelled = [False]
    def fail(*args, **kwargs):
        cancelled[0] = True
        raise ws.subprocess.TimeoutExpired("synthetic read-only query", 1)
    monkeypatch.setattr(ws.subprocess, "run", fail)
    with pytest.raises(RenderCancelled):
        ws._windows_physical_interface(time.monotonic() + 1, lambda: cancelled[0])


@pytest.mark.parametrize("stdout,expected", [("11\n", 11), ("", None), ("0", None), ("16777216", None),
                                             ("11\n12", None), ("9" * 100, None), ("unexpected output", None)])
def test_physical_interface_discovery_is_read_only_bounded_and_validated(monkeypatch, stdout, expected):
    monkeypatch.setattr(ws, "os", SimpleNamespace(name="nt"), raising=False)
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=stdout)
    monkeypatch.setattr(ws, "subprocess", SimpleNamespace(run=run, PIPE=-1, DEVNULL=-3, CREATE_NO_WINDOW=0x08000000,
                                                          SubprocessError=Exception), raising=False)
    assert ws._windows_physical_interface(time.monotonic() + 1, lambda: False) == expected
    args, kwargs = calls[0]
    assert args[:3] == ["powershell.exe", "-NoProfile", "-NonInteractive"]
    assert "Get-NetAdapter -Physical" in args[-1] and "Get-NetRoute" in args[-1]
    assert not any(word in args[-1] for word in ["Set-", "New-", "Remove-", "Stop-"])
    assert kwargs["shell"] is False and 0 < kwargs["timeout"] <= 1
    assert kwargs["creationflags"] == 0x08000000


def test_dns_deadline_and_cancellation_do_not_wait_for_resolver_thread(monkeypatch):
    release = threading.Event()
    def slow(*args, **kwargs):
        release.wait(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    monkeypatch.setattr(ws.socket, "getaddrinfo", slow)
    try:
        before = time.monotonic()
        with pytest.raises(TimeoutError):
            ws._resolve_public_ips(time.monotonic() + 0.01, lambda: False)
        assert time.monotonic() - before < 0.5
        with pytest.raises(RenderCancelled):
            ws._resolve_public_ips(time.monotonic() + 1, lambda: True)
    finally:
        release.set()


def doh_payload(ips=("163.181.39.213",)):
    return {"Status": 0, "TC": False, "AD": False, "Question": [{"name": ws.HOST + ".", "type": 1}],
            "Answer": [{"name": ws.HOST, "type": 1, "TTL": 60, "data": ip} for ip in ips]}


def fixture_doh(monkeypatch, payload=None, *, body=None, status=200, content_type="application/dns-json", after_headers=None,
                close_after_body=False):
    """Synthetic bootstrap/TLS/HTTP; this fixture opens no real socket."""
    calls = {"targets": [], "http": [], "requests": [], "reads": [], "tls": []}
    raw, tls = FakeSocket(), FakeSocket()
    def create_connection(target, **kwargs):
        calls["targets"].append((target, kwargs))
        return raw
    monkeypatch.setattr(ws.socket, "create_connection", create_connection)
    context = ws.ssl.create_default_context()
    def wrap_socket(stream, **kwargs):
        calls["tls"].append((stream, kwargs))
        return tls
    monkeypatch.setattr(context, "wrap_socket", wrap_socket)
    monkeypatch.setattr(ws.ssl, "create_default_context", lambda: context)
    class Response:
        closed = False
        def __init__(self):
            self.status = status
            self.remaining = json.dumps(doh_payload() if payload is None else payload).encode() if body is None else body
        def getheader(self, name, default=""):
            return content_type if name == "Content-Type" else default
        def read1(self, size):
            calls["reads"].append(size)
            data, self.remaining = self.remaining[:size], self.remaining[size:]
            if close_after_body and not self.remaining:
                self.closed = True
                tls.close()
            return data
        def isclosed(self):
            return self.closed
        def close(self):
            self.closed = True
    response = Response()
    class Client:
        closed = False
        sock = None
        def __init__(self, host, port, **kwargs):
            calls["http"].append((host, port, kwargs))
            calls["client"] = self
        def request(self, *args, **kwargs):
            calls["requests"].append((args, kwargs, self.sock))
        def getresponse(self):
            if after_headers:
                after_headers()
            return response
        def close(self):
            self.closed = True
    monkeypatch.setattr(ws.http.client, "HTTPConnection", Client)
    return calls, raw, tls, response, context


def test_doh_complete_close_response_does_not_touch_closed_tls_socket(monkeypatch):
    calls, raw, tls, response, _ = fixture_doh(monkeypatch, close_after_body=True)
    set_timeout = tls.settimeout

    def timeout_on_open_socket(value):
        if tls.closed:
            raise OSError("synthetic Windows socket already closed")
        set_timeout(value)

    monkeypatch.setattr(tls, "settimeout", timeout_on_open_socket)
    assert ws._resolve_doh_public_ips(time.monotonic() + 1) == ["163.181.39.213"]
    assert len(calls["reads"]) == 1
    assert raw.closed and tls.closed and response.closed and calls["client"].closed


def test_doh_bootstrap_has_fixed_public_target_tls_host_and_only_fixed_query(monkeypatch):
    payload = doh_payload(("163.181.39.213", "163.181.39.214", "163.181.39.213"))
    payload["Answer"].insert(0, {"name": ws.HOST, "type": 5, "data": "official-cname.example."})
    calls, raw, tls, response, context = fixture_doh(monkeypatch, payload)
    assert ws._resolve_doh_public_ips(time.monotonic() + 1) == ["163.181.39.213", "163.181.39.214"]
    assert calls["targets"][0][0] == ("1.1.1.1", 443)
    assert 0 < calls["targets"][0][1]["timeout"] <= 1
    assert calls["tls"] == [(raw, {"server_hostname": "cloudflare-dns.com"})]
    assert context.check_hostname and context.verify_mode != 0
    assert calls["http"][0][:2] == ("cloudflare-dns.com", 443)
    assert calls["requests"] == [(("GET", "/dns-query?name=openspeech.bytedance.com&type=A"),
                                  {"headers": {"Accept": "application/dns-json", "Connection": "close"}}, tls)]
    assert raw.closed and tls.closed and response.closed and calls["client"].closed
    assert all(0 < size <= 4096 for size in calls["reads"])


def test_tun_fake_ip_fallback_is_inside_resolver_and_final_wss_pins_public_ip(monkeypatch):
    calls, *_ = fixture_doh(monkeypatch)
    monkeypatch.setattr(ws.socket, "getaddrinfo", lambda host, port, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.0.9", port)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.19.255.254", port))])
    connection, seen = FixtureConnection(), []
    def connect(uri, **kwargs):
        seen.append((uri, kwargs))
        return connection
    monkeypatch.setattr(ws, "connect", connect)
    assert ws._open_websocket({"X-Api-Key": "TEST ONLY KEY"}, time.monotonic() + 1, lambda: False) is connection
    assert [target for target, _ in calls["targets"]] == [("1.1.1.1", 443), ("163.181.39.213", 443)]
    assert seen[0][0] == ws.ENDPOINT and seen[0][1]["server_hostname"] == ws.HOST
    assert seen[0][1]["proxy"] is None
    assert calls["requests"][0][1]["headers"] == {"Accept": "application/dns-json", "Connection": "close"}


@pytest.mark.parametrize("ips", [["127.0.0.1"], ["10.0.0.9"], ["169.254.1.1"], ["198.18.0.9", "163.181.39.213"], ["198.18.0.9", "10.0.0.9"], []])
def test_other_private_empty_or_mixed_system_dns_never_uses_doh(monkeypatch, ips):
    monkeypatch.setattr(ws.socket, "getaddrinfo", lambda host, port, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips])
    monkeypatch.setattr(ws, "_resolve_doh_public_ips", lambda *a: pytest.fail("non-TUN address triggered fallback"))
    with pytest.raises(OSError):
        ws._resolve_public_ips(time.monotonic() + 1, lambda: False)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.9", "198.18.0.9", "169.254.1.1", "::1", "not-an-ip"])
def test_doh_final_private_or_invalid_a_answer_never_reaches_wss(monkeypatch, ip):
    calls, raw, tls, response, _ = fixture_doh(monkeypatch, doh_payload(("163.181.39.213", ip)))
    monkeypatch.setattr(ws.socket, "getaddrinfo", lambda host, port, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.0.9", port))])
    monkeypatch.setattr(ws, "connect", lambda *a, **k: pytest.fail("private DoH answer reached authenticated WSS"))
    with pytest.raises(OSError):
        ws._open_websocket({"X-Api-Key": "TEST ONLY KEY"}, time.monotonic() + 1, lambda: False)
    assert len(calls["targets"]) == 1 and raw.closed and tls.closed and response.closed


@pytest.mark.parametrize("fault", ["redirect", "http_error", "wrong_type", "oversize", "invalid_json", "bad_status", "boolean_status", "truncated", "nonboolean_truncated", "wrong_question", "double_trailing_dot", "bad_question_type", "no_answers", "cname_only", "bad_answer_type"])
def test_doh_response_validation_bounds_and_cleanup(monkeypatch, fault):
    payload, options = doh_payload(), {}
    if fault == "redirect":
        options["status"] = 302
    elif fault == "http_error":
        options["status"] = 503
    elif fault == "wrong_type":
        options["content_type"] = "text/html"
    elif fault == "oversize":
        options["body"] = b"x" * (ws._MAX_DOH_BYTES + 1)
    elif fault == "invalid_json":
        options["body"] = b"{bad-json"
    elif fault == "bad_status":
        payload["Status"] = 2
    elif fault == "boolean_status":
        payload["Status"] = False
    elif fault == "truncated":
        payload["TC"] = True
    elif fault == "nonboolean_truncated":
        payload["TC"] = 0
    elif fault == "wrong_question":
        payload["Question"][0]["name"] = "other.example"
    elif fault == "double_trailing_dot":
        payload["Question"][0]["name"] = ws.HOST + ".."
    elif fault == "bad_question_type":
        payload["Question"][0]["type"] = True
    elif fault == "no_answers":
        payload["Answer"] = []
    elif fault == "cname_only":
        payload["Answer"] = [{"type": 5, "data": "official-cname.example."}]
    else:
        payload["Answer"][0]["type"] = True
    calls, raw, tls, response, _ = fixture_doh(monkeypatch, payload, **options)
    with pytest.raises(OSError):
        ws._resolve_doh_public_ips(time.monotonic() + 1)
    assert len(calls["targets"]) == 1  # No redirects or alternate resolvers.
    assert raw.closed and tls.closed and response.closed and calls["client"].closed
    assert sum(calls["reads"]) <= ws._MAX_DOH_BYTES + 1 + 4096


def test_doh_deadline_closes_tls_and_returns_without_body_read(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(ws.time, "monotonic", lambda: now[0])
    def expired():
        now[0] = 2.0
    calls, raw, tls, response, _ = fixture_doh(monkeypatch, after_headers=expired)
    with pytest.raises(TimeoutError):
        ws._resolve_doh_public_ips(1.0)
    assert not calls["reads"] and raw.closed and tls.closed and response.closed


def test_doh_tls_validation_failure_never_sends_http_query(monkeypatch):
    calls, raw, tls, response, context = fixture_doh(monkeypatch)
    def invalid_certificate(*args, **kwargs):
        raise ws.ssl.SSLCertVerificationError("synthetic invalid certificate")
    monkeypatch.setattr(context, "wrap_socket", invalid_certificate)
    with pytest.raises(OSError):
        ws._resolve_doh_public_ips(time.monotonic() + 1)
    assert raw.closed and not calls["requests"] and not calls["http"]
