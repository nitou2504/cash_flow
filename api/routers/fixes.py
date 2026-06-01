import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db, get_current_user
from api.schemas import BalanceFixIn, StatementFixIn
from cashflow import repository, controller

router = APIRouter(prefix="/api/fixes", tags=["fixes"], dependencies=[Depends(get_current_user)])


@router.get("/balance-preview")
def balance_preview(
    account: str = "Cash",
    as_of_date: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Current calculated running balance as of a date — so the UI can show the
    delta before the user commits to an adjustment."""
    if not repository.get_account_by_name(conn, account):
        raise HTTPException(400, f"Account '{account}' not found")

    ref = date.fromisoformat(as_of_date) if as_of_date else date.today()
    txns = repository.get_transactions_with_running_balance(conn)
    calculated = 0.0
    for t in txns:
        if t["date_payed"] <= ref:
            calculated = t["running_balance"]
        else:
            break
    return {"account": account, "as_of_date": ref.isoformat(), "calculated_balance": round(calculated, 2)}


@router.post("/balance")
def fix_balance(body: BalanceFixIn, conn: sqlite3.Connection = Depends(get_db)):
    """Reconcile a calculated balance to the actual amount by inserting a
    Balance Adjustment transaction. as_of_date lets you reconcile to a point
    where some forecast bills have already paid."""
    ref = date.fromisoformat(body.as_of_date) if body.as_of_date else None
    try:
        diff = controller.process_balance_adjustment(conn, body.actual_balance, body.account, as_of=ref)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "adjustment": round(diff, 2)}


@router.post("/statement")
def fix_statement(body: StatementFixIn, conn: sqlite3.Connection = Depends(get_db)):
    """Reconcile a credit-card (or cash) statement total by inserting an
    adjustment on the statement's payment date.

    The UI sends the statement total as a positive number (as printed on the
    statement); credit-card payments are stored as negative expenses, so we
    negate it here to match the stored sign.
    """
    account = repository.get_account_by_name(conn, body.account)
    if not account:
        raise HTTPException(400, f"Account '{body.account}' not found")

    if body.month:
        y, m = body.month.split("-")
        month = date(int(y), int(m), 1)
    else:
        month = date.today().replace(day=1)

    # Credit-card statement totals are expenses → store as negative.
    amount = body.statement_amount
    if account["account_type"] == "credit_card" and amount > 0:
        amount = -amount

    try:
        result = controller.process_statement_adjustment(conn, body.account, month, amount)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if result is None:
        return {"ok": True, "adjustment": 0.0, "message": "Statement already matches"}
    return {
        "ok": True,
        "account": result["account"],
        "payment_date": result["payment_date"].isoformat(),
        "current_total": round(result["current_total"], 2),
        "statement_amount": round(result["statement_amount"], 2),
        "adjustment": round(result["difference"], 2),
    }
