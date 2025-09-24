# Budget-Specific Logic Implementation Plan

This plan implements the budget tracking feature where the primary budget allocation transaction acts as a running balance for the month, which cannot go below zero.

## 1. Main Controller (`main.py`) - Real-time Budget Updates

The `process_transaction_request` function will be modified to intelligently update the running budget balance as new expenses are recorded.

*   **Logic within `process_transaction_request(conn: Connection, request: dict)`:**
    1.  The function will process the incoming request to create the new expense transaction(s) in memory.
    2.  For each new transaction that is linked to a budget (where the `budget` field is set):
        a. It will fetch the corresponding budget allocation transaction for the current month using `repository.get_budget_allocation_for_month()`.
        b. It will determine the amount of the expense that can be covered by the remaining budget. The calculation is:
           `amount_to_apply = min(abs(new_expense['amount']), abs(current_allocation['amount']))`
        c. It will calculate the new amount for the budget allocation transaction:
           `new_allocation_amount = current_allocation['amount'] + amount_to_apply`
        d. This calculation ensures the allocation's amount moves towards zero but never becomes positive.
        e. It will then call `repository.update_transaction()` to update the budget allocation's `amount` in the database with this new, capped value.
    3.  Finally, it will save the actual expense transaction(s) to the database using `repository.add_transactions()`.

## 2. Main Controller & Scheduler (`main.py`) - Month-End Reconciliation

The month-end process handles the underspend policy based on the final state of the budget allocation.

*   **Logic within `run_monthly_budget_reconciliation(conn: Connection, month_date: date)`:**
    1.  The function will fetch all active subscriptions where `is_budget` is true.
    2.  For each budget, it will:
        a. Retrieve the final state of its allocation transaction for the specified month.
        b. Check the transaction's final `amount`.
            *   If the `amount` is `0`, the budget was either met exactly or overspent. No further action is needed.
            *   If the `amount` is **negative**, the budget was underspent. If the subscription's `underspend_behavior` is `'return'`:
                i.  It will call `transactions.create_budget_release_transaction()` to create a new, positive "Budget Release" transaction. The amount of this transaction will be the absolute value of the allocation's final amount (e.g., `abs(-25.50) -> 25.50`).
                ii. It will save this new "Budget Release" transaction to the database.
                iii. It will then update the original budget allocation transaction's `amount` to `0` to officially close out the month's budget.
