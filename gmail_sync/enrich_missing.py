"""Enrich the list of missing consumo-email transactions with invoice line items.

Usage:
    python3 -m gmail_sync.enrich_missing --after 2026-03-01 --before 2026-04-20
"""
import argparse

from .client import GmailClient
from .invoice import fetch_invoices, find_matching_invoice
from .parsers import EmailTxn
from .reconcile import fetch_emails, load_db_txns, reconcile


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", default="2026-03-01")
    ap.add_argument("--before", default="2026-04-20")
    args = ap.parse_args()

    gc = GmailClient()

    print(f"Fetching consumo emails {args.after} → {args.before}")
    emails = fetch_emails(gc, args.after, args.before)
    db_rows = load_db_txns(args.after, args.before)
    _matched, missing, _db_un = reconcile(emails, db_rows)

    if not missing:
        print("No missing transactions — nothing to enrich.")
        return

    # Widen factura window by a day on each side — invoice can be emitted a day late.
    q_after = args.after.replace("-", "/")
    # Gmail before: is exclusive on that date; add 2 days to be safe.
    from datetime import datetime, timedelta
    before_dt = datetime.fromisoformat(args.before).date() + timedelta(days=2)
    q_before = before_dt.isoformat().replace("-", "/")

    print(f"\nFetching Facturas {q_after} → {q_before} (this may be slow first run)")
    facturas_label = gc.resolve_label_id("Facturas")
    invoices = fetch_invoices(gc, facturas_label, f"after:{q_after} before:{q_before}")
    print(f"  → {len(invoices)} invoices parsed/cached.\n")

    print(f"=== {len(missing)} missing consumos, enriched with invoice detail where available ===\n")

    matched_invoices = 0
    for em in sorted(missing, key=lambda e: (e.account, e.purchased_at)):
        inv = find_matching_invoice(invoices, em.purchased_at.date(), em.amount)
        header_line = (
            f"{em.account:16} {em.purchased_at.date()} {em.purchased_at.time().strftime('%H:%M')} "
            f"${em.amount:>7.2f}  {em.merchant}"
        )
        if inv and inv.lines:
            matched_invoices += 1
            print(header_line + f"   [invoice: {inv.vendor}]")
            for ln in inv.lines:
                qty = f"{ln.quantity:g}×" if ln.quantity and ln.quantity != 1 else ""
                print(f"    - {qty}{ln.description}  ${ln.total:.2f}")
        elif inv:
            matched_invoices += 1
            print(header_line + f"   [factura found but no line items: {inv.vendor}]")
        else:
            print(header_line + "   [no invoice]")
        print()

    print(f"Enriched {matched_invoices}/{len(missing)} with invoice data.")


if __name__ == "__main__":
    main()
