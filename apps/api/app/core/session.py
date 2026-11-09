from __future__ import annotations

import uuid

from fastapi import Request, Response

SESSION_COOKIE = "lernyra_sid"
SESSION_MAX_AGE = 60 * 60 * 24 * 30


def get_session_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def ensure_session_id(request: Request, response: Response) -> str:
    sid = get_session_id(request)
    if sid:
        return sid
    sid = uuid.uuid4().hex
    # Lax works for same-site local http; Secure+None needed only for cross-site HTTPS.
    secure = request.url.scheme == "https"
    response.set_cookie(
        key=SESSION_COOKIE,
        value=sid,
        httponly=True,
        samesite="none" if secure else "lax",
        secure=secure,
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return sid
