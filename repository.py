import sqlite3
from sqlite3 import Connection
from typing import List, Dict, Any
from datetime import date

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
            category, budget, status, origin_id
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
            t["budget"],
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

def add_subscription(conn: Connection, sub: Dict[str, Any]):
    """Inserts a new record into the subscriptions table."""
    cursor = conn.cursor()
    query = """
        INSERT OR IGNORE INTO subscriptions (
            id, name, category, monthly_amount, payment_account_id,
            start_date, end_date, is_budget, underspend_behavior
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    # Set defaults if not provided
    is_budget = sub.get("is_budget", 0)
    underspend_behavior = sub.get("underspend_behavior", "keep")

    data = (
        sub["id"],
        sub["name"],
        sub["category"],
        sub["monthly_amount"],
        sub["payment_account_id"],
        sub["start_date"],
        sub.get("end_date"),
        is_budget,
        underspend_behavior,
    )
    cursor.execute(query, data)
    conn.commit()

def get_subscription_by_id(conn: Connection, sub_id: str) -> Dict[str, Any]:
    """Retrieves a single subscription by its ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
    sub = cursor.fetchone()
    if sub:
        return dict(sub)
    return None

def get_all_active_subscriptions(conn: Connection, start_range: date, end_range: date = None) -> List[Dict[str, Any]]:
    """
    Fetches all subscriptions that are active within a given date range.
    If end_range is not provided, it defaults to start_range.
    """
    if end_range is None:
        end_range = start_range
        
    cursor = conn.cursor()
    query = """
        SELECT * FROM subscriptions
        WHERE start_date <= ? AND (end_date IS NULL OR end_date >= ?)
    """
    cursor.execute(query, (end_range, start_range))
    subs = cursor.fetchall()
    return [dict(row) for row in subs]

def delete_future_forecasts(conn: Connection, origin_id: str, from_date: date):
    """
    Deletes all 'forecast' status transactions for a given subscription
    from a specific date onward.
    """
    cursor = conn.cursor()
    query = """
        DELETE FROM transactions
        WHERE origin_id = ? AND status = 'forecast' AND date_created >= ?
    """
    cursor.execute(query, (origin_id, from_date))
    conn.commit()

def update_future_forecasts_account(
    conn: Connection, origin_id: str, from_date: date, new_account_id: str
):
    """Updates the account for all future forecasts of a subscription."""
    cursor = conn.cursor()
    query = """
        UPDATE transactions
        SET account = ?
        WHERE origin_id = ? AND status = 'forecast' AND date_created >= ?
    """
    cursor.execute(query, (new_account_id, origin_id, from_date))
    conn.commit()

def get_budget_allocation_for_month(
    conn: Connection, budget_id: str, month_date: date
) -> Dict[str, Any]:
    """
    Retrieves the budget allocation transaction for a specific budget in a given month.
    """
    cursor = conn.cursor()
    start_of_month = month_date.replace(day=1)
    # Correctly calculate the end of the month
    from dateutil.relativedelta import relativedelta
    end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)
    
    query = """
        SELECT * FROM transactions
        WHERE budget = ? AND date(date_created) BETWEEN ? AND ?
        AND (description LIKE '%Budget%' OR status = 'committed')
    """
    cursor.execute(query, (budget_id, start_of_month, end_of_month))
    allocation = cursor.fetchone()
    if allocation:
        return dict(allocation)
    return None

def update_transaction_amount(conn: Connection, transaction_id: int, new_amount: float):
    """Updates the amount of a specific transaction."""
    cursor = conn.cursor()
    query = "UPDATE transactions SET amount = ? WHERE id = ?"
    cursor.execute(query, (new_amount, transaction_id))
    conn.commit()

def get_setting(conn: Connection, key: str) -> str:
    """Retrieves a specific setting value from the settings table by its key."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    setting = cursor.fetchone()
    if setting:
        return setting[0]
    return None

def commit_forecasts_for_month(conn: Connection, month_date: date):
    """
    Changes the status of all 'forecast' transactions to 'committed' for a
    given month.
    """
    cursor = conn.cursor()
    start_of_month = month_date.replace(day=1)
    from dateutil.relativedelta import relativedelta
    end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)

    query = """
        UPDATE transactions
        SET status = 'committed'
        WHERE status = 'forecast' AND date(date_created) BETWEEN ? AND ?
    """
    cursor.execute(query, (start_of_month, end_of_month))
    conn.commit()