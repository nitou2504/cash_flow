"""Compare CC consumo emails against transactions in cash_flow.db.

Usage:
    python3 -m gmail_sync.reconcile --after 2026-03-01 --before 2026-04-20
"""
import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .client import GmailClient, extract_text, header
from .parsers import BANK_PARSERS, EmailTxn

DB_PATH = Path(__file__).resolve().parent.parent / "cash_flow.db"

LABEL_TO_BANK = {
    "Consumos/Pichincha": "Pichincha",
    "Consumos/Diners": "Diners",
    "Consumos/Produbanco": "Produbanco",
}

AMOUNT_TOLERANCE = 0.005   # cents
DATE_WINDOW_DAYS = 65      # CC billing-period slack (purchase → posted date)


def fetch_emails(gc: GmailClient, after: str, before: str) -> list[EmailTxn]:
    query = f"after:{after.replace('-', '/')} before:{before.replace('-', '/')}"
    txns: list[EmailTxn] = []
    for label_name, bank in LABEL_TO_BANK.items():
        label_id = gc.resolve_label_id(label_name)
        ids = list(gc.iter_message_ids(label_ids=[label_id], query=query))
        print(f"  {label_name}: {len(ids)} messages")
        parser = BANK_PARSERS[bank]
        for mid in ids:
            msg = gc.get_message(mid)
            subject = header(msg, "Subject") or ""
            body = extract_text(msg)
            parsed = parser(mid, subject, body)
            if parsed:
                txns.append(parsed)
            else:
                print(f"    ! parse failed: {mid} subject={subject!r}")
    return txns


def load_db_txns(after: str, before: str) -> list[dict]:
    # Purchases in the email range always post to a FUTURE billing-period date,
    # so only widen forward. Small backward slack for edge cases.
    after_dt = datetime.fromisoformat(after).date() - timedelta(days=5)
    before_dt = datetime.fromisoformat(before).date() + timedelta(days=DATE_WINDOW_DAYS)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, date_payed, account, amount, description, category, status, source
        FROM transactions
        WHERE account IN ('Visa Pichincha', 'Diners', 'Visa Produbanco')
          AND date_payed BETWEEN ? AND ?
        ORDER BY date_payed
        """,
        (after_dt.isoformat(), before_dt.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reconcile(emails: list[EmailTxn], db_rows: list[dict]) -> tuple[list, list, list]:
    """Greedy 1:1 match on (account, abs(amount), date within DATE_WINDOW_DAYS).

    Returns (matched_pairs, emails_unmatched, db_unmatched).
    """
    remaining = list(db_rows)
    matched: list[tuple[EmailTxn, dict]] = []
    email_unmatched: list[EmailTxn] = []

    for em in sorted(emails, key=lambda e: e.purchased_at):
        best_idx = None
        best_diff = None
        for i, row in enumerate(remaining):
            if row["account"] != em.account:
                continue
            if abs(abs(row["amount"]) - em.amount) > AMOUNT_TOLERANCE:
                continue
            row_dt = datetime.fromisoformat(row["date_payed"])
            diff_days = abs((row_dt.date() - em.purchased_at.date()).days)
            if diff_days > DATE_WINDOW_DAYS:
                continue
            if best_diff is None or diff_days < best_diff:
                best_idx, best_diff = i, diff_days
        if best_idx is not None:
            matched.append((em, remaining.pop(best_idx)))
        else:
            email_unmatched.append(em)

    return matched, email_unmatched, remaining


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", default="2026-03-01")
    ap.add_argument("--before", default="2026-04-20")
    ap.add_argument("--show-matched", action="store_true")
    args = ap.parse_args()

    print(f"Fetching emails {args.after} → {args.before}")
    gc = GmailClient()
    emails = fetch_emails(gc, args.after, args.before)
    print(f"  → {len(emails)} parsed email transactions.\n")

    print(f"Loading DB CC transactions ±{DATE_WINDOW_DAYS}d around window")
    db_rows = load_db_txns(args.after, args.before)
    print(f"  → {len(db_rows)} DB rows.\n")

    matched, email_unmatched, db_unmatched = reconcile(emails, db_rows)

    print(f"=== Matched: {len(matched)} ===")
    if args.show_matched:
        for em, row in matched:
            print(
                f"  {em.account:16} {em.purchased_at.date()} ${em.amount:>7.2f}  "
                f"{em.merchant[:30]:30}  ↔  DB#{row['id']} {row['date_payed']} {row['description'][:40]}"
            )

    print(f"\n=== MISSING from DB (email has no match): {len(email_unmatched)} ===")
    for em in sorted(email_unmatched, key=lambda e: (e.account, e.purchased_at)):
        print(
            f"  {em.account:16} {em.purchased_at.date()} {em.purchased_at.time().strftime('%H:%M')} "
            f"${em.amount:>7.2f}  {em.merchant}  (card …{em.card_last}, msg {em.msg_id})"
        )

    print(f"\n=== In DB but no email (possibly manual / wrong / refund): {len(db_unmatched)} ===")
    for row in db_unmatched:
        print(
            f"  DB#{row['id']:>4}  {row['account']:16} {row['date_payed']} "
            f"${abs(row['amount']):>7.2f}  {row['description']}"
        )


if __name__ == "__main__":
    main()
