"""Print sample messages from a label to eyeball format.

Usage:
    python3 -m gmail_sync.inspect_label "Consumos/Diners" --limit 2
"""
import argparse

from .client import GmailClient, extract_text, header, list_attachments


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--query", default=None, help="Gmail search query (e.g. 'after:2026/03/01')")
    ap.add_argument("--body-chars", type=int, default=1200)
    args = ap.parse_args()

    gc = GmailClient()
    label_id = gc.resolve_label_id(args.label)

    ids = list(gc.iter_message_ids(label_ids=[label_id], query=args.query, max_total=args.limit))
    print(f"Label {args.label!r} → {len(ids)} message(s) fetched.\n")

    for i, mid in enumerate(ids, 1):
        msg = gc.get_message(mid)
        print("=" * 70)
        print(f"[{i}/{len(ids)}] id={mid}")
        for h in ("From", "Subject", "Date"):
            print(f"  {h}: {header(msg, h)}")
        atts = list_attachments(msg)
        if atts:
            print(f"  Attachments: {[(a['filename'], a['size']) for a in atts]}")
        body = extract_text(msg).strip()
        if len(body) > args.body_chars:
            body = body[: args.body_chars] + f"\n... [+{len(body) - args.body_chars} chars truncated]"
        print(f"\n{body}\n")


if __name__ == "__main__":
    main()
