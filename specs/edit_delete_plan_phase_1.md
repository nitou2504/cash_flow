# Phase 1: Foundational Transaction Management Implementation Plan

This document outlines the first phase of implementing functionality to safely edit and delete transactions. This phase focuses on creating the core database functions and handling modifications to single, committed expense transactions.

## 1. Overview

The goal of this phase is to introduce the essential, robust mechanisms for modifying individual financial records while ensuring the integrity of linked "live" budget balances. This provides the foundational tools for the most common use cases.

## 2. Foundational Database Layer Changes (`repository.py`)

Two new general-purpose functions will be added to the persistence layer to serve as the building blocks for the new features.

*   **`update_transaction(conn: Connection, transaction_id: int, updates: dict)`**:
    *   **Purpose:** To generically update one or more fields of a specific transaction.
    *   **Logic:**
        1.  Accepts a dictionary `updates` where keys are column names and values are the new values.
        2.  Dynamically constructs a SQL `UPDATE` statement (e.g., `UPDATE transactions SET description = ?, amount = ? WHERE id = ?`).
        3.  Executes the query to apply the changes.

*   **`delete_transaction(conn: Connection, transaction_id: int)`**:
    *   **Purpose:** To permanently remove a single transaction from the database.
    *   **Logic:** Executes a `DELETE FROM transactions WHERE id = ?` SQL statement.

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
