import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db, get_current_user
from api.schemas import InvoiceOut, InvoiceLineOut, InvoiceTaxOut

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
