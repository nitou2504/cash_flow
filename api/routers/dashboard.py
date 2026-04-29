import sqlite3
from datetime import date
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, get_current_user
from api.schemas import (
    AccountOut, BalancePoint, BudgetSpending, CCCardOut, DashboardOut,
)
from api.routers.transactions import _txn_to_out
from cashflow import repository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=DashboardOut)
def dashboard(
    months: int = Query(3, ge=1, le=24),
    conn: sqlite3.Connection = Depends(get_db),
):
    today = date.today()
    today_str = str(today)
    month_start = today.replace(day=1)
    month_prefix = today.strftime("%Y-%m")

    accounts = repository.get_all_accounts(conn)
    txns = repository.get_transactions_with_running_balance(conn)

    non_pending = [t for t in txns if t["status"] != "pending"]
    committed = [t for t in txns if t["status"] == "committed"]

    # #1C — current_balance: last non-pending txn with date_payed <= today
    actual_to_today = [t for t in non_pending if str(t["date_payed"]) <= today_str]
    current_balance = actual_to_today[-1]["running_balance"] if actual_to_today else 0.0

    # #1C — projected balance: end of current month (including forecasts)
    month_end = [t for t in non_pending if str(t["date_payed"]).startswith(month_prefix)]
    projected_balance = month_end[-1]["running_balance"] if month_end else current_balance

    # #5A — balance series filtered by months param
    series_start = (month_start - relativedelta(months=months - 1))
    series_start_str = str(series_start)
    balance_by_date: dict[str, float] = {}
    for t in non_pending:
        d = str(t["date_payed"])
        if d >= series_start_str and d <= today_str:
            balance_by_date[d] = t["running_balance"]
    balance_series = [BalancePoint(date=d, balance=b) for d, b in balance_by_date.items()]

    # Month income/expenses
    month_in_balance = [t for t in non_pending if str(t["date_payed"]).startswith(month_prefix)]
    month_income = sum(t["amount"] for t in month_in_balance if t["amount"] > 0)
    month_expenses = sum(abs(t["amount"]) for t in month_in_balance if t["amount"] < 0)

    # #2 — recent by date_created <= today
    recent_committed = [t for t in committed if str(t["date_created"]) <= today_str]
    recent_committed.sort(key=lambda t: str(t["date_created"]), reverse=True)
    recent = [_txn_to_out(t) for t in recent_committed[:8]]

    # CC debt per cycle: current bill, next bill, total owed
    # "Owed" = date_created <= today (already purchased, not future forecasts)
    cc_accounts = [a for a in accounts if a["account_type"] == "credit_card"]
    cc_cards = []
    for cc in cc_accounts:
        cc_name = cc["account_id"]
        owed_txns = [t for t in non_pending
                     if t["account"] == cc_name
                     and str(t["date_payed"]) > today_str
                     and str(t["date_created"]) <= today_str
                     and t["amount"] < 0]
        cycles: dict[str, float] = {}
        for t in owed_txns:
            d = str(t["date_payed"])
            cycles[d] = cycles.get(d, 0.0) + t["amount"]
        sorted_dates = sorted(cycles.keys())

        current_date = sorted_dates[0] if sorted_dates else None
        current_owed = abs(cycles[current_date]) if current_date else 0.0
        next_date = sorted_dates[1] if len(sorted_dates) > 1 else None
        next_owed = abs(cycles[next_date]) if next_date else 0.0
        total_owed = sum(abs(v) for v in cycles.values())

        # If current payment date is within ±3 days of today, label shifts
        if current_date:
            from datetime import timedelta
            pay_date = date.fromisoformat(current_date)
            if abs((pay_date - today).days) <= 3:
                pass  # keep as "current" — it's imminent

        cc_cards.append(CCCardOut(
            name=cc_name, account_type=cc["account_type"],
            current_cycle_owed=current_owed,
            current_cycle_date=current_date,
            next_cycle_owed=next_owed,
            next_cycle_date=next_date,
            total_owed=total_owed,
            cut_off_day=cc.get("cut_off_day"), payment_day=cc.get("payment_day"),
        ))

    review_txns = repository.get_transactions_needing_review(conn)
    review_count = len(review_txns)

    # #4C — budgets whose date range includes today
    budgets_raw = repository.get_all_budgets_with_status(conn, reference_date=month_start)
    active_budgets = [b for b in budgets_raw if b.get("status") == "Active"]
    budget_spending = []
    for b in active_budgets:
        b_start = str(b.get("start_date") or "")
        b_end = str(b.get("end_date") or "9999-12-31")
        if b_start > today_str or b_end < today_str:
            continue
        allocated = b["monthly_amount"]
        spent = repository.get_total_spent_for_budget_in_month(conn, b["id"], month_start)
        budget_spending.append(BudgetSpending(
            id=b["id"], name=b["name"], monthly_amount=b["monthly_amount"],
            payment_account_id=b["payment_account_id"], category=b["category"],
            allocated=allocated, spent=spent, remaining=max(0, allocated - spent),
        ))

    cc_debt = sum(c.total_owed for c in cc_cards)
    total_budget = sum(b.allocated for b in budget_spending)

    return DashboardOut(
        accounts=[AccountOut(**a) for a in accounts],
        balance_series=balance_series,
        budgets=budget_spending,
        review_count=review_count,
        recent_transactions=recent,
        cc_cards=cc_cards,
        current_balance=current_balance,
        projected_balance=projected_balance,
        cc_debt=cc_debt,
        total_budget=total_budget,
        month_income=month_income,
        month_expenses=month_expenses,
    )
