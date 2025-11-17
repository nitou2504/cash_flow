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

def get_transaction_by_id(conn: Connection, transaction_id: int) -> Dict[str, Any]:
    """Retrieves a single transaction by its primary key."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    transaction = cursor.fetchone()
    if transaction:
        return dict(transaction)
    return None


def get_transactions_by_origin_id(conn: Connection, origin_id: str) -> List[Dict[str, Any]]:
    """Retrieves all transactions sharing a common origin_id."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE origin_id = ?", (origin_id,))
    transactions = cursor.fetchall()
    return [dict(row) for row in transactions]


def add_subscription(conn: Connection, sub: Dict[str, Any]):
    """Inserts a new record into the subscriptions table."""
    cursor = conn.cursor()
    query = """
        INSERT OR IGNORE INTO subscriptions (
            id, name, category, monthly_amount, payment_account_id,
            start_date, end_date, is_budget, underspend_behavior, is_income
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    # Set defaults if not provided
    is_budget = sub.get("is_budget", 0)
    underspend_behavior = sub.get("underspend_behavior", "keep")
    is_income = sub.get("is_income", 0)

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
        is_income,
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

def update_subscription(conn: Connection, subscription_id: str, updates: Dict[str, Any]):
    """Generically updates one or more fields of a specific subscription."""
    cursor = conn.cursor()
    fields = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values())
    values.append(subscription_id)
    
    query = f"UPDATE subscriptions SET {fields} WHERE id = ?"
    cursor.execute(query, tuple(values))
    conn.commit()

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

def delete_future_budget_allocations(conn: Connection, origin_id: str, from_date: date):
    """
    Deletes all future budget allocation transactions for a given budget,
    regardless of their status ('forecast' or 'committed').
    This is used when a budget's amount is updated, to ensure a clean slate
    for regenerating future allocations.
    """
    cursor = conn.cursor()
    query = """
        DELETE FROM transactions
        WHERE origin_id = ? AND date_created >= ?
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
        WHERE origin_id = ? AND date(date_created) BETWEEN ? AND ?
    """
    cursor.execute(query, (budget_id, start_of_month, end_of_month))
    allocation = cursor.fetchone()
    if allocation:
        return dict(allocation)
    return None

def get_total_spent_for_budget_in_month(
    conn: Connection, budget_id: str, month_date: date
) -> float:
    """
    Calculates the total amount spent against a specific budget in a given month.
    It sums up all transactions linked to the budget, excluding the initial
    budget allocation transaction itself.
    """
    cursor = conn.cursor()
    start_of_month = month_date.replace(day=1)
    from dateutil.relativedelta import relativedelta
    end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)

    query = """
        SELECT SUM(amount) FROM transactions
        WHERE budget = ?
        AND date(date_created) BETWEEN ? AND ?
        AND (origin_id IS NULL OR origin_id != ?)
        AND status != 'pending'
    """
    cursor.execute(query, (budget_id, start_of_month, end_of_month, budget_id))
    total = cursor.fetchone()[0]
    return abs(total) if total else 0.0


def get_total_committed_for_budget_in_month(
    conn: Connection, budget_id: str, month_date: date
) -> float:
    """
    Calculates the total of committed expenses against a budget for a future month.
    This is used by the forecast generator to correctly adjust the starting
    balance of a new budget allocation.
    """
    cursor = conn.cursor()
    start_of_month = month_date.replace(day=1)
    from dateutil.relativedelta import relativedelta
    end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)

    query = """
        SELECT SUM(amount) FROM transactions
        WHERE budget = ?
        AND status = 'committed'
        AND date(date_payed) BETWEEN ? AND ?
        AND (origin_id IS NULL OR origin_id != ?)
    """
    cursor.execute(query, (budget_id, start_of_month, end_of_month, budget_id))
    total = cursor.fetchone()[0]
    return abs(total) if total else 0.0


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

def commit_past_and_current_forecasts(conn: Connection, month_date: date):
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
        WHERE status = 'forecast' AND date(date_payed) <= ?
    """
    cursor.execute(query, (end_of_month,))
    conn.commit()

def update_transaction(conn: Connection, transaction_id: int, updates: Dict[str, Any]):
    """Generically updates one or more fields of a specific transaction."""
    cursor = conn.cursor()
    fields = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values())
    values.append(transaction_id)
    
    query = f"UPDATE transactions SET {fields} WHERE id = ?"
    cursor.execute(query, tuple(values))
    conn.commit()

def delete_transaction(conn: Connection, transaction_id: int):
    """Permanently removes a single transaction from the database."""
    cursor = conn.cursor()
    query = "DELETE FROM transactions WHERE id = ?"
    cursor.execute(query, (transaction_id,))
    conn.commit()

def get_transactions_with_running_balance(conn: Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all transactions and calculates a cumulative running balance.
    It relies on the core system logic where budget allocation amounts are
    dynamically updated, ensuring the 'amount' column is always the source
    of truth for cash flow.
    """
    transactions = get_all_transactions(conn) # Already sorted by date_payed
    
    running_balance = 0.0
    processed_transactions = []

    for t in transactions:
        transaction_dict = dict(t)
        # Only add to the balance if the transaction is not pending
        if transaction_dict["status"] != "pending":
            running_balance += transaction_dict["amount"]
        transaction_dict["running_balance"] = running_balance
        processed_transactions.append(transaction_dict)
        
    return processed_transactions


def get_all_accounts(conn: Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all accounts from the database.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY account_id")
    accounts = cursor.fetchall()
    return [dict(row) for row in accounts]


def get_all_budgets(conn: Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all subscriptions that are marked as budgets.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE is_budget = 1 ORDER BY name")
    budgets = cursor.fetchall()
    return [dict(row) for row in budgets]


def get_all_budgets_with_status(conn: Connection, reference_date: date = None) -> List[Dict[str, Any]]:
    """
    Retrieves all budgets with their status (Active or Expired) as of a reference date.
    If reference_date is None, uses today's date.

    Status logic:
    - Active: Budget is usable (includes current and future budgets with forecasts)
    - Expired: end_date < ref_date (budget has ended)

    Since the system creates forecast allocations in advance, future budgets
    are considered "Active" rather than having a separate "Upcoming" status.
    """
    from datetime import date as date_module

    if reference_date is None:
        reference_date = date_module.today()

    budgets = get_all_budgets(conn)

    budgets_with_status = []
    for budget in budgets:
        budget_dict = dict(budget)

        # Determine status
        end_date = budget_dict.get('end_date')

        if end_date and end_date < reference_date:
            status = "Expired"
        else:
            status = "Active"  # Includes current and future budgets

        budget_dict['status'] = status
        budgets_with_status.append(budget_dict)

    return budgets_with_status


def add_account(conn: Connection, account_id: str, account_type: str, cut_off_day: int = None, payment_day: int = None):
    """
    Inserts a new account into the accounts table.
    """
    cursor = conn.cursor()
    query = "INSERT OR IGNORE INTO accounts (account_id, account_type, cut_off_day, payment_day) VALUES (?, ?, ?, ?)"
    cursor.execute(query, (account_id, account_type, cut_off_day, payment_day))
    conn.commit()


def get_all_categories(conn: Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all categories from the database.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()
    return [dict(row) for row in categories]


def category_exists(conn: Connection, category_name: str) -> bool:
    """
    Checks if a category exists in the database.
    Returns True if found, False otherwise.
    """
    if category_name is None:
        return True  # Allow None/null categories

    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM categories WHERE name = ?", (category_name,))
    return cursor.fetchone() is not None


def add_category(conn: Connection, name: str, description: str):
    """
    Inserts a new category into the categories table.
    Raises ValueError if the category already exists.
    """
    if category_exists(conn, name):
        raise ValueError(f"Category '{name}' already exists.")

    cursor = conn.cursor()
    query = "INSERT INTO categories (name, description) VALUES (?, ?)"
    cursor.execute(query, (name, description))
    conn.commit()


def update_category(conn: Connection, name: str, new_description: str):
    """
    Updates the description of an existing category.
    Raises ValueError if the category doesn't exist.
    """
    if not category_exists(conn, name):
        raise ValueError(f"Category '{name}' does not exist.")

    cursor = conn.cursor()
    query = "UPDATE categories SET description = ? WHERE name = ?"
    cursor.execute(query, (new_description, name))
    conn.commit()


def delete_category(conn: Connection, name: str):
    """
    Deletes a category from the categories table.
    Raises ValueError if the category doesn't exist.
    """
    if not category_exists(conn, name):
        raise ValueError(f"Category '{name}' does not exist.")

    cursor = conn.cursor()
    query = "DELETE FROM categories WHERE name = ?"
    cursor.execute(query, (name,))
    conn.commit()
