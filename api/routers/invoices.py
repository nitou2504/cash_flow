import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db, get_current_user
from api.schemas import InvoiceOut, InvoiceLineOut, InvoiceTaxOut, ConsumoOut, InvoiceLinkIn
from cashflow import consumo_repository

router = APIRouter(prefix="/api/invoices", tags=["invoices"], dependencies=[Depends(get_current_user)])


def _build_invoice(inv: dict, cursor: sqlite3.Cursor) -> InvoiceOut:
    cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number", (inv["id"],))
    lines = [InvoiceLineOut(**dict(r)) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM invoice_taxes WHERE invoice_id = ?", (inv["id"],))
    taxes = [InvoiceTaxOut(**dict(r)) for r in cursor.fetchall()]

    return InvoiceOut(
        id=inv["id"], invoice_number=inv["invoice_number"], doc_type=inv["doc_type"],
        ruc=inv["ruc"], vendor=inv["vendor"], vendor_trade_name=inv.get("vendor_trade_name"),
        issue_date=str(inv["issue_date"]),
        subtotal_sin_impuesto=inv["subtotal_sin_impuesto"],
        total_descuento=inv.get("total_descuento", 0), propina=inv.get("propina", 0),
        total=inv["total"], currency=inv.get("currency", "USD"),
        forma_pago=inv.get("forma_pago"), merchant_name=inv.get("merchant_name"),
        store_address=inv.get("store_address"),
        lines=lines, taxes=taxes,
    )


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    vendor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    conditions = []
    params: list = []

    if from_date:
        conditions.append("i.issue_date >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("i.issue_date <= ?")
        params.append(to_date)
    if vendor:
        conditions.append("(i.vendor LIKE ? OR i.vendor_trade_name LIKE ?)")
        params.extend([f"%{vendor}%", f"%{vendor}%"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT i.*, c.registered_txn_id
        FROM invoices i
        LEFT JOIN consumos c ON c.matched_invoice_number = i.invoice_number
        {where}
        ORDER BY i.issue_date DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        inv = dict(row)
        results.append(_build_invoice(inv, cursor))
    return results


@router.get("/by-transaction/{txn_id}", response_model=InvoiceOut)
def get_invoice_by_transaction(txn_id: int, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.* FROM invoices i
        JOIN consumos c ON c.matched_invoice_number = i.invoice_number
        WHERE c.registered_txn_id = ?
        LIMIT 1
    """, (txn_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No invoice linked to this transaction")
    return _build_invoice(dict(row), cursor)


CARD_FORMA_PAGO = (16, 17, 18, 19, 20)


@router.get("/unmatched", response_model=list[InvoiceOut])
def list_unmatched_invoices(
    from_date: Optional[str] = None,
    card_only: bool = False,
    limit: int = Query(100, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Invoices with no consumo linked to them."""
    cursor = conn.cursor()
    conditions = ["c.id IS NULL", "i.doc_type = 'factura'"]
    params: list = []
    if from_date:
        conditions.append("i.issue_date >= ?")
        params.append(from_date)
    if card_only:
        conditions.append(f"i.forma_pago IN ({','.join('?' * len(CARD_FORMA_PAGO))})")
        params.extend(CARD_FORMA_PAGO)
    query = f"""
        SELECT i.*
        FROM invoices i
        LEFT JOIN consumos c ON c.matched_invoice_number = i.invoice_number
        WHERE {' AND '.join(conditions)}
        ORDER BY i.issue_date DESC
        LIMIT ?
    """
    params.append(limit)
    cursor.execute(query, params)
    return [_build_invoice(dict(row), cursor) for row in cursor.fetchall()]


@router.get("/{invoice_id}/candidates", response_model=list[ConsumoOut])
def invoice_link_candidates(
    invoice_id: int,
    window_days: int = Query(7, ge=1, le=60),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Unmatched consumos near the invoice issue date, closest amount first."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    inv = cursor.fetchone()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv = dict(inv)
    cursor.execute("""
        SELECT * FROM consumos
        WHERE matched_invoice_number IS NULL
          AND date(purchased_at) BETWEEN date(?, ?) AND date(?, ?)
        ORDER BY ABS(amount - ?) ASC, ABS(julianday(purchased_at) - julianday(?)) ASC
        LIMIT 20
    """, (
        inv["issue_date"], f"-{window_days} day",
        inv["issue_date"], f"+{window_days} day",
        inv["total"], inv["issue_date"],
    ))
    return [ConsumoOut(
        id=c["id"], msg_id=c["msg_id"], bank=c["bank"], account=c["account"],
        purchased_at=c["purchased_at"], amount=c["amount"], merchant=c["merchant"],
        card_last=c.get("card_last"), matched_invoice_number=c.get("matched_invoice_number"),
        registered_txn_id=c.get("registered_txn_id"),
    ) for c in (dict(r) for r in cursor.fetchall())]


@router.post("/{invoice_id}/link")
def link_invoice_to_consumo(
    invoice_id: int,
    body: InvoiceLinkIn,
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_number FROM invoices WHERE id = ?", (invoice_id,))
    inv = cursor.fetchone()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    cursor.execute("SELECT matched_invoice_number FROM consumos WHERE id = ?", (body.consumo_id,))
    consumo = cursor.fetchone()
    if not consumo:
        raise HTTPException(status_code=404, detail="Consumo not found")
    if consumo["matched_invoice_number"]:
        raise HTTPException(status_code=409, detail="Consumo already matched to an invoice")
    consumo_repository.set_invoice_match(conn, body.consumo_id, inv["invoice_number"])
    return {"ok": True}


@router.post("/{invoice_id}/unlink")
def unlink_invoice(invoice_id: int, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_number FROM invoices WHERE id = ?", (invoice_id,))
    inv = cursor.fetchone()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    cursor.execute(
        "UPDATE consumos SET matched_invoice_number = NULL, matched_at = NULL WHERE matched_invoice_number = ?",
        (inv["invoice_number"],),
    )
    conn.commit()
    return {"ok": True, "unlinked": cursor.rowcount}


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _build_invoice(dict(row), cursor)


@router.get("/by-number/{invoice_number}", response_model=InvoiceOut)
def get_invoice_by_number(invoice_number: str, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM invoices WHERE invoice_number = ?", (invoice_number,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return get_invoice(row["id"], conn)
