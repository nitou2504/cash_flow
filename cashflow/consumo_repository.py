"""Consumo repository: CRUD helpers for consumos.db.

Idempotent upsert keyed on msg_id (one Gmail message = one consumo).
"""
from datetime import date, datetime, timezone
from sqlite3 import Connection
from typing import Optional

from gmail_sync.parsers import EmailTxn


def upsert_consumo(conn: Connection, txn: EmailTxn, label: str) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO consumos (
            msg_id, bank, account, purchased_at, amount, merchant,
            card_last, subject, label,
            beneficiary, destination_account, concepto
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(msg_id) DO UPDATE SET
            bank = excluded.bank,
            account = excluded.account,
            purchased_at = excluded.purchased_at,
            amount = excluded.amount,
            merchant = excluded.merchant,
            card_last = excluded.card_last,
            subject = excluded.subject,
            label = excluded.label,
            beneficiary = excluded.beneficiary,
            destination_account = excluded.destination_account,
            concepto = excluded.concepto
    """, (
        txn.msg_id, txn.bank, txn.account,
        txn.purchased_at.isoformat(timespec="seconds"),
        txn.amount, txn.merchant,
        txn.card_last, txn.subject, label,
        txn.beneficiary, txn.destination_account, txn.concepto,
    ))
    conn.commit()
    return cursor.lastrowid


def get_ingested_msg_ids(conn: Connection) -> set[str]:
    rows = conn.execute("SELECT msg_id FROM consumos").fetchall()
    ids = {r["msg_id"] for r in rows}
    rows = conn.execute(
        "SELECT msg_id FROM unparsed_consumos WHERE resolved = 0"
    ).fetchall()
    ids |= {r["msg_id"] for r in rows}
    return ids


def get_latest_purchased_at(conn: Connection) -> Optional[date]:
    row = conn.execute(
        "SELECT MAX(purchased_at) as latest FROM consumos"
    ).fetchone()
    if not row or not row["latest"]:
        return None
    return datetime.fromisoformat(row["latest"]).date()


def find_unmatched(conn: Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM consumos
        WHERE matched_invoice_number IS NULL
        ORDER BY purchased_at
    """).fetchall()
    return [dict(r) for r in rows]


def set_invoice_match(
    conn: Connection, consumo_id: int, invoice_number: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "UPDATE consumos SET matched_invoice_number = ?, matched_at = ? WHERE id = ?",
        (invoice_number, now, consumo_id),
    )
    conn.commit()


def record_unparsed(
    conn: Connection,
    msg_id: str,
    label: str,
    subject: str,
    received_at: Optional[str],
    reason: str,
    *,
    from_addr: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    conn.execute("""
        INSERT OR IGNORE INTO unparsed_consumos
            (msg_id, label, subject, from_addr, received_at, reason, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (msg_id, label, subject, from_addr, received_at, reason, notes))
    conn.commit()


def list_unparsed(
    conn: Connection, *, reason: Optional[str] = None,
) -> list[dict]:
    if reason:
        rows = conn.execute(
            "SELECT * FROM unparsed_consumos WHERE resolved = 0 AND reason = ? "
            "ORDER BY received_at", (reason,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM unparsed_consumos WHERE resolved = 0 ORDER BY received_at"
        ).fetchall()
    return [dict(r) for r in rows]


def find_unregistered(conn: Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM consumos
        WHERE registered_txn_id IS NULL
        ORDER BY purchased_at
    """).fetchall()
    return [dict(r) for r in rows]


def mark_registered(
    conn: Connection, consumo_id: int, transaction_id: int,
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "UPDATE consumos SET registered_txn_id = ?, registered_at = ? WHERE id = ?",
        (transaction_id, now, consumo_id),
    )
    conn.commit()
