import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, get_current_user
from api.schemas import TransactionOut
from cashflow import repository

router = APIRouter(prefix="/api/transactions", tags=["transactions"], dependencies=[Depends(get_current_user)])


def _txn_to_out(t: dict) -> TransactionOut:
    return TransactionOut(
        id=t["id"],
        date_created=str(t["date_created"]),
        date_payed=str(t["date_payed"]),
        description=t["description"],
        account=t.get("account"),
        amount=t["amount"],
        category=t.get("category"),
        budget=t.get("budget"),
        status=t["status"],
        origin_id=t.get("origin_id"),
        source=t.get("source"),
        needs_review=t.get("needs_review", 0),
        running_balance=t.get("running_balance"),
    )


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    account: Optional[str] = None,
    category: Optional[str] = None,
    include_planning: bool = True,
    conn: sqlite3.Connection = Depends(get_db),
):
    txns = repository.get_transactions_with_running_balance(conn)
    if from_date:
        txns = [t for t in txns if str(t["date_payed"]) >= from_date]
    if to_date:
        txns = [t for t in txns if str(t["date_payed"]) <= to_date]
    if status:
        txns = [t for t in txns if t["status"] == status]
    if account:
        txns = [t for t in txns if t.get("account") == account]
    if category:
        txns = [t for t in txns if t.get("category") == category]
    if not include_planning:
        txns = [t for t in txns if t["status"] != "planning"]
    return [_txn_to_out(t) for t in txns]


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, conn: sqlite3.Connection = Depends(get_db)):
    t = repository.get_transaction_by_id(conn, transaction_id)
    if not t:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _txn_to_out(dict(t))


@router.get("/{transaction_id}/group", response_model=list[TransactionOut])
def get_transaction_group(transaction_id: int, conn: sqlite3.Connection = Depends(get_db)):
    t = repository.get_transaction_by_id(conn, transaction_id)
    if not t:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transaction not found")
    t = dict(t)
    if not t.get("origin_id"):
        return [_txn_to_out(t)]
    group = repository.get_transactions_by_origin_id(conn, t["origin_id"])
    return [_txn_to_out(dict(g)) for g in group]
