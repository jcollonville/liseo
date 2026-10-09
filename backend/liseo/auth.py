"""Admin session cookie. The ByteBooks password is not part of the session."""

from __future__ import annotations

import hashlib
import secrets

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from liseo.config import Settings

COOKIE = "liseo_session"
MAX_AGE = 12 * 60 * 60


def serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="liseo-session")


def passwords_match(given: str, expected: str) -> bool:
    return secrets.compare_digest(
        hashlib.sha256(given.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )


def issue_session(response: Response, settings: Settings) -> None:
    token = serializer(settings).dumps({"ok": True})
    response.set_cookie(
        COOKIE,
        token,
        max_age=MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session(response: Response, settings: Settings) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict", secure=settings.cookie_secure)


def require_session(request: Request, settings: Settings) -> None:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    try:
        serializer(settings).loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=401, detail="Session invalide.") from exc


def require_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is None or origin.rstrip("/") not in settings.allowed_origins:
        raise HTTPException(status_code=403, detail="Origine refusée.")
