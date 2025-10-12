import sqlite3
from datetime import date
from typing import Dict, Any
from dateutil.relativedelta import relativedelta

import repository
import transactions

def _recalculate_and_update_budget(conn: sqlite3.Connection, budget_id: str, month_date: date):
    """
    Recalculates a budget's live balance for a given month and updates it.
    This is the source of truth for budget adjustments.
    """
    budget_subscription = repository.get_subscription_by_id(conn, budget_id)
    if not budget_subscription:
        return

    total_budget_amount = budget_subscription['monthly_amount']
    
    # Get all expenses for this budget in the given month
    total_spent = repository.get_total_spent_for_budget_in_month(conn, budget_id, month_date)
    
    # The new balance is the initial budget minus what's been spent, capped at 0
    amount_to_apply = min(total_spent, total_budget_amount)
    new_allocation_amount = -total_budget_amount + amount_to_apply

    # Find the allocation transaction and update it
    allocation = repository.get_budget_allocation_for_month(conn, budget_id, month_date)
    if allocation:
        repository.update_transaction_amount(conn, allocation['id'], new_allocation_amount)


def _get_transaction_group_info(conn: sqlite3.Connection, transaction_id: int) -> Dict[str, Any]:
    """
    Analyzes a transaction to determine its group type (simple, split, installment, or subscription)
    and retrieves all sibling transactions.
    """
    transaction = repository.get_transaction_by_id(conn, transaction_id)
    if not transaction:
        raise ValueError(f"Transaction with ID {transaction_id} not found.")

    origin_id = transaction.get("origin_id")

    # Case 1: Simple transaction (no origin_id)
    if not origin_id:
        return {"type": "simple", "origin_id": None, "siblings": [transaction]}

    # Fetch all transactions sharing the same origin_id
    siblings = repository.get_transactions_by_origin_id(conn, origin_id)

    # Case 2: Subscription-linked transaction
    if repository.get_subscription_by_id(conn, origin_id):
        return {"type": "subscription", "origin_id": origin_id, "siblings": siblings}

    # Case 3 & 4: Differentiate between Split and Installment
    # Collect all unique payment dates from the sibling transactions
    payment_dates = {t["date_payed"] for t in siblings}

    if len(payment_dates) == 1:
        return {"type": "split", "origin_id": origin_id, "siblings": siblings}
    else:
        return {"type": "installment", "origin_id": origin_id, "siblings": siblings}


def _apply_expense_to_budget(conn: sqlite3.Connection, transaction: Dict[str, Any]):
    """
    Finds or creates the correct budget allocation for an expense and updates its balance.
    """
    budget_id = transaction.get("budget")
    if not budget_id:
        return

    target_month = transaction["date_payed"]
    allocation = repository.get_budget_allocation_for_month(conn, budget_id, target_month)

    # If no budget exists for that month, create it on the fly
    if not allocation:
        budget_sub = repository.get_subscription_by_id(conn, budget_id)
        if not budget_sub:
            return # Should not happen if data is consistent

        # Create a new, full allocation for the future month
        new_allocation_trans = transactions.create_single_transaction(
            description=budget_sub["name"],
            amount=budget_sub["monthly_amount"],
            category=budget_sub["category"],
            budget=budget_id,
            account=repository.get_account_by_name(conn, budget_sub["payment_account_id"]),
            transaction_date=target_month.replace(day=1)
        )
        # Important: Mark it as a forecast and link to the subscription
        new_allocation_trans["status"] = "forecast"
        new_allocation_trans["origin_id"] = budget_id
        
        repository.add_transactions(conn, [new_allocation_trans])
        # Retrieve the newly created allocation to proceed
        allocation = repository.get_budget_allocation_for_month(conn, budget_id, target_month)

    if allocation:
        # Amount to apply is the smaller of the expense or the remaining budget
        amount_to_apply = min(abs(transaction['amount']), abs(allocation['amount']))
        new_allocation_amount = allocation['amount'] + amount_to_apply
        
        repository.update_transaction_amount(
            conn, allocation['id'], new_allocation_amount
        )


def process_transaction_request(conn: sqlite3.Connection, request: Dict[str, Any], transaction_date: date = None):
    """
    Acts as the main router for incoming transaction requests.
    """
    transaction_type = request.get("type")
    account_name = request.get("account")
    
    account = repository.get_account_by_name(conn, account_name)
    if not account:
        raise ValueError(f"Account '{account_name}' not found.")

    # Use the provided date or default to today
    effective_transaction_date = transaction_date or date.today()
    new_transactions = []

    if transaction_type == "simple":
        new_transactions.append(
            transactions.create_single_transaction(
                description=request["description"],
                amount=request["amount"],
                category=request.get("category"),
                budget=request.get("budget"),
                account=account,
                transaction_date=effective_transaction_date,
                grace_period_months=request.get("grace_period_months", 0),
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
            transaction_date=effective_transaction_date,
            grace_period_months=request.get("grace_period_months", 0),
        )
    elif transaction_type == "split":
        new_transactions = transactions.create_split_transactions(
            description=request["description"],
            splits=request["splits"],
            account=account,
            transaction_date=effective_transaction_date,
        )
    else:
        raise ValueError(f"Invalid transaction type: {transaction_type}")

    if new_transactions:
        # First, save the transactions to the database
        repository.add_transactions(conn, new_transactions)
        print(f"Successfully added {len(new_transactions)} transaction(s).")

        # --- Real-time Budget Update Logic ---
        # Now, apply their effects to the corresponding budgets
        for t in new_transactions:
            _apply_expense_to_budget(conn, t)
        # --- End Budget Logic ---

def process_transaction_update(conn: sqlite3.Connection, transaction_id: int, updates: Dict[str, Any]):
    """
    Modifies a transaction and ensures its linked budget is correctly adjusted.
    """
    original_transaction = repository.get_transaction_by_id(conn, transaction_id)
    if not original_transaction:
        raise ValueError(f"Transaction with ID {transaction_id} not found.")

    # Apply the update first
    repository.update_transaction(conn, transaction_id, updates)
    updated_transaction = repository.get_transaction_by_id(conn, transaction_id)

    # Use a set to avoid recalculating the same budget twice.
    # It stores tuples of (budget_id, month_date)
    budgets_to_recalculate = set()
    
    original_budget = original_transaction.get("budget")
    if original_budget:
        budgets_to_recalculate.add((original_budget, original_transaction["date_payed"]))

    updated_budget = updated_transaction.get("budget")
    if updated_budget:
        # Use the date from the updated transaction in case it also changed
        budgets_to_recalculate.add((updated_budget, updated_transaction["date_payed"]))
    
    for budget_id, month_date in budgets_to_recalculate:
        _recalculate_and_update_budget(conn, budget_id, month_date)


def process_transaction_deletion(conn: sqlite3.Connection, transaction_id: int):
    """
    Deletes a transaction and correctly "returns" its value to any linked budget.
    """
    transaction_to_delete = repository.get_transaction_by_id(conn, transaction_id)
    if not transaction_to_delete:
        return

    budget_id = transaction_to_delete.get("budget")
    transaction_date = transaction_to_delete.get("date_payed")

    # Delete the transaction first
    repository.delete_transaction(conn, transaction_id)

    # If there was a budget, trigger a full recalculation
    if budget_id:
        _recalculate_and_update_budget(conn, budget_id, transaction_date)


def process_transaction_conversion(conn: sqlite3.Connection, transaction_id: int, conversion_details: Dict[str, Any]):
    """
    Orchestrates the conversion of a transaction or group of transactions
    from one type to another using a robust "collect, delete, heal, create" pattern.
    """
    # 1. Identify the full transaction group
    group_info = _get_transaction_group_info(conn, transaction_id)
    
    # 2. Validate the conversion
    if group_info["type"] == "subscription":
        raise ValueError("Cannot convert a subscription-linked transaction.")

    # 3. Collect Context: Find all unique budgets and months that will be affected
    budgets_to_heal = set()
    for sibling in group_info["siblings"]:
        if sibling.get("budget"):
            # Use date_payed as it determines the month the budget is in
            budgets_to_heal.add((sibling["budget"], sibling["date_payed"]))

    # 4. Delete: Remove all old transactions from the database directly
    for sibling in group_info["siblings"]:
        repository.delete_transaction(conn, sibling["id"])

    # 5. Heal: After all deletions, recalculate every affected budget
    for budget_id, month_date in budgets_to_heal:
        _recalculate_and_update_budget(conn, budget_id, month_date)

    # 6. Create: Generate the new transaction(s)
    original_date = group_info["siblings"][0]["date_created"]
    request = {
        "type": conversion_details["target_type"],
        "account": conversion_details["account"],
        **conversion_details
    }
    process_transaction_request(conn, request, transaction_date=original_date)


def process_budget_update(conn: sqlite3.Connection, budget_id: str, new_amount: float, effective_date: date):
    """
    Changes the monthly allocation for a budget from a specific date onward,
    regenerating all future forecasts.
    """
    # First, ensure the budget we are trying to update actually exists.
    budget_subscription = repository.get_subscription_by_id(conn, budget_id)
    if not budget_subscription:
        print(f"Warning: Budget with ID '{budget_id}' not found. No update performed.")
        return

    # Part A: Handle the effective_date month
    # 1. Always update the master subscription record first
    repository.update_subscription(conn, budget_id, {"monthly_amount": new_amount})

    # 2. Check if the effective_date is in a "live" (committed) month
    effective_month_start = effective_date.replace(day=1)
    allocation_for_effective_month = repository.get_budget_allocation_for_month(conn, budget_id, effective_month_start)

    if allocation_for_effective_month and allocation_for_effective_month['status'] == 'committed':
        # It's the current, active month. We need to recalculate the live balance.
        total_spent = repository.get_total_spent_for_budget_in_month(conn, budget_id, effective_month_start)
        
        # New balance is the new budget minus what's already been spent, capped at 0
        new_live_balance = -abs(new_amount) + total_spent
        if new_live_balance > 0:
            new_live_balance = 0
        
        repository.update_transaction_amount(conn, allocation_for_effective_month['id'], new_live_balance)

    # Part B: Wipe and Regenerate the Future
    # 1. Define the starting point for the wipe
    wipe_start_date = effective_month_start

    # 2. Delete all old forecasts from that point onward
    repository.delete_future_forecasts(conn, budget_id, wipe_start_date)

    # 3. Regenerate new forecasts up to the horizon
    horizon_str = repository.get_setting(conn, "forecast_horizon_months")
    horizon_months = int(horizon_str) if horizon_str else 6
    # Use the effective_date to ensure forecasts are generated from the correct point in time
    generate_forecasts(conn, horizon_months, from_date=effective_date)


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
            start_period = (last_forecast_date + relativedelta(months=1)).replace(day=1)
        else:
            # No forecasts exist, start from the subscription's start date or today
            effective_start = max(sub['start_date'], today)
            start_period = effective_start.replace(day=1)

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

        # --- Pre-calculation for Budgets ---
        initial_amounts = {}
        if sub.get("is_budget"):
            # Check each month in the generation window for pre-existing committed expenses
            current_month = start_period
            while current_month <= end_period:
                total_committed = repository.get_total_committed_for_budget_in_month(
                    conn, sub["id"], current_month
                )
                if total_committed > 0:
                    month_key = current_month.strftime("%Y-%m")
                    initial_amount = -sub["monthly_amount"] + total_committed
                    initial_amounts[month_key] = min(0, initial_amount) # Cap at 0
                current_month += relativedelta(months=1)
        # --- End Pre-calculation ---

        new_forecasts = transactions.create_recurrent_transactions(
            subscription=sub,
            account=account,
            start_period=start_period,
            end_period=end_period,
            initial_amounts=initial_amounts,
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


def process_transaction_date_update(conn: sqlite3.Connection, transaction_id: int, new_date: date):
    """
    Handles the complex logic of changing a transaction's date, ensuring
    payment dates and budget allocations are correctly recalculated using a
    "delete and re-create" pattern.
    """
    # 1. Identify the full transaction group
    group_info = _get_transaction_group_info(conn, transaction_id)
    
    # Validate the operation
    if group_info["type"] == "subscription":
        raise ValueError("Cannot change the date of a subscription-linked transaction directly.")

    # 2. Collect Context from the original transaction(s) before deletion
    original_siblings = group_info["siblings"]
    first_sibling = original_siblings[0]
    
    # This context will be used to re-create the transaction
    recreation_context = {
        "account": first_sibling["account"],
        "budget": first_sibling.get("budget"),
        "category": first_sibling.get("category"),
    }

    # Specifics for transaction type
    if group_info["type"] == "simple":
        recreation_context["type"] = "simple"
        recreation_context["description"] = first_sibling["description"]
        recreation_context["amount"] = abs(first_sibling["amount"])
    
    elif group_info["type"] == "installment":
        # For installments, we need to find the total amount and count
        total_amount = sum(abs(t["amount"]) for t in original_siblings)
        installments = len(original_siblings)
        # Description needs to be stripped of the "(1/N)" part
        description = first_sibling["description"].split('(')[0].strip()

        recreation_context["type"] = "installment"
        recreation_context["description"] = description
        recreation_context["total_amount"] = total_amount
        recreation_context["installments"] = installments
    
    elif group_info["type"] == "split":
        # Re-create the splits array
        splits = [
            {
                "amount": abs(t["amount"]),
                "category": t["category"],
                "budget": t.get("budget")
            }
            for t in original_siblings
        ]
        recreation_context["type"] = "split"
        recreation_context["description"] = first_sibling["description"]
        recreation_context["splits"] = splits

    # 3. Heal: Identify affected budgets, delete old transactions, and recalculate
    budgets_to_heal = set()
    for sibling in original_siblings:
        if sibling.get("budget"):
            budgets_to_heal.add((sibling["budget"], sibling["date_payed"]))

    for sibling in original_siblings:
        repository.delete_transaction(conn, sibling["id"])

    for budget_id, month_date in budgets_to_heal:
        _recalculate_and_update_budget(conn, budget_id, month_date)

    # 4. Re-create: Generate the new transaction(s) with the new date
    process_transaction_request(conn, recreation_context, transaction_date=new_date)


if __name__ == '__main__':
    # Example Usage
    from database import create_connection, initialize_database
    from unittest.mock import patch

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