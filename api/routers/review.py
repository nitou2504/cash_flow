import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db, get_current_user
from api.schemas import TransactionOut, ReviewItemOut, ConsumoOut, InvoiceOut
from api.routers.transactions import _txn_to_out
from cashflow import repository

router = APIRouter(prefix="/api/review", tags=["review"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TransactionOut])
def list_review(source: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    txns = repository.get_transactions_needing_review(conn, source=source)
    return [_txn_to_out(t) for t in txns]


@router.get("/{transaction_id}/context", response_model=ReviewItemOut)
def review_context(transaction_id: int, conn: sqlite3.Connection = Depends(get_db)):
    t = repository.get_transaction_by_id(conn, transaction_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    t = dict(t)
    txn_out = _txn_to_out(t)

    consumo = None
    invoice = None
    llm_decision = None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM consumos WHERE registered_txn_id = ? LIMIT 1",
        (transaction_id,),
    )
    row = cursor.fetchone()
    if row:
        c = dict(row)
        consumo = ConsumoOut(
            id=c["id"], msg_id=c["msg_id"], bank=c["bank"], account=c["account"],
            purchased_at=c["purchased_at"], amount=c["amount"], merchant=c["merchant"],
            card_last=c.get("card_last"), matched_invoice_number=c.get("matched_invoice_number"),
            registered_txn_id=c.get("registered_txn_id"),
        )
        if c.get("matched_invoice_number"):
            cursor.execute(
                "SELECT * FROM invoices WHERE invoice_number = ? LIMIT 1",
                (c["matched_invoice_number"],),
            )
            inv_row = cursor.fetchone()
            if inv_row:
                inv = dict(inv_row)
                invoice = InvoiceOut(
                    id=inv["id"], invoice_number=inv["invoice_number"],
                    doc_type=inv["doc_type"], ruc=inv["ruc"], vendor=inv["vendor"],
                    vendor_trade_name=inv.get("vendor_trade_name"),
                    issue_date=str(inv["issue_date"]),
                    subtotal_sin_impuesto=inv["subtotal_sin_impuesto"],
                    total_descuento=inv.get("total_descuento", 0),
                    propina=inv.get("propina", 0), total=inv["total"],
                    forma_pago=inv.get("forma_pago"),
                    merchant_name=inv.get("merchant_name"),
                    store_address=inv.get("store_address"),
                )
        cursor.execute(
            "SELECT * FROM llm_decisions WHERE consumo_id = ? ORDER BY id DESC LIMIT 1",
            (c["id"],),
        )
        llm_row = cursor.fetchone()
        if llm_row:
            llm_decision = dict(llm_row)

    return ReviewItemOut(
        transaction=txn_out, consumo=consumo, invoice=invoice, llm_decision=llm_decision,
    )
