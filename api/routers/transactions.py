import sqlite3
from collections import OrderedDict
from datetime import date, datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db, get_current_user
from api.schemas import (
    BalancePoint, MonthGroup, TimelineResponse, TimelineStats,
    TimelineTransaction, TransactionCreate, TransactionCreateResponse,
    TransactionOut,
)
from cashflow import repository
from cashflow import transactions as txn_factory

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


def _txn_to_timeline(t: dict, budget_ids: set, invoice_txn_ids: set) -> TimelineTransaction:
    is_alloc = t.get("origin_id") in budget_ids and t.get("budget") == t.get("origin_id")
    return TimelineTransaction(
        id=t.get("id", 0),
        date_created=str(t["date_created"]),
        date_payed=str(t["date_payed"]) if t["date_payed"] else "",
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
        is_budget_allocation=is_alloc,
        has_invoice=t.get("id", 0) in invoice_txn_ids,
    )


# ── List ──

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


# ── Timeline ──

@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    from_month: Optional[str] = None,
    months: int = Query(3, ge=1, le=24),
    sort_by: str = Query("date_payed", pattern="^(date_payed|date_created)$"),
    include_planning: bool = True,
    summary: bool = False,
    account: Optional[str] = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    all_txns = repository.get_transactions_with_running_balance(conn)

    # Monthly minimums for MoM (computed from ALL transactions before any filtering)
    monthly_minimums: dict[str, float] = {}
    for t in all_txns:
        mk = t["date_payed"].strftime("%Y-%m") if hasattr(t["date_payed"], "strftime") else str(t["date_payed"])[:7]
        rb = t["running_balance"]
        if mk not in monthly_minimums or rb < monthly_minimums[mk]:
            monthly_minimums[mk] = rb

    # Budget IDs for allocation detection
    budgets = repository.get_all_budgets(conn)
    budget_ids = {b["id"] for b in budgets}

    # Invoice-linked transaction IDs
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT registered_txn_id FROM consumos "
        "WHERE registered_txn_id IS NOT NULL AND matched_invoice_number IS NOT NULL"
    )
    invoice_txn_ids = {row[0] for row in cursor.fetchall()}

    # Summary mode: aggregate CC transactions
    display_txns = list(all_txns)
    if summary:
        accounts_list = repository.get_all_accounts(conn)
        cc_accounts = {a["account_id"] for a in accounts_list if a["account_type"] == "credit_card"}
        summarized: dict = {}
        other = []
        planning_txns = []
        pending_txns = []

        for t in all_txns:
            if t["account"] in cc_accounts:
                if not include_planning and t["status"] == "planning":
                    planning_txns.append(t)
                    continue
                if t["status"] == "pending":
                    pending_txns.append(t)
                    continue
                if sort_by == "date_created":
                    key = (t["account"], t["date_created"].strftime("%Y-%m") if hasattr(t["date_created"], "strftime") else str(t["date_created"])[:7])
                else:
                    key = (t["account"], t["date_payed"])
                if key not in summarized:
                    summarized[key] = {"amount": 0.0, "statuses": set(), "running_balance": 0.0}
                summarized[key]["amount"] += t["amount"]
                summarized[key]["statuses"].add(t["status"])
                summarized[key]["running_balance"] = t["running_balance"]
            else:
                other.append(t)

        summary_txns = []
        for (acct, date_key), data in summarized.items():
            statuses = data["statuses"]
            st = "forecast"
            if "committed" in statuses:
                st = "committed"
            elif "pending" in statuses:
                st = "pending"
            elif "planning" in statuses:
                st = "planning"

            if sort_by == "date_created":
                month_date = datetime.strptime(date_key, "%Y-%m").date().replace(day=1)
                summary_txns.append({
                    "id": 0, "date_created": month_date, "date_payed": month_date,
                    "description": f"{acct} ({month_date.strftime('%b')})",
                    "account": acct, "amount": data["amount"],
                    "category": "Credit Card", "budget": None,
                    "status": st, "origin_id": None, "source": None,
                    "needs_review": 0, "running_balance": 0.0,
                })
            else:
                summary_txns.append({
                    "id": 0, "date_created": date_key, "date_payed": date_key,
                    "description": f"{acct} Payment",
                    "account": acct, "amount": data["amount"],
                    "category": "Credit Card", "budget": None,
                    "status": st, "origin_id": None, "source": None,
                    "needs_review": 0, "running_balance": data["running_balance"],
                })

        display_txns = other + summary_txns + planning_txns + pending_txns

    # Sort
    date_field = "date_created" if sort_by == "date_created" else "date_payed"
    display_txns.sort(key=lambda t: (str(t[date_field]), t.get("id", 0)))

    # Account filter
    if account:
        display_txns = [t for t in display_txns if t.get("account") == account]

    # Planning filter
    if not include_planning:
        display_txns = [t for t in display_txns if t["status"] != "planning"]

    # Date range
    today = date.today()
    if from_month:
        try:
            start_date = datetime.strptime(from_month, "%Y-%m").date().replace(day=1)
        except ValueError:
            start_date = today.replace(day=1)
    else:
        start_date = today.replace(day=1)
    end_date = (start_date + relativedelta(months=months)) - relativedelta(days=1)

    # Pending from past
    pending_from_past = [
        t for t in display_txns
        if t["status"] == "pending" and _to_date(t[date_field]) < start_date
    ]

    # Transactions in period
    txns_in_period = [
        t for t in display_txns
        if start_date <= _to_date(t[date_field]) <= end_date
    ]

    # Starting balance (date_payed mode only)
    starting_balance = None
    if sort_by != "date_created":
        for t in reversed(display_txns):
            if _to_date(t["date_payed"]) < start_date:
                starting_balance = t["running_balance"]
                break

    # Monthly spending (date_created mode only)
    monthly_spending: dict[str, float] = {}
    if sort_by == "date_created":
        for t in txns_in_period:
            if t["amount"] < 0 and t["status"] != "pending":
                mk = _month_key(t["date_created"])
                monthly_spending[mk] = monthly_spending.get(mk, 0.0) + t["amount"]

    # Group by month
    sorted_month_keys = sorted(monthly_minimums.keys())
    month_groups: OrderedDict[str, list] = OrderedDict()
    for t in txns_in_period:
        mk = _month_key(t[date_field])
        if mk not in month_groups:
            month_groups[mk] = []
        month_groups[mk].append(t)

    result_months = []
    for mk, group_txns in month_groups.items():
        total_in = sum(t["amount"] for t in group_txns if t["amount"] > 0 and t["status"] == "committed")
        total_out = sum(abs(t["amount"]) for t in group_txns if t["amount"] < 0 and t["status"] == "committed")

        # MoM change
        mom = None
        if sort_by != "date_created" and mk in monthly_minimums:
            idx = sorted_month_keys.index(mk) if mk in sorted_month_keys else -1
            if idx > 0:
                prev_mk = sorted_month_keys[idx - 1]
                mom = monthly_minimums[mk] - monthly_minimums.get(prev_mk, 0.0)

        # Month label
        try:
            month_label = datetime.strptime(mk, "%Y-%m").strftime("%B %Y")
        except ValueError:
            month_label = mk

        tl_txns = [_txn_to_timeline(t, budget_ids, invoice_txn_ids) for t in group_txns]

        result_months.append(MonthGroup(
            month_key=mk,
            month_label=month_label,
            transactions=tl_txns,
            mom_change=mom,
            month_spending=monthly_spending.get(mk),
            total_in=total_in,
            total_out=total_out,
        ))

    # Balance series for chart (date_payed, non-pending, within visible range)
    balance_by_date: dict[str, float] = {}
    for t in all_txns:
        if t["status"] == "pending":
            continue
        d = str(t["date_payed"])
        if str(start_date) <= d <= str(end_date):
            balance_by_date[d] = t["running_balance"]
    balance_series = [BalancePoint(date=d, balance=b) for d, b in balance_by_date.items()]

    # Stats
    visible_balances = [t["running_balance"] for t in txns_in_period if t["status"] != "pending"]
    lowest = min(visible_balances) if visible_balances else 0.0
    forecast_end = visible_balances[-1] if visible_balances else 0.0

    current_mk = today.strftime("%Y-%m")
    stats_mom = 0.0
    if current_mk in monthly_minimums and current_mk in sorted_month_keys:
        idx = sorted_month_keys.index(current_mk)
        if idx > 0:
            stats_mom = monthly_minimums[current_mk] - monthly_minimums[sorted_month_keys[idx - 1]]

    pending_past_tl = [_txn_to_timeline(t, budget_ids, invoice_txn_ids) for t in pending_from_past]

    return TimelineResponse(
        pending_from_past=pending_past_tl,
        starting_balance=starting_balance,
        months=result_months,
        balance_series=balance_series,
        stats=TimelineStats(mom_change=stats_mom, forecast_end=forecast_end, lowest_in_period=lowest),
    )


def _to_date(d) -> date:
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def _month_key(d) -> str:
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m")
    return str(d)[:7]


# ── Create ──

@router.post("", response_model=TransactionCreateResponse)
def create_transaction(
    body: TransactionCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    account = repository.get_account_by_name(conn, body.account)
    if not account:
        raise HTTPException(status_code=400, detail=f"Account '{body.account}' not found")

    txn_date = date.fromisoformat(body.date) if body.date else date.today()
    is_pending = body.status == "pending"
    is_planning = body.status == "planning"

    if body.splits:
        splits = [{"amount": s.amount, "category": s.category, "budget": s.budget} for s in body.splits]
        txn_list = txn_factory.create_split_transactions(
            description=body.description, splits=splits, account=account,
            transaction_date=txn_date, is_income=body.is_income,
            is_pending=is_pending, is_planning=is_planning,
        )
    elif body.installments and body.installments >= 2:
        txn_list = txn_factory.create_installment_transactions(
            description=body.description, total_amount=body.amount,
            installments=body.installments, category=body.category,
            budget=body.budget, account=account, transaction_date=txn_date,
            grace_period_months=body.grace_period_months,
            start_from_installment=body.start_from_installment,
            is_income=body.is_income, is_pending=is_pending, is_planning=is_planning,
        )
    else:
        txn = txn_factory.create_single_transaction(
            description=body.description, amount=body.amount,
            category=body.category, budget=body.budget, account=account,
            transaction_date=txn_date, grace_period_months=body.grace_period_months,
            is_income=body.is_income, is_pending=is_pending, is_planning=is_planning,
        )
        txn_list = [txn]

    ids = repository.add_transactions(conn, txn_list)
    created = []
    for i, tid in enumerate(ids):
        t = dict(txn_list[i])
        t["id"] = tid
        created.append(_txn_to_out(t))

    return TransactionCreateResponse(count=len(ids), ids=ids, transactions=created)


# ── Preview ──

@router.post("/preview", response_model=list[TransactionOut])
def preview_transaction(
    body: TransactionCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    account = repository.get_account_by_name(conn, body.account)
    if not account:
        raise HTTPException(status_code=400, detail=f"Account '{body.account}' not found")

    txn_date = date.fromisoformat(body.date) if body.date else date.today()
    is_pending = body.status == "pending"
    is_planning = body.status == "planning"

    if body.splits:
        splits = [{"amount": s.amount, "category": s.category, "budget": s.budget} for s in body.splits]
        txn_list = txn_factory.create_split_transactions(
            description=body.description, splits=splits, account=account,
            transaction_date=txn_date, is_income=body.is_income,
            is_pending=is_pending, is_planning=is_planning,
        )
    elif body.installments and body.installments >= 2:
        txn_list = txn_factory.create_installment_transactions(
            description=body.description, total_amount=body.amount,
            installments=body.installments, category=body.category,
            budget=body.budget, account=account, transaction_date=txn_date,
            grace_period_months=body.grace_period_months,
            start_from_installment=body.start_from_installment,
            is_income=body.is_income, is_pending=is_pending, is_planning=is_planning,
        )
    else:
        txn = txn_factory.create_single_transaction(
            description=body.description, amount=body.amount,
            category=body.category, budget=body.budget, account=account,
            transaction_date=txn_date, grace_period_months=body.grace_period_months,
            is_income=body.is_income, is_pending=is_pending, is_planning=is_planning,
        )
        txn_list = [txn]

    return [_txn_to_out({**t, "id": 0}) for t in txn_list]


# ── Single + Group ──

@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, conn: sqlite3.Connection = Depends(get_db)):
    t = repository.get_transaction_by_id(conn, transaction_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _txn_to_out(dict(t))


@router.get("/{transaction_id}/group", response_model=list[TransactionOut])
def get_transaction_group(transaction_id: int, conn: sqlite3.Connection = Depends(get_db)):
    t = repository.get_transaction_by_id(conn, transaction_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    t = dict(t)
    if not t.get("origin_id"):
        return [_txn_to_out(t)]
    group = repository.get_transactions_by_origin_id(conn, t["origin_id"])
    return [_txn_to_out(dict(g)) for g in group]
