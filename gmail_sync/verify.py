"""Verify Gmail API setup by authenticating and listing labels.

Usage:
    python3 -m gmail_sync.verify

First run opens a browser for OAuth consent and writes token.json.
Subsequent runs reuse the cached token.
"""
from .client import GmailClient


def main() -> None:
    client = GmailClient()
    labels = client.list_labels()

    user_labels = sorted(
        (lbl for lbl in labels if lbl.get("type") == "user"),
        key=lambda lbl: lbl["name"],
    )
    system_count = sum(1 for lbl in labels if lbl.get("type") == "system")

    print(f"Auth OK. {len(user_labels)} user labels, {system_count} system labels.\n")
    print("User labels:")
    for lbl in user_labels:
        print(f"  {lbl['name']}  (id={lbl['id']})")


if __name__ == "__main__":
    main()
