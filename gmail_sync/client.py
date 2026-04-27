"""Thin wrapper around the Gmail API."""
import base64
from typing import Iterator

from googleapiclient.discovery import build

from .auth import get_credentials


class GmailClient:
    def __init__(self) -> None:
        self._service = build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)

    def list_labels(self) -> list[dict]:
        result = self._service.users().labels().list(userId="me").execute()
        return result.get("labels", [])

    def resolve_label_id(self, name: str) -> str:
        for lbl in self.list_labels():
            if lbl["name"] == name:
                return lbl["id"]
        raise KeyError(f"No label named {name!r}")

    def iter_message_ids(
        self,
        label_ids: list[str] | None = None,
        query: str | None = None,
        max_total: int | None = None,
    ) -> Iterator[str]:
        """Yield message IDs matching labels/query. Paginates automatically."""
        page_token = None
        yielded = 0
        while True:
            kwargs = {"userId": "me", "maxResults": 500}
            if label_ids:
                kwargs["labelIds"] = label_ids
            if query:
                kwargs["q"] = query
            if page_token:
                kwargs["pageToken"] = page_token
            result = self._service.users().messages().list(**kwargs).execute()
            for msg in result.get("messages", []):
                yield msg["id"]
                yielded += 1
                if max_total is not None and yielded >= max_total:
                    return
            page_token = result.get("nextPageToken")
            if not page_token:
                return

    def get_message(self, msg_id: str, fmt: str = "full") -> dict:
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=msg_id, format=fmt)
            .execute()
        )

    def get_attachment(self, msg_id: str, attachment_id: str) -> bytes:
        result = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=msg_id, id=attachment_id)
            .execute()
        )
        return base64.urlsafe_b64decode(result["data"])


def header(message: dict, name: str) -> str | None:
    for h in message.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def walk_parts(payload: dict) -> Iterator[dict]:
    yield payload
    for part in payload.get("parts", []) or []:
        yield from walk_parts(part)


_TAG_RE = None


def _html_to_text(html: str) -> str:
    import html as html_mod
    import re

    global _TAG_RE
    if _TAG_RE is None:
        _TAG_RE = re.compile(r"<[^>]+>")

    # Drop entire <style>, <script>, <head> blocks (including their content).
    for tag in ("style", "script", "head"):
        html = re.sub(
            rf"<{tag}\b[^>]*>.*?</{tag}>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    # Strip remaining tags.
    text = _TAG_RE.sub(" ", html)
    # Decode HTML entities (&nbsp;, &amp;, ...).
    text = html_mod.unescape(text)
    # Collapse whitespace aggressively while preserving line breaks.
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(message: dict) -> str:
    """Best-effort plaintext body (prefers text/plain, falls back to text/html stripped)."""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in walk_parts(message.get("payload", {})):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if not data:
            continue
        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        if mime == "text/plain":
            plain_parts.append(decoded)
        elif mime == "text/html":
            html_parts.append(decoded)
    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return _html_to_text("\n".join(html_parts))
    return ""


def list_attachments(message: dict) -> list[dict]:
    out = []
    for part in walk_parts(message.get("payload", {})):
        filename = part.get("filename")
        att_id = part.get("body", {}).get("attachmentId")
        if filename and att_id:
            out.append({
                "filename": filename,
                "attachment_id": att_id,
                "mime_type": part.get("mimeType"),
                "size": part.get("body", {}).get("size"),
            })
    return out
