import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db, get_current_user
from api.schemas import AccountOut
from cashflow import repository

router = APIRouter(prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AccountOut])
def list_accounts(conn: sqlite3.Connection = Depends(get_db)):
    return [AccountOut(**a) for a in repository.get_all_accounts(conn)]
