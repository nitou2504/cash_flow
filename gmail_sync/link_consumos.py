"""Retroactively link existing transactions to consumos entries.

Usage:
    python3 -m gmail_sync.link_consumos --dry-run     # preview matches
    python3 -m gmail_sync.link_consumos               # execute linking
    python3 -m gmail_sync.link_consumos --stats        # show link coverage
"""
import argparse
import sys
from datetime import datetime

from cashflow.consumo_repository import mark_registered
from cashflow.database import create_connection
from cashflow.repository import get_unlinked_transactions, link_transaction


CC_ACCOUNTS = ["Visa Pichincha", "Diners", "Visa Produbanco"]
ALL_ACCOUNTS = CC_ACCOUNTS + ["Cash"]
DATE_TOLERANCE_DAYS = 3
AMOUNT_TOLERANCE = 0.01


def _find_consumo_match(conn, account: str, amount: float, date_created: str):
    rows = conn.execute("""
        SELECT id, msg_id, merchant, purchased_at, matched_invoice_number
        FROM consumos
        WHERE account = ? AND ABS(amount - ?) < ?
          AND ABS(JULIANDAY(purchased_at) - JULIANDAY(?)) < ?
        ORDER BY ABS(JULIANDAY(purchased_at) - JULIANDAY(?))
        LIMIT 1
    """, (account, amount, AMOUNT_TOLERANCE, date_created,
          DATE_TOLERANCE_DAYS, date_created)).fetchone()
    return dict(rows) if rows else None


def _find_origin_link(conn, origin_id: str):
    """If a sibling transaction (same origin_id) is already linked, return its consumo info."""
    if not origin_id:
        return None
    row = conn.execute("""
        SELECT c.msg_id as consumo_msg_id, c.matched_invoice_number as invoice_number
        FROM consumos c
        JOIN transactions t ON c.registered_txn_id = t.id
        WHERE t.origin_id = ? AND c.msg_id IS NOT NULL
        LIMIT 1
    """, (origin_id,)).fetchone()
    return dict(row) if row else None


def link_all(conn, *, dry_run: bool = False) -> dict:
    stats = {"direct": 0, "origin_chain": 0, "no_match": 0, "total": 0}

    unlinked = get_unlinked_transactions(conn, accounts=ALL_ACCOUNTS)
    stats["total"] = len(unlinked)
    print(f"Unlinked transactions: {len(unlinked)}")

    already_claimed: set[str] = set()

    for txn in unlinked:
        tid = txn["id"]
        amount = abs(txn["amount"])
        account = txn["account"]
        date_created = txn["date_created"]
        if isinstance(date_created, (datetime,)):
            date_created = date_created.isoformat()
        elif hasattr(date_created, 'isoformat'):
            date_created = date_created.isoformat()

        match = _find_consumo_match(conn, account, amount, str(date_created))

        if match and match["msg_id"] not in already_claimed:
            already_claimed.add(match["msg_id"])
            inv = match.get("matched_invoice_number")
            if not dry_run:
                link_transaction(conn, tid,
                                 consumo_msg_id=match["msg_id"],
                                 invoice_number=inv,
                                 source="auto_match")
                mark_registered(conn, match["id"], tid)
            stats["direct"] += 1
            if dry_run:
                desc = (txn["description"] or "")[:40]
                merch = (match["merchant"] or "")[:25]
                print(f"  TX#{tid} {date_created} ${amount:.2f} {desc} → {merch}"
                      + (f" inv={inv}" if inv else ""))
            continue

        sibling = _find_origin_link(conn, txn.get("origin_id"))
        if sibling:
            if not dry_run:
                link_transaction(conn, tid,
                                 consumo_msg_id=sibling["consumo_msg_id"],
                                 invoice_number=sibling.get("invoice_number"),
                                 source="origin_chain")
            stats["origin_chain"] += 1
            if dry_run:
                desc = (txn["description"] or "")[:40]
                print(f"  TX#{tid} {date_created} ${amount:.2f} {desc} → chain:{sibling['consumo_msg_id'][:12]}")
            continue

        stats["no_match"] += 1

    return stats


def print_stats(conn):
    total_txns = conn.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE status = 'committed' AND amount < 0
          AND account IN ('Visa Pichincha', 'Diners', 'Visa Produbanco', 'Cash')
    """).fetchone()[0]
    linked = conn.execute(
        "SELECT COUNT(*) FROM consumos WHERE link_source IS NOT NULL"
    ).fetchone()[0]
    total_consumos = conn.execute("SELECT COUNT(*) FROM consumos").fetchone()[0]
    registered = conn.execute(
        "SELECT COUNT(*) FROM consumos WHERE registered_txn_id IS NOT NULL"
    ).fetchone()[0]

    print(f"\n=== Link Coverage ===")
    print(f"  Transactions (CC+Cash, committed): {total_txns}")
    print(f"  Linked to consumo: {linked} ({linked/total_txns*100:.1f}%)" if total_txns else "")
    print(f"  Unlinked: {total_txns - linked}")
    print(f"\n  Consumos total: {total_consumos}")
    print(f"  Registered (→ transaction): {registered} ({registered/total_consumos*100:.1f}%)" if total_consumos else "")
    print(f"  Unregistered: {total_consumos - registered}")

    by_source = conn.execute("""
        SELECT link_source, COUNT(*) FROM consumos
        WHERE link_source IS NOT NULL GROUP BY link_source
    """).fetchall()
    if by_source:
        print(f"\n  By link source:")
        for row in by_source:
            print(f"    {row[0]}: {row[1]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Link transactions to consumos retroactively")
    ap.add_argument("--dry-run", action="store_true", help="Preview matches without writing")
    ap.add_argument("--stats", action="store_true", help="Show link coverage stats and exit")
    ap.add_argument("--db", default="cash_flow.db", help="Override cash_flow.db path")
    args = ap.parse_args()

    conn = create_connection(args.db)

    try:
        if args.stats:
            print_stats(conn)
            return 0

        print(f"Linking transactions → consumos"
              + ("  [DRY RUN]" if args.dry_run else ""))
        stats = link_all(conn, dry_run=args.dry_run)

        print(f"\n=== Results ===")
        print(f"  Total unlinked: {stats['total']}")
        print(f"  Direct match:   {stats['direct']}")
        print(f"  Origin chain:   {stats['origin_chain']}")
        print(f"  No match:       {stats['no_match']}")

        if not args.dry_run:
            print_stats(conn)

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
