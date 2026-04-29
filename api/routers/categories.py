import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db, get_current_user
from api.schemas import CategoryOut
from cashflow import repository

router = APIRouter(prefix="/api/categories", tags=["categories"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CategoryOut])
def list_categories(conn: sqlite3.Connection = Depends(get_db)):
    return [CategoryOut(**c) for c in repository.get_all_categories(conn)]
