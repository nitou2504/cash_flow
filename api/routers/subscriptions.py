import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db, get_current_user
from api.schemas import SubscriptionOut
from cashflow import repository

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SubscriptionOut])
def list_subscriptions(conn: sqlite3.Connection = Depends(get_db)):
    subs = repository.get_all_subscriptions_with_status(conn)
    return [SubscriptionOut(**s) for s in subs]
