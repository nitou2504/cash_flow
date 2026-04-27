"""Periodic Gmail ingest — pulls Consumos/* labels into consumos.db.

Usage:
    # First-time bulk import
    python3 -m gmail_sync.ingest_consumos --after 2025-01-01

    # Incremental (recommended for periodic runs)
    python3 -m gmail_sync.ingest_consumos --since-last

    # Dry run (show what would be imported, touch no DB)
    python3 -m gmail_sync.ingest_consumos --since-last --dry-run

    # Show unparsed emails
    python3 -m gmail_sync.ingest_consumos --show-unparsed

    # Re-match unmatched consumos against invoices
    python3 -m gmail_sync.ingest_consumos --rematch

    # Limit to specific labels
    python3 -m gmail_sync.ingest_consumos --since-last --labels Consumos/Cash

Idempotent: already-ingested messages (by Gmail msg_id) are skipped.
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import Callable, Optional

from cashflow.config import CONSUMOS_DB_PATH, INVOICES_DB_PATH
from cashflow.consumo_database import create_consumo_connection, initialize_consumos_database
from cashflow.consumo_repository import (
    find_unmatched,
    get_ingested_msg_ids,
    get_latest_purchased_at,
    list_unparsed,
    record_unparsed,
    set_invoice_match,
    upsert_consumo,
)

from .client import GmailClient, extract_text, header
from .parsers import LABEL_TO_PARSER, EmailTxn, clear_warnings, diagnose_parse_failure, get_warnings


def _to_gmail_date(d: str) -> str:
    return d.replace("-", "/")


def ingest_label(
    gc: GmailClient,
    label_name: str,
    label_id: str,
    parser_fn: Callable,
    query: str,
    conn,
    *,
    dry_run: bool = False,
    skip_known: bool = True,
    progress_every: int = 25,
) -> dict:
    stats = {
        "seen": 0,
        "skipped_known": 0,
        "upserted": 0,
        "unparsed_logged": 0,
    }
    known_msg_ids = get_ingested_msg_ids(conn) if skip_known else set()

    msg_ids = list(gc.iter_message_ids(label_ids=[label_id], query=query))
    total = len(msg_ids)
    print(f"  {label_name}: {total} messages match; {len(known_msg_ids)} already in DB")

    for i, mid in enumerate(msg_ids, 1):
        stats["seen"] += 1
        if mid in known_msg_ids:
            stats["skipped_known"] += 1
            continue

        msg = gc.get_message(mid)
        subject = header(msg, "Subject") or ""
        from_addr = header(msg, "From") or ""
        body = extract_text(msg)
        internal_date = int(msg.get("internalDate", 0) or 0) / 1000
        received_at = (
            datetime.fromtimestamp(internal_date).isoformat(timespec="seconds")
            if internal_date else None
        )

        txn = parser_fn(mid, subject, body)

        if txn:
            if not dry_run:
                upsert_consumo(conn, txn, label=label_name)
            stats["upserted"] += 1
        else:
            reason = diagnose_parse_failure(mid, label_name, subject, body)
            stats["unparsed_logged"] += 1
            if not dry_run:
                record_unparsed(
                    conn, mid, label_name, subject, received_at,
                    reason=reason, from_addr=from_addr,
                )

        if progress_every and i % progress_every == 0:
            print(f"  [{i}/{total}] upserted={stats['upserted']} "
                  f"unparsed={stats['unparsed_logged']} skipped={stats['skipped_known']}")

    return stats


def match_invoices(consumos_conn, invoices_conn, *, dry_run: bool = False) -> dict:
    from cashflow.invoice_repository import find_invoices_near

    unmatched = find_unmatched(consumos_conn)
    stats = {"attempted": len(unmatched), "matched": 0, "no_match": 0}

    for row in unmatched:
        purchased = datetime.fromisoformat(row["purchased_at"]).date()
        candidates = find_invoices_near(
            invoices_conn, purchased, row["amount"],
            tol_days=2, tol_amount=0.01,
        )
        if candidates:
            best = candidates[0]
            if not dry_run:
                set_invoice_match(consumos_conn, row["id"], best["invoice_number"])
            stats["matched"] += 1
        else:
            stats["no_match"] += 1

    return stats


def _compute_after(conn, user_after: Optional[str], since_last: bool) -> str:
    if since_last:
        last = get_latest_purchased_at(conn)
        if last:
            back = last - timedelta(days=7)
            return back.isoformat()
        return "2025-01-01"
    return user_after or "2025-01-01"


def _print_unparsed(conn, reason_filter: Optional[str]) -> None:
    rows = list_unparsed(conn, reason=reason_filter)
    if not rows:
        print("No unresolved unparsed emails.")
        return
    print(f"Unresolved unparsed consumo emails: {len(rows)}\n")
    for r in rows:
        subj = (r["subject"] or "")[:70]
        frm = (r["from_addr"] or "").split("<")[0].strip() or (r["from_addr"] or "")
        print(f"  {r['received_at'] or '?':<19}  {r['label']:<22} {r['reason']:<14} "
              f"{frm[:30]:<30}  {subj}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ingest consumo emails from Gmail into consumos.db"
    )
    ap.add_argument("--after", help="YYYY-MM-DD (default: 2025-01-01 or --since-last)")
    ap.add_argument("--before", help="YYYY-MM-DD (Gmail 'before' is exclusive)")
    ap.add_argument("--since-last", action="store_true",
                    help="Start from latest purchased_at in DB (minus 7 days)")
    ap.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    ap.add_argument("--db", default=None, help=f"Override DB path (default: {CONSUMOS_DB_PATH})")
    ap.add_argument("--invoices-db", default=None,
                    help=f"Override invoices DB path (default: {INVOICES_DB_PATH})")
    ap.add_argument("--show-unparsed", action="store_true",
                    help="List unresolved unparsed emails and exit")
    ap.add_argument("--unparsed-reason", help="Filter --show-unparsed by reason")
    ap.add_argument("--rematch", action="store_true",
                    help="Re-attempt invoice matching for unmatched consumos only")
    ap.add_argument("--labels", nargs="*", default=None,
                    help="Limit to specific labels (default: all Consumos/*)")
    ap.add_argument("--no-match", action="store_true",
                    help="Skip invoice matching after ingest")
    args = ap.parse_args()

    db_path = args.db or CONSUMOS_DB_PATH
    invoices_db_path = args.invoices_db or INVOICES_DB_PATH
    initialize_consumos_database(db_path)
    conn = create_consumo_connection(db_path)

    try:
        if args.show_unparsed:
            _print_unparsed(conn, args.unparsed_reason)
            return 0

        if args.rematch:
            from cashflow.invoice_database import create_invoice_connection
            inv_conn = create_invoice_connection(invoices_db_path)
            try:
                print("Re-matching unmatched consumos against invoices...")
                mstats = match_invoices(conn, inv_conn, dry_run=args.dry_run)
                print(f"  attempted={mstats['attempted']}  matched={mstats['matched']}  "
                      f"no_match={mstats['no_match']}"
                      + ("  [DRY RUN]" if args.dry_run else ""))
            finally:
                inv_conn.close()
            return 0

        gc = GmailClient()
        clear_warnings()

        labels_to_process = LABEL_TO_PARSER
        if args.labels:
            labels_to_process = {
                k: v for k, v in LABEL_TO_PARSER.items() if k in args.labels
            }

        after = _compute_after(conn, args.after, args.since_last)
        query = f"after:{_to_gmail_date(after)}"
        if args.before:
            query += f" before:{_to_gmail_date(args.before)}"

        print(f"Ingest — query={query}  db={db_path}"
              + ("  [DRY RUN]" if args.dry_run else ""))

        totals = {"seen": 0, "skipped_known": 0, "upserted": 0, "unparsed_logged": 0}

        for label_name, (_bank, parser_fn) in labels_to_process.items():
            try:
                label_id = gc.resolve_label_id(label_name)
            except KeyError:
                print(f"  {label_name}: label not found, skipping")
                continue

            stats = ingest_label(
                gc, label_name, label_id, parser_fn, query, conn,
                dry_run=args.dry_run,
            )
            for k in totals:
                totals[k] += stats[k]

        print(f"\n=== Ingest Summary ===")
        print(f"  seen:          {totals['seen']}")
        print(f"  skipped:       {totals['skipped_known']}")
        print(f"  upserted:      {totals['upserted']}")
        print(f"  unparsed:      {totals['unparsed_logged']}")

        if not args.no_match and not args.dry_run:
            from cashflow.invoice_database import create_invoice_connection
            inv_conn = create_invoice_connection(invoices_db_path)
            try:
                print("\nMatching against invoices.db...")
                mstats = match_invoices(conn, inv_conn)
                print(f"  attempted={mstats['attempted']}  matched={mstats['matched']}  "
                      f"no_match={mstats['no_match']}")
            finally:
                inv_conn.close()

        if totals["unparsed_logged"]:
            print("\nReview with: python3 -m gmail_sync.ingest_consumos --show-unparsed")

        warnings = get_warnings()
        if warnings:
            print(f"\n=== Format Warnings ({len(warnings)}) ===")
            by_code: dict[str, list] = {}
            for w in warnings:
                by_code.setdefault(w.code, []).append(w)
            for code, ws in by_code.items():
                print(f"\n  [{code}] — {len(ws)} email(s)")
                for w in ws[:5]:
                    subj = (w.subject or "")[:60]
                    print(f"    {w.label:<22} {subj}")
                    print(f"      → {w.detail}")
                if len(ws) > 5:
                    print(f"    ... and {len(ws) - 5} more")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
