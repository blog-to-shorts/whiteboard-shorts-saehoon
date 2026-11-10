"""외부 공유용 접근 제어.

DEMO_PASSWORD 가 설정되면 모든 화면·API 에 HTTP Basic 인증을 건다(브라우저가 아이디·비밀번호 창을 띄움).
DEMO_MAX_JOBS_PER_DAY 로 하루 새 작업 수를 제한해 API 비용이 무한정 늘지 않게 한다.
둘 다 비어 있으면(로컬 개발) 아무 제한도 걸지 않는다.
"""

from __future__ import annotations

import base64
import secrets
from datetime import date

from fastapi import HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pipeline.config import env


def _creds() -> tuple[str, str] | None:
    pw = env("DEMO_PASSWORD")
    return (env("DEMO_USER", "demo"), pw) if pw else None


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        creds = _creds()
        if creds is None or request.method == "OPTIONS":
            return await call_next(request)
        header = request.headers.get("authorization", "")
        if header.lower().startswith("basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            except (ValueError, UnicodeDecodeError):
                user, pw = "", ""
            if secrets.compare_digest(user, creds[0]) and secrets.compare_digest(pw, creds[1]):
                return await call_next(request)
        return PlainTextResponse("로그인이 필요합니다", status_code=401,
                                 headers={"WWW-Authenticate": 'Basic realm="whiteboard-shorts", charset="UTF-8"'})


_today = {"day": None, "count": 0}


def check_daily_quota() -> None:
    """새 작업 생성 전에 호출. 한도를 넘으면 429."""
    limit = int(env("DEMO_MAX_JOBS_PER_DAY", "0") or 0)
    if not limit:
        return
    today = date.today().isoformat()
    if _today["day"] != today:
        _today.update(day=today, count=0)
    if _today["count"] >= limit:
        raise HTTPException(429, f"오늘 만들 수 있는 영상 {limit}편을 모두 썼어요. 내일 다시 시도해 주세요.")
    _today["count"] += 1


def quota_status() -> dict:
    limit = int(env("DEMO_MAX_JOBS_PER_DAY", "0") or 0)
    used = _today["count"] if _today["day"] == date.today().isoformat() else 0
    return {"limit": limit or None, "used": used, "protected": _creds() is not None}
