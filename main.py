import sqlite3
from datetime import date
from typing import Dict, Any
from dateutil.relativedelta import relativedelta

import repository
import transactions

def process_transaction_request(conn: sqlite3.Connection, request: Dict[str, Any]):
    """
    Acts as the main router for incoming transaction requests.
    """
    transaction_type = request.get("type")
    account_name = request.get("account")
    
    account = repository.get_account_by_name(conn, account_name)
    if not account:
        raise ValueError(f"Account '{account_name}' not found.")

    transaction_date = date.today()
    new_transactions = []

    if transaction_type == "simple":
        new_transactions.append(
            transactions.create_single_transaction(
                description=request["description"],
                amount=request["amount"],
                category=request.get("category"),
                budget=request.get("budget"),
                account=account,
                transaction_date=transaction_date,
            )
        )
    elif transaction_type == "installment":
        new_transactions = transactions.create_installment_transactions(
            description=request["description"],
            total_amount=request["total_amount"],
            installments=request["installments"],
            category=request.get("category"),
            budget=request.get("budget"),
            account=account,
            transaction_date=transaction_date,
        )
    elif transaction_type == "split":
        new_transactions = transactions.create_split_transactions(
            description=request["description"],
            splits=request["splits"],
            account=account,
            transaction_date=transaction_date,
        )
    else:
        raise ValueError(f"Invalid transaction type: {transaction_type}")

    if new_transactions:
        repository.add_transactions(conn, new_transactions)
        print(f"Successfully added {len(new_transactions)} transaction(s).")

def generate_forecasts(conn: sqlite3.Connection, horizon_months: int):
    """
    A scheduler job that creates and maintains forecast transactions up to a
    defined horizon.
    """
    today = date.today()
    horizon_date = today + relativedelta(months=horizon_months)
    
    active_subscriptions = repository.get_all_active_subscriptions(conn, today, horizon_date)
    all_transactions = repository.get_all_transactions(conn)

    for sub in active_subscriptions:
        # Find the last forecast date for this subscription
        last_forecast_date = None
        for t in reversed(all_transactions):
            if t['origin_id'] == sub['id'] and t['status'] == 'forecast':
                last_forecast_date = t['date_created']
                break
        
        # Determine the start period for generating new forecasts
        if last_forecast_date:
            # Start from the month after the last forecast
            start_period = last_forecast_date + relativedelta(months=1)
        else:
            # No forecasts exist, start from the subscription's start date or today
            start_period = max(sub['start_date'], today)

        # Determine the end period
        end_period = sub.get('end_date') or horizon_date
        if end_period > horizon_date:
            end_period = horizon_date

        if start_period > end_period:
            continue

        account = repository.get_account_by_name(conn, sub['payment_account_id'])
        if not account:
            print(f"Warning: Account '{sub['payment_account_id']}' for subscription '{sub['id']}' not found. Skipping.")
            continue

        new_forecasts = transactions.create_recurrent_transactions(
            subscription=sub,
            account=account,
            start_period=start_period,
            end_period=end_period
        )

        if new_forecasts:
            repository.add_transactions(conn, new_forecasts)
            print(f"Generated {len(new_forecasts)} new forecasts for '{sub['name']}'.")


if __name__ == '__main__':
    # Example Usage
    from database import create_connection, initialize_database

    # Initialize and connect to the database
    db_path = "cash_flow.db"
    initialize_database(db_path)
    conn = create_connection(db_path)

    # --- Simple Transaction Example ---
    simple_request = {
        "type": "simple",
        "description": "Lunch at cafe",
        "amount": 15.75,
        "account": "Cash",
        "category": "dining",
        "budget": "food"
    }
    process_transaction_request(conn, simple_request)

    # --- Installment Transaction Example ---
    installment_request = {
        "type": "installment",
        "description": "New Laptop",
        "total_amount": 1200.00,
        "installments": 6,
        "account": "Visa Produbanco",
        "category": "electronics",
        "budget": "shopping"
    }
    process_transaction_request(conn, installment_request)

    # --- Split Transaction Example ---
    split_request = {
        "type": "split",
        "description": "Grocery Store",
        "account": "Amex Produbanco",
        "splits": [
            { "amount": 80, "category": "groceries", "budget": "food" },
            { "amount": 15, "category": "household", "budget": "home" }
        ]
    }
    process_transaction_request(conn, split_request)

    # --- Recurrent Transaction Example ---
    print("\n--- Setting up Subscription and Generating Forecasts ---")
    netflix_subscription = {
        "id": "sub_netflix",
        "name": "Netflix Subscription",
        "category": "entertainment",
        "monthly_amount": 15.99,
        "payment_account_id": "Visa Produbanco",
        "start_date": date.today() - relativedelta(months=1),
    }
    repository.add_subscription(conn, netflix_subscription)
    generate_forecasts(conn, horizon_months=6)

    # --- Verify by fetching all transactions ---
    all_trans = repository.get_all_transactions(conn)
    print("\n--- All Transactions in Database ---")
    for t in all_trans:
        print(dict(t))
    
    conn.close()