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
        # --- Real-time Budget Update Logic ---
        for t in new_transactions:
            if t.get("budget"):
                allocation = repository.get_budget_allocation_for_month(
                    conn, t["budget"], t["date_created"]
                )
                if allocation:
                    amount_to_apply = abs(t['amount'])
                    new_allocation_amount = allocation['amount'] + amount_to_apply
                    
                    repository.update_transaction_amount(
                        conn, allocation['id'], new_allocation_amount
                    )
        # --- End Budget Logic ---
        
        repository.add_transactions(conn, new_transactions)
        print(f"Successfully added {len(new_transactions)} transaction(s).")

def process_transaction_update(conn: sqlite3.Connection, transaction_id: int, updates: Dict[str, Any]):
    """
    Modifies a transaction and ensures its linked budget is correctly adjusted.
    """
    original_transaction = repository.get_transaction_by_id(conn, transaction_id)
    if not original_transaction:
        raise ValueError(f"Transaction with ID {transaction_id} not found.")

    budget_id = original_transaction.get("budget")
    
    if budget_id:
        old_amount = original_transaction.get("amount", 0.0)
        new_amount = updates.get("amount", old_amount)

        if old_amount != new_amount:
            # The adjustment is the difference in impact between the new and old amounts.
            adjustment = abs(new_amount) - abs(old_amount)
            
            allocation = repository.get_budget_allocation_for_month(
                conn, budget_id, original_transaction["date_created"]
            )
            
            if allocation:
                # Apply the adjustment to the allocation's current value
                new_allocation_amount = allocation['amount'] + adjustment
                repository.update_transaction_amount(
                    conn, allocation['id'], new_allocation_amount
                )

    repository.update_transaction(conn, transaction_id, updates)

def process_transaction_deletion(conn: sqlite3.Connection, transaction_id: int):
    """
    Deletes a transaction and correctly "returns" its value to any linked budget.
    """
    transaction_to_delete = repository.get_transaction_by_id(conn, transaction_id)
    if not transaction_to_delete:
        return

    budget_id = transaction_to_delete.get("budget")

    if budget_id:
        transaction_amount = transaction_to_delete.get("amount", 0.0)
        
        allocation = repository.get_budget_allocation_for_month(
            conn, budget_id, transaction_to_delete["date_created"]
        )
        
        if allocation:
            # "Return" the money by subtracting the absolute value (impact) of the expense
            new_allocation_amount = allocation['amount'] - abs(transaction_amount)
            repository.update_transaction_amount(
                conn, allocation['id'], new_allocation_amount
            )

    repository.delete_transaction(conn, transaction_id)


def generate_forecasts(conn: sqlite3.Connection, horizon_months: int, from_date: date = None):
    """
    A scheduler job that creates and maintains forecast transactions up to a
    defined horizon.
    """
    today = from_date or date.today()
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

def run_monthly_budget_reconciliation(conn: sqlite3.Connection, month_date: date):
    """
    Handles the month-end underspend policy for all active budgets.
    """
    active_budgets = [
        s for s in repository.get_all_active_subscriptions(conn, month_date)
        if s.get("is_budget")
    ]

    for budget_sub in active_budgets:
        allocation = repository.get_budget_allocation_for_month(
            conn, budget_sub["id"], month_date
        )
        
        if allocation and allocation["amount"] < 0: # Underspent
            if budget_sub["underspend_behavior"] == "return":
                account = repository.get_account_by_name(conn, budget_sub["payment_account_id"])
                
                release_trans = transactions.create_budget_release_transaction(
                    budget_id=budget_sub["id"],
                    budget_name=budget_sub["name"],
                    release_amount=abs(allocation["amount"]),
                    account=account,
                    month_date=month_date,
                )
                repository.add_transactions(conn, [release_trans])
                repository.update_transaction_amount(conn, allocation["id"], 0)
                print(f"Released {release_trans['amount']:.2f} from '{budget_sub['name']}'.")


def run_monthly_rollover(conn: sqlite3.Connection, process_date: date):
    """
    The main, on-demand entry point for all monthly processing.
    It commits the current month's forecasts and tops up the forecast horizon.
    """
    print(f"\n--- Running Monthly Rollover for {process_date.strftime('%Y-%m')} ---")
    
    # 1. Commit forecasts for the given month
    repository.commit_forecasts_for_month(conn, process_date)
    print("Committed forecasts for the current month.")

    # 2. Retrieve forecast horizon setting
    horizon_str = repository.get_setting(conn, "forecast_horizon_months")
    horizon_months = int(horizon_str) if horizon_str else 6 # Default to 6
    
    # 3. Generate new forecasts to top up the horizon
    generate_forecasts(conn, horizon_months, process_date)
    print("Forecast generation complete.")


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
    generate_forecasts(conn, horizon_months=6, from_date=date.today())

    # --- Budget Logic Examples ---
    print("\n--- Setting up Budgets for Demonstration ---")
    today = date.today()
    current_month_start = today.replace(day=1)

    # 1. Food Budget (Underspend with 'return')
    food_budget = {
        "id": "budget_food", "name": "Food Budget", "category": "Food",
        "monthly_amount": 400, "payment_account_id": "Cash",
        "start_date": current_month_start, "is_budget": True, "underspend_behavior": "return"
    }
    repository.add_subscription(conn, food_budget)
    repository.add_transactions(conn, [{
        "date_created": current_month_start, "date_payed": current_month_start,
        "description": "Food Budget", "account": "Cash", "amount": -400,
        "category": "Food", "budget": "budget_food", "status": "committed", "origin_id": "budget_food"
    }])

    # 2. Transport Budget (Overspend example)
    transport_budget = {
        "id": "budget_transport", "name": "Transport Budget", "category": "Transport",
        "monthly_amount": 100, "payment_account_id": "Cash",
        "start_date": current_month_start, "is_budget": True, "underspend_behavior": "keep"
    }
    repository.add_subscription(conn, transport_budget)
    repository.add_transactions(conn, [{
        "date_created": current_month_start, "date_payed": current_month_start,
        "description": "Transport Budget", "account": "Cash", "amount": -100,
        "category": "Transport", "budget": "budget_transport", "status": "committed", "origin_id": "budget_transport"
    }])

    # 3. Shopping Budget (Underspend with 'keep')
    shopping_budget = {
        "id": "budget_shopping", "name": "Shopping Budget", "category": "Shopping",
        "monthly_amount": 250, "payment_account_id": "Visa Produbanco",
        "start_date": current_month_start, "is_budget": True, "underspend_behavior": "keep"
    }
    repository.add_subscription(conn, shopping_budget)
    repository.add_transactions(conn, [{
        "date_created": current_month_start, "date_payed": current_month_start,
        "description": "Shopping Budget", "account": "Visa Produbanco", "amount": -250,
        "category": "Shopping", "budget": "budget_shopping", "status": "committed", "origin_id": "budget_shopping"
    }])

    print("\n--- Logging Expenses Against Budgets ---")
    # Scenario 1: Underspend the Food budget ($350 spent out of $400)
    process_transaction_request(conn, {"type": "simple", "description": "Groceries Week 1", "amount": 150, "account": "Cash", "budget": "budget_food"})
    process_transaction_request(conn, {"type": "simple", "description": "Groceries Week 2", "amount": 200, "account": "Cash", "budget": "budget_food"})

    # Scenario 2: Overspend the Transport budget ($120 spent out of $100)
    process_transaction_request(conn, {"type": "simple", "description": "Gasoline", "amount": 120, "account": "Cash", "budget": "budget_transport"})

    # Scenario 3: Underspend the Shopping budget ($180 spent out of $250)
    process_transaction_request(conn, {"type": "simple", "description": "New Shoes", "amount": 180, "account": "Visa Produbanco", "budget": "budget_shopping"})

    print("\n--- Running Month-End Budget Reconciliation ---")
    run_monthly_budget_reconciliation(conn, current_month_start)

    # --- Run Monthly Rollover to commit forecasts and generate new ones ---
    run_monthly_rollover(conn, today)


    # --- Verify by fetching all transactions ---
    all_trans = repository.get_all_transactions(conn)
    print("\n--- All Transactions in Database ---")
    for t in all_trans:
        print(dict(t))
    
    conn.close()
