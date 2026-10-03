"""Bound outbound requests to public HTTPS sources or explicitly configured local providers."""

import ipaddress
import socket
import ssl
from urllib.parse import urlparse

import httpcore
import httpx


def validate_url(url: str, *, local_provider: bool = False, resolve: bool = True) -> str:
    parts = urlparse(url)
    if parts.username or parts.password or parts.fragment or not parts.hostname:
        raise ValueError("URL 不得包含凭据、fragment 或缺少主机")
    host = parts.hostname.lower()
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if parts.scheme != "https" and not (local_provider and loopback and parts.scheme == "http"):
        raise ValueError("来源须为 HTTPS；仅显式配置的本机 provider 支持 HTTP")
    if loopback:
        if not local_provider:
            raise ValueError("不允许访问本机来源")
        return url
    if resolve:
        try:
            addresses = socket.getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("来源主机无法解析") from exc
        if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("不允许访问私网、保留或特殊地址")
    return url


class PublicNetworkBackend(httpcore.SyncBackend):
    """Connect only to the very addresses checked in this connection attempt.

    TLS SNI/hostname verification and HTTP Host remain the original host in
    httpcore; only the TCP target is changed to the resolved public IP.
    """
    def __init__(self, local_provider: bool = False):
        self.local_provider = local_provider

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        host = host.decode() if isinstance(host, bytes) else host
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(address[4][0] for address in addresses))
        allowed_local = self.local_provider and host.lower() in {"localhost", "127.0.0.1", "::1"}
        if not ips or any(not ipaddress.ip_address(ip).is_global and not (allowed_local and ipaddress.ip_address(ip).is_loopback) for ip in ips):
            raise httpcore.ConnectError("出站连接被私网/保留地址策略拒绝")
        last_error = None
        for address in ips:
            try:
                return super().connect_tcp(address, port, timeout, local_address, socket_options)
            except httpcore.ConnectError as exc:
                last_error = exc
        raise last_error or httpcore.ConnectError("无法连接公开来源")


def public_transport(*, local_provider: bool = False) -> httpx.HTTPTransport:
    # HTTPTransport's public interface maps httpcore errors for us. The only
    # replaced implementation detail is its connection pool, tested with the
    # project's locked httpx/httpcore versions.
    transport = httpx.HTTPTransport(trust_env=False, retries=0)
    transport._pool.close()
    transport._pool = httpcore.ConnectionPool(ssl_context=ssl.create_default_context(),
                                             network_backend=PublicNetworkBackend(local_provider), retries=0)
    return transport


def safe_get(url: str, *, max_bytes: int = 20 * 1024 * 1024) -> tuple[bytes, str, str]:
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False, transport=public_transport()) as client:
        for _ in range(6):
            validate_url(url)
            with client.stream("GET", url, headers={"User-Agent": "VideoAgents/0.1 source-verification"}) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ValueError("下载文件超过限制")
                return bytes(data), response.headers.get("content-type", "").split(";")[0], url
    raise ValueError("来源重定向次数超过限制")
