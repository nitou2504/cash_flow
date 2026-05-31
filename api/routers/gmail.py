import json
import os
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.deps import get_current_user, get_db

router = APIRouter(tags=["gmail"])


# ── Models ─────────────────────────────────────────────────────────────


class GmailCredentialsIn(BaseModel):
    client_id: str
    client_secret: str
    project_id: str = "cash-flow"


# ── Helpers ────────────────────────────────────────────────────────────


def _build_redirect_uri(request: Request) -> str:
    base = os.environ.get("GMAIL_REDIRECT_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/api/gmail/callback"
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    return f"{proto}://{host}/api/gmail/callback"


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/api/gmail/status", dependencies=[Depends(get_current_user)])
def gmail_status(request: Request):
    from gmail_sync.auth import get_token_status
    status = get_token_status()
    status["redirect_uri"] = _build_redirect_uri(request)
    return status


@router.post("/api/gmail/credentials", dependencies=[Depends(get_current_user)])
def gmail_save_credentials(body: GmailCredentialsIn):
    from gmail_sync.auth import save_credentials_file
    save_credentials_file(body.client_id, body.client_secret, body.project_id)
    return {"ok": True}


@router.delete("/api/gmail/credentials", dependencies=[Depends(get_current_user)])
def gmail_delete_credentials():
    from gmail_sync.auth import CREDENTIALS_FILE, TOKEN_FILE
    CREDENTIALS_FILE.unlink(missing_ok=True)
    TOKEN_FILE.unlink(missing_ok=True)
    return {"ok": True}


@router.get("/api/gmail/auth-url", dependencies=[Depends(get_current_user)])
def gmail_auth_url(request: Request, conn=Depends(get_db)):
    from gmail_sync.auth import CREDENTIALS_FILE, create_web_flow

    if not CREDENTIALS_FILE.exists():
        raise HTTPException(400, "No credentials.json — save OAuth client credentials first")

    redirect_uri = _build_redirect_uri(request)
    flow = create_web_flow(redirect_uri)
    state = secrets.token_urlsafe(32)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("gmail_oauth_state", json.dumps({
            "state": state,
            "redirect_uri": redirect_uri,
            "code_verifier": flow.code_verifier,
            "ts": time.time(),
        })),
    )
    conn.commit()
    return {"auth_url": auth_url}


@router.get("/api/gmail/callback")
def gmail_callback(code: str, state: str, conn=Depends(get_db)):
    from gmail_sync.auth import TOKEN_FILE, create_web_flow

    row = conn.execute("SELECT value FROM settings WHERE key = 'gmail_oauth_state'").fetchone()
    if not row:
        raise HTTPException(403, "No pending OAuth flow")
    saved = json.loads(row[0])
    if saved.get("state") != state:
        raise HTTPException(403, "Invalid OAuth state")
    if time.time() - saved.get("ts", 0) > 600:
        raise HTTPException(403, "OAuth state expired")

    flow = create_web_flow(saved["redirect_uri"])
    flow.code_verifier = saved.get("code_verifier")
    flow.fetch_token(code=code)
    TOKEN_FILE.write_text(flow.credentials.to_json())

    conn.execute("DELETE FROM settings WHERE key = 'gmail_oauth_state'")
    conn.commit()

    return RedirectResponse("/settings?gmail=connected")


@router.post("/api/gmail/disconnect", dependencies=[Depends(get_current_user)])
def gmail_disconnect():
    from gmail_sync.auth import revoke_token
    revoke_token()
    return {"ok": True}
