
import sqlite3
from sqlite3 import Connection
from typing import List, Dict, Any

def get_account_by_name(conn: Connection, name: str) -> Dict[str, Any]:
    """
    Retrieves a single account's details from the database by its name.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE account_id = ?", (name,))
    account = cursor.fetchone()
    if account:
        return dict(account)
    return None

def add_transactions(conn: Connection, transactions: List[Dict[str, Any]]):
    """
    Inserts a list of one or more transaction dictionaries into the database.
    """
    cursor = conn.cursor()
    query = """
        INSERT INTO transactions (
            date_created, date_payed, description, account, amount,
            category, budget_category, status, origin_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    data = [
        (
            t["date_created"],
            t["date_payed"],
            t["description"],
            t["account"],
            t["amount"],
            t["category"],
            t["budget_category"],
            t["status"],
            t["origin_id"],
        )
        for t in transactions
    ]
    cursor.executemany(query, data)
    conn.commit()

def get_all_transactions(conn: Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all transactions from the database for display or export.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions ORDER BY date_payed")
    transactions = cursor.fetchall()
    return [dict(row) for row in transactions]
