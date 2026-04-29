import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db, get_current_user
from api.schemas import InvoiceOut, InvoiceLineOut, InvoiceTaxOut

router = APIRouter(prefix="/api/invoices", tags=["invoices"], dependencies=[Depends(get_current_user)])


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv = dict(row)

    cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number", (invoice_id,))
    lines = [InvoiceLineOut(**dict(r)) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM invoice_taxes WHERE invoice_id = ?", (invoice_id,))
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


@router.get("/by-number/{invoice_number}", response_model=InvoiceOut)
def get_invoice_by_number(invoice_number: str, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM invoices WHERE invoice_number = ?", (invoice_number,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return get_invoice(row["id"], conn)
