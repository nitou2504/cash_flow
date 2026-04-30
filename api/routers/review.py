import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db, get_current_user
from api.schemas import TransactionOut, ReviewItemOut, ConsumoOut, InvoiceOut
from api.routers.transactions import _txn_to_out
from api.routers.invoices import _build_invoice
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
                invoice = _build_invoice(dict(inv_row), cursor)
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


@router.post("/{transaction_id}/approve")
def approve_review(transaction_id: int, conn: sqlite3.Connection = Depends(get_db)):
    t = repository.get_transaction_by_id(conn, transaction_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    repository.mark_reviewed(conn, transaction_id)
    return {"ok": True}


class BatchApproveBody(BaseModel):
    ids: List[int]


@router.post("/approve-batch")
def approve_review_batch(body: BatchApproveBody, conn: sqlite3.Connection = Depends(get_db)):
    approved = 0
    for tid in body.ids:
        t = repository.get_transaction_by_id(conn, tid)
        if t and dict(t).get("needs_review"):
            repository.mark_reviewed(conn, tid)
            approved += 1
    return {"approved": approved}
