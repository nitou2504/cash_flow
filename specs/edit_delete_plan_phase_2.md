# Phase 2: Advanced Budget & Forecast Management Implementation Plan

This document outlines the second phase of implementing functionality to modify financial records. This phase builds upon the foundational functions from Phase 1 to handle the complex scenario of updating a budget's core monthly amount and regenerating all future forecasts.

## 1. Overview

The goal of this phase is to implement the logic for safely changing a budget's allocation from a specific date onward. This involves updating the current month's live balance, wiping all old future forecasts, and regenerating a new, correct set of forecasts based on the updated amount.

## 2. Foundational Database Layer Changes (`repository.py`)

One new function will be added to the persistence layer to handle modifications to the master subscription/budget records.

*   **`update_subscription(conn: Connection, subscription_id: str, updates: dict)`**:
    *   **Purpose:** To generically update one or more fields of a subscription, primarily for changing a budget's `monthly_amount`.
    *   **Logic:** Similar to `update_transaction`, it dynamically constructs and executes a SQL `UPDATE` statement for the `subscriptions` table.

## 3. Controller Layer Logic (`main.py`)

A new high-level function will be created to orchestrate the complex process of updating a budget's future allocations.

### 3.1. Use Case: Updating a Budget's Amount

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
