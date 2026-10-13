"""Source decoding and bounded body extraction use the public download path."""

import hashlib
import socket

import httpx
import pytest

from videoagents.providers import network
from videoagents.tools.sources import fetch_source

SOURCE = "https://evidence.example/article"


def install_response(monkeypatch, body, content_type="text/html"):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))])

    def response(request):
        return httpx.Response(200, content=body, headers={"Content-Type": content_type})

    monkeypatch.setattr(network, "public_transport", lambda: httpx.MockTransport(response))


def test_source_decodes_cnr_style_declared_gb2312_and_preserves_raw_proof(tmp_path, monkeypatch):
    # The live CNR page sends bare text/html and declares gb2312 in its HTML head.
    body = ('<meta charset="gb2312"><title>上海警方破获虚假APP诈骗案</title>'
            '<p>冒充境外投资平台，警方提示防范诈骗。</p>'
            '<img src="/photo.jpg" alt="警方反诈提示">').encode("gb2312")
    install_response(monkeypatch, body)
    path = tmp_path / "source.html"

    receipt = fetch_source(SOURCE, path)

    assert receipt["title"] == "上海警方破获虚假APP诈骗案"
    assert "冒充境外投资平台" in receipt["text"]
    assert "\ufffd" not in receipt["text"]
    assert receipt["images"][0]["description"] == "警方反诈提示"
    assert receipt["content_type"] == "text/html"
    assert path.read_bytes() == body
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("html,encoding,content_type", [
    ('<meta charset="GBK"><p>警方提示防范诈骗。</p>', "gbk", "text/html"),
    ('<meta content="text/html; charset=gb2312" http-equiv="Content-Type">'
     '<p>警方提示防范诈骗。</p>', "gb2312", "text/html"),
    ("<p>警方提示防范诈骗。</p>", "gbk", 'text/html; charset="gbk"'),
    ('<meta charset="gb2312"><p>警方提示防范诈骗。</p>', "utf-8", "text/html; charset=utf-8"),
    ("警方提示防范诈骗。", "gb2312", "text/plain; charset=gb2312"),
    ('<meta charset="invalid-label"><p>警方提示防范诈骗。</p>', "utf-8", "text/html"),
    ('<meta charset="utf-8"><p>警方提示防范诈骗。</p>', "utf-8", "text/html; charset=invalid-label"),
    ('<meta charset="gb2312"><p>警方提示防范诈骗。</p>', "utf-8-sig", "text/html; charset=gb2312"),
    ("<p>警方提示防范诈骗。</p>", "utf-16", "text/html; charset=gb2312"),
    ("<p>警方提示防范诈骗。</p>", "utf-32", "text/html; charset=gb2312"),
    ("<p>警方提示防范诈骗。</p>", "utf-8", "text/html; charset=base64_codec"),
    ("<p>警方提示防范诈骗。</p>", "utf-8", "application/xhtml+xml"),
])
def test_source_honors_declared_encodings_and_keeps_utf8_default(
        tmp_path, monkeypatch, html, encoding, content_type):
    install_response(monkeypatch, html.encode(encoding), content_type)

    receipt = fetch_source(SOURCE, tmp_path / "source.html")

    assert "警方提示防范诈骗。" in receipt["text"]
    assert "\ufffd" not in receipt["text"]


def test_source_reads_official_report_late_section_with_a_finite_body_limit(tmp_path, monkeypatch):
    # Live Anthropic report: GTG-15001 first appears after character 227,000.
    evidence = "GTG-15001: 4,700 accounts, 25,000 messages, $2.36."
    text = "intro " * 38000 + evidence
    install_response(monkeypatch, f"<p>{text}</p>".encode())

    receipt = fetch_source(SOURCE, tmp_path / "source.html")

    assert evidence in receipt["text"]


def test_source_text_remains_bounded_at_256k_characters(tmp_path, monkeypatch):
    install_response(monkeypatch, b"<p>" + b"a" * (300 * 1024) + b"</p>")

    receipt = fetch_source(SOURCE, tmp_path / "source.html")

    assert len(receipt["text"]) == 256 * 1024


def test_source_download_still_rejects_more_than_three_mib(tmp_path, monkeypatch):
    install_response(monkeypatch, b"x" * (3 * 1024 * 1024 + 1))
    path = tmp_path / "source.html"

    with pytest.raises(ValueError, match="下载文件超过限制"):
        fetch_source(SOURCE, path)

    assert not path.exists()


def test_safe_get_keeps_default_mime_tuple_contract(monkeypatch):
    install_response(monkeypatch, b"plain", "text/plain; charset=gb2312")

    assert network.safe_get(SOURCE) == (b"plain", "text/plain", SOURCE)


def test_source_redirect_to_private_address_is_rejected_before_fetch(tmp_path, monkeypatch):
    calls = []
    install_response(monkeypatch, b"")

    def response(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://127.0.0.1/private"})

    monkeypatch.setattr(network, "public_transport", lambda: httpx.MockTransport(response))
    with pytest.raises(ValueError, match="本机来源"):
        fetch_source(SOURCE, tmp_path / "source.html")

    assert calls == [SOURCE]
