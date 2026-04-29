import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt

from fastapi import APIRouter, HTTPException, Request, Response, status
from jose import jwt
from pydantic import BaseModel

ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = int(os.getenv("WEB_TOKEN_EXPIRY_HOURS", "24"))
SECRET_KEY = os.getenv("WEB_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)

_raw_password = os.getenv("WEB_PASSWORD", "")
PASSWORD_HASH = _bcrypt.hashpw(_raw_password.encode(), _bcrypt.gensalt()) if _raw_password else b""

DEV_MODE = os.getenv("WEB_DEV_MODE", "false").lower() in ("true", "1")

_login_attempts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


def _check_rate_limit(ip: str):
    now = time.time()
    attempts = _login_attempts[ip]
    _login_attempts[ip] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    if len(_login_attempts[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )


def _create_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)
    return jwt.encode({"sub": "owner", "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _set_cookie(response: Response, token: str):
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="strict",
        secure=not DEV_MODE,
        max_age=TOKEN_EXPIRY_HOURS * 3600,
        path="/",
    )


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response):
    if not PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WEB_PASSWORD not configured",
        )
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)
    if not _bcrypt.checkpw(body.password.encode(), PASSWORD_HASH):
        _login_attempts[ip].append(time.time())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    _login_attempts.pop(ip, None)
    token = _create_token()
    _set_cookie(response, token)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    from api.deps import get_current_user
    try:
        get_current_user(request)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"authenticated": True}
