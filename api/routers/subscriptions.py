import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db, get_current_user
from api.schemas import SubscriptionOut, SubscriptionCreate, SubscriptionUpdate
from cashflow import repository, controller

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"], dependencies=[Depends(get_current_user)])


def _slug_id(name: str, is_budget: bool) -> str:
    prefix = "budget" if is_budget else "sub"
    slug = name.lower().strip().replace(" ", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    return f"{prefix}_{slug}"


@router.get("", response_model=list[SubscriptionOut])
def list_subscriptions(conn: sqlite3.Connection = Depends(get_db)):
    subs = repository.get_all_subscriptions_with_status(conn)
    return [SubscriptionOut(**s) for s in subs]


@router.post("", response_model=SubscriptionOut, status_code=201)
def create_subscription(body: SubscriptionCreate, conn: sqlite3.Connection = Depends(get_db)):
    if not repository.get_account_by_name(conn, body.payment_account_id):
        raise HTTPException(400, f"Account '{body.payment_account_id}' not found")

    sub_id = _slug_id(body.name, body.is_budget)
    if repository.get_subscription_by_id(conn, sub_id):
        raise HTTPException(409, f"A subscription with id '{sub_id}' already exists")

    sub_data = {
        "id": sub_id,
        "name": body.name,
        "category": body.category,
        "monthly_amount": body.monthly_amount,
        "payment_account_id": body.payment_account_id,
        "start_date": body.start_date,  # process_subscription_request handles None/str
        "end_date": body.end_date,
        "is_budget": 1 if body.is_budget else 0,
        "is_income": 1 if body.is_income else 0,
        "underspend_behavior": body.underspend_behavior,
    }
    try:
        controller.process_subscription_request(conn, sub_data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    created = repository.get_subscription_by_id(conn, sub_id)
    rows = repository.get_all_subscriptions_with_status(conn)
    enriched = next((r for r in rows if r["id"] == sub_id), created)
    return SubscriptionOut(**enriched)


@router.put("/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(subscription_id: str, body: SubscriptionUpdate, conn: sqlite3.Connection = Depends(get_db)):
    existing = repository.get_subscription_by_id(conn, subscription_id)
    if not existing:
        raise HTTPException(404, "Subscription not found")

    provided = body.model_dump(exclude_unset=True)
    retroactive = bool(provided.pop("retroactive", False))

    updates: dict = {}
    for key in ("name", "category", "monthly_amount", "payment_account_id", "underspend_behavior"):
        if key in provided and provided[key] is not None:
            updates[key] = provided[key]
    if "end_date" in provided:
        val = provided["end_date"]
        if val is None or str(val).lower() == "none":
            updates["end_date"] = None
        else:
            # controller's rename logic calls .strftime(), so pass a date object
            updates["end_date"] = date.fromisoformat(str(val))

    if "payment_account_id" in updates and not repository.get_account_by_name(conn, updates["payment_account_id"]):
        raise HTTPException(400, f"Account '{updates['payment_account_id']}' not found")

    if not updates:
        raise HTTPException(400, "No changes provided")

    try:
        # process_budget_update regenerates forecasts for budgets; for plain
        # subscriptions it still updates the row + future forecasts correctly.
        controller.process_budget_update(conn, subscription_id, updates, retroactive=retroactive)
    except ValueError as e:
        raise HTTPException(400, str(e))

    rows = repository.get_all_subscriptions_with_status(conn)
    enriched = next((r for r in rows if r["id"] == subscription_id), None)
    if not enriched:
        raise HTTPException(404, "Subscription not found after update")
    return SubscriptionOut(**enriched)


@router.delete("/{subscription_id}")
def delete_subscription(subscription_id: str, conn: sqlite3.Connection = Depends(get_db)):
    if not repository.get_subscription_by_id(conn, subscription_id):
        raise HTTPException(404, "Subscription not found")
    try:
        controller.process_budget_deletion(conn, subscription_id)
    except ValueError as e:
        # e.g. committed transactions exist — surface the guidance to the user
        raise HTTPException(409, str(e))
    return {"ok": True}
