"""OAuth flow and credential caching for the Gmail API."""
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

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
