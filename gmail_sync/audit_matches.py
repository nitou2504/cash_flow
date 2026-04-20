"""Audit the matched email↔DB pairs for ambiguity (multiple same-amount DB rows).

Usage:
    python3 -m gmail_sync.audit_matches --after 2026-03-01 --before 2026-04-20
"""
import argparse
from collections import Counter
from datetime import datetime

from .client import GmailClient
from .reconcile import fetch_emails, load_db_txns, reconcile


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", default="2026-03-01")
    ap.add_argument("--before", default="2026-04-20")
    args = ap.parse_args()

    gc = GmailClient()
    emails = fetch_emails(gc, args.after, args.before)
    db_rows = load_db_txns(args.after, args.before)
    matched, _missing, _db_un = reconcile(emails, db_rows)

    # Count how many DB rows share (account, round(amount,2)) in the loaded set.
    bucket: Counter = Counter()
    for row in db_rows:
        bucket[(row["account"], round(abs(row["amount"]), 2))] += 1

    print(f"\n=== Suspicious matches (source='mom' OR amount collision OR far date) ===\n")
    suspicious = 0
    for em, row in sorted(matched, key=lambda p: p[0].purchased_at):
        key = (em.account, round(em.amount, 2))
        n = bucket[key]
        row_dt = datetime.fromisoformat(row["date_payed"]).date()
        day_diff = abs((row_dt - em.purchased_at.date()).days)
        flags = []
        if row.get("source") == "mom":
            flags.append("source=mom (shared-finance entry, verify merchant)")
        if n > 1:
            flags.append(f"{n} DB rows with same ({em.account}, ${em.amount:.2f})")
        if day_diff > 45:
            flags.append(f"date_diff={day_diff}d")
        if not flags:
            continue
        suspicious += 1
        print(
            f"{em.purchased_at.date()} {em.account:16} ${em.amount:>7.2f} "
            f"{em.merchant[:28]:28} ↔ DB#{row['id']} {row['date_payed']} "
            f"{(row['description'] or '')[:42]}"
        )
        for f in flags:
            print(f"    ⚠ {f}")

    print(f"\n{suspicious}/{len(matched)} matches flagged for review.")


if __name__ == "__main__":
    main()
