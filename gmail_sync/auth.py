"""OAuth flow and credential caching for the Gmail API."""
import json
import os
from pathlib import Path

import requests as http_requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = _ROOT / "credentials.json"
TOKEN_FILE = _ROOT / "token.json"

# Fixed port so SSH tunnels (ssh -L PORT:localhost:PORT) can forward the
# OAuth redirect back to this machine. Override with GMAIL_OAUTH_PORT if 8765
# collides with something.
OAUTH_PORT = int(os.environ.get("GMAIL_OAUTH_PORT", "8765"))


def get_credentials() -> Credentials:
    creds: Credentials | None = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
        return creds

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"{CREDENTIALS_FILE.name} not found at {CREDENTIALS_FILE}. "
            "Follow gmail_sync/SETUP.md to create an OAuth client in Google Cloud."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    # host=localhost so Google accepts the loopback redirect_uri; bind_addr=0.0.0.0
    # so the callback server is reachable over Tailscale when authing from a laptop.
    creds = flow.run_local_server(
        host="localhost",
        bind_addr="0.0.0.0",
        port=OAUTH_PORT,
        open_browser=False,
    )
    TOKEN_FILE.write_text(creds.to_json())
    return creds


# ── Web flow helpers ──────────────────────────────────────────────────


def get_token_status() -> dict:
    """Return current Gmail token status for the web UI."""
    if not CREDENTIALS_FILE.exists():
        return {"has_credentials": False, "connected": False}
    if not TOKEN_FILE.exists():
        return {"has_credentials": True, "connected": False}
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception:
        return {"has_credentials": True, "connected": False}
    expired = bool(creds.expired)
    if expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            expired = False
        except Exception:
            pass
    return {
        "has_credentials": True,
        "connected": True,
        "valid": creds.valid,
        "expired": expired,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def create_web_flow(redirect_uri: str) -> Flow:
    """Create OAuth2 web flow for browser-based auth."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError("credentials.json not found")
    return Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE), scopes=SCOPES, redirect_uri=redirect_uri,
    )


def save_credentials_file(client_id: str, client_secret: str, project_id: str = "cash-flow"):
    """Write credentials.json from user-provided OAuth client values."""
    config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "project_id": project_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [],
        }
    }
    CREDENTIALS_FILE.write_text(json.dumps(config, indent=2))


def revoke_token() -> bool:
    """Revoke current token and delete token.json."""
    if not TOKEN_FILE.exists():
        return False
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.token:
            http_requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": creds.token},
                timeout=5,
            )
    except Exception:
        pass
    TOKEN_FILE.unlink(missing_ok=True)
    return True
