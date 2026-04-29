import sqlite3
from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from cashflow.config import DB_PATH
from cashflow.database import create_connection
from api.auth import SECRET_KEY, ALGORITHM


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = create_connection(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(request: Request) -> bool:
    from api.auth import DEV_MODE
    if DEV_MODE:
        return True
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") != "owner":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return True
