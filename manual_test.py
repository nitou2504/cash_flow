from datetime import date
from database import create_connection, initialize_database
from main import process_transaction_request, run_monthly_rollover
from repository import add_subscription
from interface import view_transactions, export_transactions_to_csv

def run_manual_test():
    """
    A simple script to manually test the view and export commands.
    """
    db_path = "manual_test.db"
    print(f"--- Initializing a new database: {db_path} ---")
    initialize_database(db_path)
    conn = create_connection(db_path)

    print("\n--- Setting up a 'Food' budget and running rollover ---")
    today = date.today()
    add_subscription(conn, {
        "id": "budget_food", "name": "Food Budget", "category": "Food",
        "monthly_amount": 400, "payment_account_id": "Cash",
        "start_date": today.replace(day=1), "is_budget": True
    })

    print("\n--- Setting up income subscription and running rollover ---")
    add_subscription(conn, {
        "id": "income_salary", "name": "Salary", "category": "Income",
        "monthly_amount": 1100, "payment_account_id": "Cash",
        "start_date": today.replace(day=1), "is_budget": False
    })

    add_subscription(conn, {
        "id": "netflix_subscription", "name": "Netflix", "category": "Entertainment",
        "monthly_amount": 15, "payment_account_id": "Cash",
        "start_date": today.replace(day=1), "is_budget": False
    })

    run_monthly_rollover(conn, today)

    print("\n--- Adding some sample transactions ---")
    process_transaction_request(conn, {
        "type": "simple", "description": "Coffee", "amount": 5,
        "account": "Cash", "budget": "budget_food"
    })
    process_transaction_request(conn, {
        "type": "simple", "description": "Movie Ticket", "amount": 25,
        "account": "Visa Produbanco", "category": "Entertainment"
    })
    process_transaction_request(conn, {
        "type": "simple", "description": "Groceries", "amount": 120,
        "account": "Cash", "budget": "budget_food"
    })

    print("\n--- Displaying transactions in the terminal ---")
    view_transactions(conn)

    export_path = "manual_export.csv"
    print(f"\n--- Exporting transactions to {export_path} ---")
    export_transactions_to_csv(conn, export_path, include_balance=True)

    print("\n--- Manual test complete ---")
    print(f"To run this test, execute: python3 {__file__}")
    print(f"Check the console for the table view and look for the '{export_path}' file.")

    conn.close()

if __name__ == "__main__":
    run_manual_test()
