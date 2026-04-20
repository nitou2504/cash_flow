"""Build a CSV + PDF bundle of consumo-emails missing from the DB for review.

Usage:
    python3 -m gmail_sync.export_review --after 2026-03-01 --before 2026-04-20
    python3 -m gmail_sync.export_review --after 2026-03-01 --before 2026-04-20 --scp user@host:~/Downloads/
"""
import argparse
import csv
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .client import GmailClient
from .invoice import fetch_invoices, find_matching_invoice
from .reconcile import fetch_emails, load_db_txns, reconcile

OUT_DIR = Path(__file__).resolve().parent.parent / "extra" / "review_missing"


def format_items(lines) -> str:
    parts = []
    for ln in lines:
        qty = f"{ln.quantity:g}x " if ln.quantity and ln.quantity != 1 else ""
        parts.append(f"{qty}{ln.description} ${ln.total:.2f}")
    return " | ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", default="2026-03-01")
    ap.add_argument("--before", default="2026-04-20")
    ap.add_argument("--scp", default=None, help="Destination like user@host:~/Downloads/")
    args = ap.parse_args()

    # Clean+recreate output dir so re-runs don't accumulate stale files.
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    pdf_dir = OUT_DIR / "pdfs"
    pdf_dir.mkdir()

    gc = GmailClient()

    print(f"Fetching consumo emails {args.after} → {args.before}")
    emails = fetch_emails(gc, args.after, args.before)
    db_rows = load_db_txns(args.after, args.before)
    _matched, missing, _db_un = reconcile(emails, db_rows)

    if not missing:
        print("Nothing missing — nothing to export.")
        return

    before_dt = datetime.fromisoformat(args.before).date() + timedelta(days=2)
    q_after = args.after.replace("-", "/")
    q_before = before_dt.isoformat().replace("-", "/")

    facturas_label = gc.resolve_label_id("Facturas")
    print(f"\nFetching Facturas {q_after} → {q_before}")
    invoices = fetch_invoices(gc, facturas_label, f"after:{q_after} before:{q_before}")

    csv_path = OUT_DIR / "missing_transactions.csv"
    downloaded_pdfs: set[str] = set()

    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "date",
            "merchant",
            "total",
            "items",
            "time",
            "account",
            "issuer",
            "invoice_matched",
            "invoice_pdf",
            "consumo_msg_id",
            "invoice_msg_id",
        ])

        for em in sorted(missing, key=lambda e: (e.purchased_at, e.account)):
            inv = find_matching_invoice(invoices, em.purchased_at.date(), em.amount)
            pdf_link = ""

            if inv and inv.pdf_filename:
                pdf_target = pdf_dir / inv.pdf_filename
                if inv.pdf_filename not in downloaded_pdfs:
                    print(f"  downloading {inv.pdf_filename} …")
                    data = gc.get_attachment(inv.msg_id, inv.pdf_attachment_id)
                    pdf_target.write_bytes(data)
                    downloaded_pdfs.add(inv.pdf_filename)
                pdf_link = f"pdfs/{inv.pdf_filename}"

            w.writerow([
                em.purchased_at.date().isoformat(),
                em.merchant,
                f"{em.amount:.2f}",
                format_items(inv.lines) if inv else "",
                em.purchased_at.strftime("%H:%M"),
                em.account,
                inv.vendor if inv else "",
                "yes" if inv else "no",
                pdf_link,
                em.msg_id,
                inv.msg_id if inv else "",
            ])

    print(f"\nWrote {csv_path} ({len(missing)} rows)")
    print(f"Downloaded {len(downloaded_pdfs)} PDFs to {pdf_dir}")

    if args.scp:
        dest = args.scp.rstrip("/") + "/"
        print(f"\nscp -r {OUT_DIR} {dest}")
        subprocess.run(["scp", "-r", str(OUT_DIR), dest], check=True)
        print("scp done.")


if __name__ == "__main__":
    main()
