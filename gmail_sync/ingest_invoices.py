"""Periodic Gmail ingest — pulls Facturas label into invoices.db.

Usage:
    # First-time bulk import
    python3 -m gmail_sync.ingest_invoices --after 2025-01-01

    # Incremental (recommended for periodic runs)
    python3 -m gmail_sync.ingest_invoices --since-last

    # Dry run (show what would be imported, touch no DB)
    python3 -m gmail_sync.ingest_invoices --since-last --dry-run

    # List emails flagged as unparsed so you can handle them
    python3 -m gmail_sync.ingest_invoices --show-unparsed

Idempotent: already-ingested messages (by Gmail msg_id) are skipped on rerun.
Messages that can't be parsed (no XML attached, parse failure, ZIP without XML)
are recorded in `unparsed_facturas` for manual review.
"""
import argparse
import io
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from cashflow.database import create_connection, initialize_database
from cashflow.invoice_repository import (
    get_ingested_msg_ids,
    get_latest_issue_date,
    list_unparsed,
    record_unparsed,
    upsert_invoice,
)

from .client import GmailClient, header, list_attachments
from .invoice import _cached_xml_path, parse_sri_factura


# --- Helpers ---------------------------------------------------------------

def _to_gmail_date(d: str) -> str:
    """Gmail search uses YYYY/MM/DD syntax in after:/before: operators."""
    return d.replace("-", "/")


def _gather_xml_sources(gc: GmailClient, msg: dict, mid: str) -> list[tuple[str, bytes]]:
    """Download + cache all XML bytes from direct attachments and inner ZIPs."""
    atts = list_attachments(msg)
    out: list[tuple[str, bytes]] = []
    for att in atts:
        fn = att["filename"]
        low = fn.lower()
        cache = _cached_xml_path(fn)
        if low.endswith(".xml"):
            if cache.exists():
                out.append((fn, cache.read_bytes()))
            else:
                data = gc.get_attachment(mid, att["attachment_id"])
                cache.write_bytes(data)
                out.append((fn, data))
        elif low.endswith(".zip"):
            if cache.exists():
                zdata = cache.read_bytes()
            else:
                zdata = gc.get_attachment(mid, att["attachment_id"])
                cache.write_bytes(zdata)
            try:
                with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".xml"):
                            inner = zf.read(name)
                            _cached_xml_path(name).write_bytes(inner)
                            out.append((name, inner))
            except zipfile.BadZipFile:
                pass
    return out


def _classify_missing_reason(atts: list[dict]) -> str:
    """Decide why we got no XML: attachments we saw, but no XML."""
    exts = {Path(a["filename"]).suffix.lower().lstrip(".") for a in atts if a.get("filename")}
    if not exts:
        return "no_attachment"
    if "zip" in exts:
        return "zip_no_xml"
    if "pdf" in exts:
        return "no_xml"
    return "other"


# --- Core ingest loop ------------------------------------------------------

def ingest_messages(
    gc: GmailClient,
    label_id: str,
    query: str,
    conn,
    *,
    dry_run: bool = False,
    skip_known: bool = True,
    progress_every: int = 25,
) -> dict:
    """Walk Gmail messages matching label+query; upsert parseable invoices,
    flag unparseable ones. Returns per-category counts."""
    stats = {
        "seen": 0,
        "skipped_known": 0,
        "upserted": 0,
        "unparsed_logged": 0,
        "parse_failed": 0,
    }
    known_msg_ids = get_ingested_msg_ids(conn) if skip_known else set()

    msg_ids = list(gc.iter_message_ids(label_ids=[label_id], query=query))
    total = len(msg_ids)
    print(f"  {total} messages match; {len(known_msg_ids)} already in DB")

    for i, mid in enumerate(msg_ids, 1):
        stats["seen"] += 1
        if mid in known_msg_ids:
            stats["skipped_known"] += 1
            continue

        msg = gc.get_message(mid)
        subject = header(msg, "Subject") or ""
        from_addr = header(msg, "From") or ""
        internal_date = int(msg.get("internalDate", 0) or 0) / 1000
        received_at = (
            datetime.fromtimestamp(internal_date).isoformat(timespec="seconds")
            if internal_date else None
        )
        atts = list_attachments(msg)
        pdf_atts = [a for a in atts if a["filename"].lower().endswith(".pdf")]
        has_pdf = bool(pdf_atts)
        pdf_filename = pdf_atts[0]["filename"] if pdf_atts else ""

        xml_sources = _gather_xml_sources(gc, msg, mid)

        if not xml_sources:
            stats["unparsed_logged"] += 1
            if not dry_run:
                record_unparsed(
                    conn, mid, subject, from_addr, received_at,
                    reason=_classify_missing_reason(atts),
                    has_pdf=has_pdf,
                )
            continue

        upserted_any = False
        for xml_name, xml_bytes in xml_sources:
            inv = parse_sri_factura(xml_bytes)
            if inv is None or not inv.invoice_number:
                continue
            inv.msg_id = mid
            inv.subject = subject
            inv.pdf_filename = pdf_filename
            inv.email_subject = subject
            inv.email_from = from_addr
            if not dry_run:
                upsert_invoice(
                    conn, inv,
                    xml_path=str(_cached_xml_path(xml_name)),
                    pdf_path=pdf_filename or None,
                )
            stats["upserted"] += 1
            upserted_any = True

        if not upserted_any:
            stats["parse_failed"] += 1
            stats["unparsed_logged"] += 1
            if not dry_run:
                record_unparsed(
                    conn, mid, subject, from_addr, received_at,
                    reason="parse_failed",
                    has_pdf=has_pdf,
                    notes=f"{len(xml_sources)} XML(s) attached, none parseable",
                )

        if progress_every and i % progress_every == 0:
            print(f"  [{i}/{total}] upserted={stats['upserted']} "
                  f"unparsed={stats['unparsed_logged']} skipped={stats['skipped_known']}")

    return stats


# --- CLI -------------------------------------------------------------------

def _compute_after(conn, user_after: Optional[str], since_last: bool) -> str:
    """Pick the Gmail `after:` date. --since-last wins over --after."""
    if since_last:
        last = get_latest_issue_date(conn)
        if last:
            # Re-fetch a week back to cover late-arriving invoices / clock skew.
            back = last - timedelta(days=7)
            return back.isoformat()
        return "2025-01-01"  # first-run fallback
    return user_after or "2025-01-01"


def _print_unparsed(conn, reason_filter: Optional[str]) -> None:
    rows = list_unparsed(conn, reason=reason_filter)
    if not rows:
        print("No unresolved unparsed emails.")
        return
    print(f"Unresolved unparsed Facturas emails: {len(rows)}\n")
    for r in rows:
        pdf_mark = " [pdf]" if r["has_pdf"] else ""
        subj = (r["subject"] or "")[:70]
        frm = (r["from_addr"] or "").split("<")[0].strip() or (r["from_addr"] or "")
        print(f"  {r['received_at'] or '?':<19}  {r['reason']:<14}{pdf_mark}  {frm[:30]:<30}  {subj}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ingest Facturas from Gmail into invoices.db"
    )
    ap.add_argument("--after", help="YYYY-MM-DD (default: 2025-01-01 or --since-last)")
    ap.add_argument("--before", help="YYYY-MM-DD (Gmail 'before' is exclusive)")
    ap.add_argument("--since-last", action="store_true",
                    help="Start from the latest issue_date in DB (minus 7 days)")
    ap.add_argument("--label", default="Facturas")
    ap.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    ap.add_argument("--db", default="cash_flow.db", help="Override DB path")
    ap.add_argument("--show-unparsed", action="store_true",
                    help="List unresolved unparsed emails and exit")
    ap.add_argument("--unparsed-reason",
                    help="Filter --show-unparsed by reason (e.g. no_attachment)")
    args = ap.parse_args()

    db_path = args.db
    initialize_database(db_path)
    conn = create_connection(db_path)
    try:
        if args.show_unparsed:
            _print_unparsed(conn, args.unparsed_reason)
            return 0

        gc = GmailClient()
        label_id = gc.resolve_label_id(args.label)

        after = _compute_after(conn, args.after, args.since_last)
        query = f"after:{_to_gmail_date(after)}"
        if args.before:
            query += f" before:{_to_gmail_date(args.before)}"

        print(f"Ingest — label={args.label!r}  query={query}  db={db_path}"
              + ("  [DRY RUN]" if args.dry_run else ""))
        stats = ingest_messages(gc, label_id, query, conn, dry_run=args.dry_run)

        print("\n=== Summary ===")
        print(f"  seen:                  {stats['seen']}")
        print(f"  skipped (already in DB): {stats['skipped_known']}")
        print(f"  invoices upserted:     {stats['upserted']}")
        print(f"  unparsed logged:       {stats['unparsed_logged']}"
              f"  (of which parse failures: {stats['parse_failed']})")
        if stats["unparsed_logged"]:
            print("\nReview with: python3 -m gmail_sync.ingest_invoices --show-unparsed")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
