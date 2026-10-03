import hmac
import os
import secrets
from urllib.parse import urlparse

from fastapi import HTTPException, Request

DEFAULT_ORIGINS = {
    f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (8000, 5173, 4173)
}


class LocalSession:
    def __init__(self):
        self.secret = secrets.token_bytes(32)
        self.origins = set(DEFAULT_ORIGINS)
        for value in os.environ.get("VIDEOAGENTS_ALLOWED_ORIGINS", "").split(","):
            if value.strip():
                parts = urlparse(value.strip())
                if parts.scheme not in {"http", "https"} or parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
                    raise ValueError("只允许明确的本机前端 Origin")
                self.origins.add(value.strip().rstrip("/"))

    def token(self, session_id: str) -> str:
        return hmac.new(self.secret, session_id.encode(), "sha256").hexdigest()

    def cookie(self, session_id: str) -> str:
        return session_id + "." + self.token("session:" + session_id)

    def validate_origin(self, request: Request):
        if request.headers.get("origin") and request.headers["origin"] not in self.origins:
            raise HTTPException(403, "请求来源未授权")
        site = request.headers.get("sec-fetch-site")
        if site == "cross-site":
            raise HTTPException(403, "拒绝跨站请求")

    def require(self, request: Request):
        self.validate_origin(request)
        cookie = request.cookies.get("videoagents_session", "")
        try:
            session_id, signature = cookie.split(".", 1)
        except ValueError:
            raise HTTPException(401, "请先建立本机会话")
        if not hmac.compare_digest(signature, self.token("session:" + session_id)):
            raise HTTPException(401, "本机会话已失效，请刷新页面")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf = request.headers.get("x-csrf-token", "")
            if not hmac.compare_digest(csrf, self.token("csrf:" + session_id)):
                raise HTTPException(403, "请求缺少有效 CSRF token")
