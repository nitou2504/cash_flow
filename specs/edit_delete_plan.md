# Transaction and Budget Editing/Deletion Implementation Plan

This document outlines the detailed strategy for implementing functionality to safely edit and delete transactions and to update budget allocations.

## 1. Overview

The goal is to introduce robust mechanisms for modifying financial records while ensuring the integrity of the entire system, especially the "live" budget balances and future forecasts. The core principle is to differentiate between modifying past, committed records and altering future, forecasted plans.

## 2. Foundational Database Layer Changes (`repository.py`)

Three new general-purpose functions will be added to the persistence layer to serve as the building blocks for the new features.

*   **`update_transaction(conn: Connection, transaction_id: int, updates: dict)`**:
    *   **Purpose:** To generically update one or more fields of a specific transaction.
    *   **Logic:**
        1.  Accepts a dictionary `updates` where keys are column names and values are the new values.
        2.  Dynamically constructs a SQL `UPDATE` statement (e.g., `UPDATE transactions SET description = ?, amount = ? WHERE id = ?`).
        3.  Executes the query to apply the changes.

*   **`delete_transaction(conn: Connection, transaction_id: int)`**:
    *   **Purpose:** To permanently remove a single transaction from the database.
    *   **Logic:** Executes a `DELETE FROM transactions WHERE id = ?` SQL statement.

*   **`update_subscription(conn: Connection, subscription_id: str, updates: dict)`**:
    *   **Purpose:** To generically update one or more fields of a subscription, primarily for changing a budget's `monthly_amount`.
    *   **Logic:** Similar to `update_transaction`, it dynamically constructs and executes a SQL `UPDATE` statement for the `subscriptions` table.

## 3. Controller Layer Logic (`main.py`)

New high-level functions will be created in the main controller to orchestrate the update and deletion processes, ensuring all related data (like budget balances) is handled correctly.

### 3.1. Use Case: Editing a Simple Transaction

This covers correcting a mistake in a single, committed transaction.

*   **New Function: `process_transaction_update(conn: Connection, transaction_id: int, updates: dict)`**:
    *   **Purpose:** To modify a transaction and ensure its linked budget is correctly adjusted.
    *   **Logic:**
        1.  **Fetch Original State:** Before any changes, retrieve the original transaction using its `transaction_id` to get its `old_amount` and `budget_id`.
        2.  **Check for Budget Link:** If `budget_id` is `None`, simply call `repository.update_transaction` and finish.
        3.  **Calculate Adjustment:** If a budget is linked, calculate the required adjustment to the budget's running balance. The formula is: `adjustment = old_amount - new_amount`.
            *   *Example:* Changing an expense from -50 (`old_amount`) to -60 (`new_amount`) yields `adjustment = (-50) - (-60) = +10`.
        4.  **Apply Adjustment to Budget:**
            a.  Fetch the budget allocation transaction for the corresponding month using `repository.get_budget_allocation_for_month`.
            b.  Calculate the new allocation amount: `new_allocation_amount = allocation['amount'] + adjustment`.
            c.  Update the allocation using `repository.update_transaction_amount`.
        5.  **Update the Transaction:** Finally, call `repository.update_transaction` to apply the `updates` to the expense transaction itself.

### 3.2. Use Case: Deleting a Simple Transaction

This covers removing a single, committed transaction.

*   **New Function: `process_transaction_deletion(conn: Connection, transaction_id: int)`**:
    *   **Purpose:** To delete a transaction and correctly "return" its value to any linked budget.
    *   **Logic:**
        1.  **Fetch Original State:** Retrieve the transaction to get its `amount` and `budget_id`.
        2.  **Check for Budget Link:** If `budget_id` is `None`, simply call `repository.delete_transaction` and finish.
        3.  **Reverse Budget Impact:**
            a.  Fetch the budget allocation transaction.
            b.  Calculate the new allocation amount by adding back the absolute value of the expense: `new_allocation_amount = allocation['amount'] + abs(transaction_amount)`.
            c.  Update the allocation using `repository.update_transaction_amount`.
        4.  **Delete the Transaction:** Call `repository.delete_transaction` to remove the expense.

### 3.3. Use Case: Updating a Budget's Amount

This is the most complex scenario, designed to handle changes to future plans safely.

*   **New Function: `process_budget_update(conn: Connection, budget_id: str, new_amount: float, effective_date: date)`**:
    *   **Purpose:** To change the monthly allocation for a budget from a specific date onward, correctly handling the current month and regenerating all future forecasts.
    *   **Logic:** The process is divided into two main parts.

    **Part A: Handle the `effective_date` Month**

    1.  **Update the Subscription Definition:** The first step is always to update the master record in the `subscriptions` table with the new `monthly_amount`. This ensures all future logic uses the correct base value.
        ```python
        repository.update_subscription(conn, budget_id, {"monthly_amount": new_amount})
        ```
    2.  **Check if `effective_date` is the Current Month:** Determine if the budget allocation for the `effective_date`'s month is already `'committed'`.
        *   **If NO (it's a future month):** The logic is simple. Proceed directly to Part B.
        *   **If YES (it's the current, active month):**
            a.  **Calculate Total Spend:** Find all expense transactions for the current month linked to this `budget_id` and sum their amounts to get `total_spend`.
            b.  **Calculate New Live Balance:** The new amount for the committed allocation transaction is calculated by applying the total spend to the new base budget amount. The formula is: `new_live_balance = (-abs(new_amount)) + abs(total_spend)`.
                *   *Example:* New budget is 500. Total spend is -150. `new_live_balance` is `-500 + 150 = -350`.
            c.  **Update Current Allocation:** Use `repository.update_transaction_amount` to set the current month's committed budget allocation to this `new_live_balance`.

    **Part B: Wipe and Regenerate the Future**

    This part runs after Part A is complete.

    1.  **Define the "Future":** The future is defined as any month *after* the `effective_date`'s month.
    2.  **Delete Future Forecasts:** Call `repository.delete_future_forecasts`, passing the `budget_id` and a `from_date` corresponding to the first day of the month *after* the `effective_date`. This clears the slate of all old, incorrect forecasts.
    3.  **Regenerate Forecasts:** Call the existing `generate_forecasts` function. It will use the updated `monthly_amount` from the subscription table and automatically create a new, correct set of `'forecast'` transactions up to the defined horizon.
