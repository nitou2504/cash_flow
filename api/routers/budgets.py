import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import get_db, get_current_user
from api.schemas import SubscriptionOut, BudgetSpending
from cashflow import repository

router = APIRouter(prefix="/api/budgets", tags=["budgets"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SubscriptionOut])
def list_budgets(conn: sqlite3.Connection = Depends(get_db)):
    budgets = repository.get_all_budgets_with_status(conn)
    return [SubscriptionOut(**b) for b in budgets]


@router.get("/spending", response_model=list[BudgetSpending])
def budget_spending(
    month: Optional[str] = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    ref = date.fromisoformat(month) if month else date.today().replace(day=1)
    budgets = repository.get_all_budgets_with_status(conn, reference_date=ref)
    active = [b for b in budgets if b.get("status") == "Active"]

    result = []
    for b in active:
        alloc_row = repository.get_budget_allocation_for_month(conn, b["id"], ref)
        allocated = abs(alloc_row["amount"]) if alloc_row else b["monthly_amount"]
        spent = repository.get_total_spent_for_budget_in_month(conn, b["id"], ref)
        result.append(BudgetSpending(
            id=b["id"],
            name=b["name"],
            monthly_amount=b["monthly_amount"],
            payment_account_id=b["payment_account_id"],
            category=b["category"],
            allocated=allocated,
            spent=spent,
            remaining=max(0, allocated - spent),
        ))
    return result
