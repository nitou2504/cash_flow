import sqlite3
from datetime import date
from typing import Dict, Any

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
                budget_category=request.get("budget_category"),
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
            budget_category=request.get("budget_category"),
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
        "budget_category": "food"
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
        "budget_category": "shopping"
    }
    process_transaction_request(conn, installment_request)

    # --- Split Transaction Example ---
    split_request = {
        "type": "split",
        "description": "Grocery Store",
        "account": "Amex Produbanco",
        "splits": [
            { "amount": 80, "category": "groceries", "budget_category": "food" },
            { "amount": 15, "category": "household", "budget_category": "home" }
        ]
    }
    process_transaction_request(conn, split_request)

    # --- Verify by fetching all transactions ---
    all_trans = repository.get_all_transactions(conn)
    print("\n--- All Transactions in Database ---")
    for t in all_trans:
        print(dict(t))
    
    conn.close()
