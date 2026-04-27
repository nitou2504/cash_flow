"""Invoice repository: CRUD helpers for the separate invoices.db store.

Idempotent upsert keyed on `invoice_number` (SRI estab-ptoEmi-secuencial is
unique system-wide). Re-ingesting the same XML replaces its lines + taxes.
"""
from datetime import date, datetime, timezone
from sqlite3 import Connection
from typing import Any, Dict, List, Optional

from gmail_sync.invoice import Invoice


def upsert_invoice(
    conn: Connection,
    invoice: Invoice,
    *,
    xml_path: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> int:
    """Insert or replace an invoice (and its lines + taxes) keyed on
    invoice_number. Returns the row id of the invoices row."""
    if not invoice.invoice_number:
        raise ValueError("Invoice.invoice_number is required for upsert")

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM invoices WHERE invoice_number = ?", (invoice.invoice_number,))
    existing = cursor.fetchone()

    if existing:
        invoice_id = existing["id"]
        cursor.execute("""
            UPDATE invoices SET
                msg_id = ?, doc_type = ?, clave_acceso = ?, ruc = ?,
                vendor = ?, vendor_trade_name = ?, issue_date = ?,
                subtotal_sin_impuesto = ?, total_descuento = ?, propina = ?,
                total = ?, currency = ?,
                refund_of_invoice_number = ?, refund_of_issue_date = ?,
                motivo = ?, motivo_category = ?,
                merchant_name = ?, establishment_code = ?, store_address = ?,
                forma_pago = ?, deducible_alimentacion = ?,
                email_subject = COALESCE(?, email_subject),
                email_from = COALESCE(?, email_from),
                xml_path = COALESCE(?, xml_path),
                pdf_path = COALESCE(?, pdf_path)
            WHERE id = ?
        """, (
            invoice.msg_id or None,
            invoice.doc_type, invoice.clave_acceso or None, invoice.ruc,
            invoice.vendor, invoice.vendor_trade_name or None, invoice.issue_date,
            invoice.subtotal_sin_impuesto, invoice.total_descuento, invoice.propina,
            invoice.total, invoice.currency,
            invoice.refund_of or None, invoice.refund_of_issue_date,
            invoice.motivo or None, invoice.motivo_category or None,
            invoice.merchant_name or None, invoice.establishment_code or None,
            invoice.store_address or None,
            invoice.forma_pago or None, invoice.deducible_alimentacion or None,
            invoice.email_subject or None, invoice.email_from or None,
            xml_path, pdf_path,
            invoice_id,
        ))
        cursor.execute("DELETE FROM invoice_lines WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("DELETE FROM invoice_taxes WHERE invoice_id = ?", (invoice_id,))
    else:
        cursor.execute("""
            INSERT INTO invoices (
                msg_id, doc_type, invoice_number, clave_acceso, ruc,
                vendor, vendor_trade_name, issue_date,
                subtotal_sin_impuesto, total_descuento, propina, total, currency,
                refund_of_invoice_number, refund_of_issue_date,
                motivo, motivo_category,
                merchant_name, establishment_code, store_address,
                forma_pago, deducible_alimentacion,
                email_subject, email_from,
                xml_path, pdf_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice.msg_id or None,
            invoice.doc_type, invoice.invoice_number,
            invoice.clave_acceso or None, invoice.ruc,
            invoice.vendor, invoice.vendor_trade_name or None, invoice.issue_date,
            invoice.subtotal_sin_impuesto, invoice.total_descuento, invoice.propina,
            invoice.total, invoice.currency,
            invoice.refund_of or None, invoice.refund_of_issue_date,
            invoice.motivo or None, invoice.motivo_category or None,
            invoice.merchant_name or None, invoice.establishment_code or None,
            invoice.store_address or None,
            invoice.forma_pago or None, invoice.deducible_alimentacion or None,
            invoice.email_subject or None, invoice.email_from or None,
            xml_path, pdf_path,
        ))
        invoice_id = cursor.lastrowid

    for i, ln in enumerate(invoice.lines, start=1):
        cursor.execute("""
            INSERT INTO invoice_lines (
                invoice_id, line_number, sku, sku_aux, description,
                quantity, unit_price, discount, line_subtotal, line_tax, line_total, tax_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_id, i, ln.sku or None, ln.sku_aux or None, ln.description,
            ln.quantity, ln.unit_price, ln.discount, ln.total,
            ln.line_tax, ln.total + ln.line_tax, ln.tax_rate,
        ))

    for tax in invoice.taxes:
        cursor.execute("""
            INSERT INTO invoice_taxes (
                invoice_id, tax_code, rate_code, rate_pct, base_imponible, tax_value
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            invoice_id, tax.tax_code, tax.rate_code, tax.rate_pct,
            tax.base_imponible, tax.tax_value,
        ))

    # If this msg_id was previously flagged as unparsed, clear it.
    if invoice.msg_id:
        cursor.execute(
            "UPDATE unparsed_facturas SET resolved = 1, resolved_at = ? WHERE msg_id = ?",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), invoice.msg_id),
        )

    conn.commit()
    return invoice_id


def get_invoice_by_id(conn: Connection, invoice_id: int) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_invoice_by_number(conn: Connection, invoice_number: str) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_lines(conn: Connection, invoice_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number",
        (invoice_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


def get_taxes(conn: Connection, invoice_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM invoice_taxes WHERE invoice_id = ? ORDER BY rate_pct",
        (invoice_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


def find_invoices_near(
    conn: Connection,
    issue_date: date,
    amount: float,
    tol_days: int = 2,
    tol_amount: float = 0.01,
) -> List[Dict[str, Any]]:
    """Find invoices matching `amount` within ±`tol_days` of `issue_date`.

    Mirrors the semantics of gmail_sync.invoice.find_matching_invoice but
    runs on the persisted store.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM invoices
        WHERE ABS(total - ?) <= ?
          AND ABS(JULIANDAY(issue_date) - JULIANDAY(?)) <= ?
        ORDER BY ABS(JULIANDAY(issue_date) - JULIANDAY(?)) ASC,
                 ABS(total - ?) ASC
    """, (amount, tol_amount, issue_date, tol_days, issue_date, amount))
    return [dict(r) for r in cursor.fetchall()]


def list_invoices(
    conn: Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    vendor: Optional[str] = None,
    after: Optional[date] = None,
    before: Optional[date] = None,
    doc_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where = []
    args: list = []
    if vendor:
        where.append("vendor LIKE ?")
        args.append(f"%{vendor}%")
    if after:
        where.append("issue_date >= ?")
        args.append(after)
    if before:
        where.append("issue_date <= ?")
        args.append(before)
    if doc_type:
        where.append("doc_type = ?")
        args.append(doc_type)
    sql = "SELECT * FROM invoices"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY issue_date DESC, id DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    cursor = conn.cursor()
    cursor.execute(sql, tuple(args))
    return [dict(r) for r in cursor.fetchall()]


# --- Unparsed Facturas tracking -------------------------------------------

UNPARSED_REASONS = (
    "no_attachment",     # Email has no attachments at all (HTML-body factura)
    "no_xml",            # Has PDF but no XML (e.g. Payphone, old manual uploads)
    "zip_no_xml",        # Has ZIP but no XML inside
    "parse_failed",      # Had XML but parse_sri_factura returned None
    "other",
)


def record_unparsed(
    conn: Connection,
    msg_id: str,
    subject: str,
    from_addr: str,
    received_at: Optional[str],
    reason: str,
    *,
    notes: Optional[str] = None,
    has_pdf: bool = False,
) -> None:
    """Flag an email as unparsed. Idempotent by msg_id (updates existing row)."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO unparsed_facturas (msg_id, subject, from_addr, received_at, reason, notes, has_pdf)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(msg_id) DO UPDATE SET
            subject = excluded.subject,
            from_addr = excluded.from_addr,
            received_at = excluded.received_at,
            reason = excluded.reason,
            notes = excluded.notes,
            has_pdf = excluded.has_pdf
    """, (msg_id, subject, from_addr, received_at, reason, notes, 1 if has_pdf else 0))
    conn.commit()


def list_unparsed(
    conn: Connection,
    *,
    only_unresolved: bool = True,
    reason: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM unparsed_facturas"
    where: list[str] = []
    args: list = []
    if only_unresolved:
        where.append("resolved = 0")
    if reason:
        where.append("reason = ?")
        args.append(reason)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY received_at DESC, msg_id DESC LIMIT ?"
    args.append(limit)
    cursor = conn.cursor()
    cursor.execute(sql, tuple(args))
    return [dict(r) for r in cursor.fetchall()]


def mark_unparsed_resolved(conn: Connection, msg_id: str, notes: Optional[str] = None) -> bool:
    """Manually mark an unparsed email as handled. Returns True if a row was updated."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE unparsed_facturas
        SET resolved = 1,
            resolved_at = ?,
            notes = COALESCE(?, notes)
        WHERE msg_id = ?
    """, (datetime.now(timezone.utc).isoformat(timespec="seconds"), notes, msg_id))
    conn.commit()
    return cursor.rowcount > 0


def get_ingested_msg_ids(conn: Connection) -> set[str]:
    """Return msg_ids already represented in invoices OR unparsed_facturas.
    Used to skip known emails in incremental runs."""
    cursor = conn.cursor()
    cursor.execute("SELECT msg_id FROM invoices WHERE msg_id IS NOT NULL")
    seen = {r["msg_id"] for r in cursor.fetchall() if r["msg_id"]}
    cursor.execute("SELECT msg_id FROM unparsed_facturas")
    seen.update(r["msg_id"] for r in cursor.fetchall())
    return seen


def get_latest_issue_date(conn: Connection) -> Optional[date]:
    """Most recent issue_date in invoices (for --since-last mode)."""
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(issue_date) AS d FROM invoices")
    row = cursor.fetchone()
    if not row or row["d"] is None:
        return None
    v = row["d"]
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def get_invoice_by_msg_id(conn: Connection, msg_id: str) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE msg_id = ?", (msg_id,))
    row = cursor.fetchone()
    return dict(row) if row else None
