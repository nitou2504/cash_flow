# Implementation Plan: Pending Transactions

## 1. Overview

This document outlines the plan to implement a "pending" status for transactions. This feature will allow users to log expected or unconfirmed financial events (both income and expenses) without them affecting the official running balance or any budget allocations until they are explicitly "cleared."

This is useful for tracking anticipated payments, reimbursements, or purchases that are not yet finalized.

## 2. Core Requirements

1.  **Creation:** Users must be able to create any type of transaction (simple, installment, split) with a new `pending` status.
2.  **Balance Calculation:** Transactions with a `pending` status must be excluded from the running balance calculation. They will be visible in the transaction list but will not impact the cash flow total.
3.  **Budget Calculation:** Pending expenses must not be applied to any budget's live balance. They should not reduce the available funds in a budget's "digital envelope."
4.  **Clearing Mechanism:** A new command must be introduced to change a transaction's status from `pending` to `committed`.
5.  **Visual Distinction:** In the CLI's `view` command, pending transactions and their corresponding running balance should be visually distinct (e.g., colorized or dimmed) to be easily identifiable.

## 3. Implementation Details by File

### `database.py`

*   **No Change Required.** The `status` column in the `transactions` table is of type `TEXT` and can already accommodate the new `"pending"` value without any schema modification.

### `transactions.py`

*   **`_create_base_transaction`:**
    *   This internal factory function will be modified to accept a new boolean parameter: `is_pending: bool = False`.
    *   The logic will be updated to set the transaction's status based on this flag: `status = "pending" if is_pending else "committed"`.

*   **`create_single_transaction`, `create_installment_transactions`, `create_split_transactions`:**
    *   Each of these public-facing functions will be updated to accept the new `is_pending: bool = False` argument.
    *   This argument will be passed down to `_create_base_transaction` to ensure that any type of transaction can be created with the pending status.

### `repository.py`

*   **`get_transactions_with_running_balance`:**
    *   This is a critical change. The loop that calculates the running balance will be modified.
    *   An `if` condition will be added: `if transaction_dict["status"] != "pending":`.
    *   The line `running_balance += transaction_dict["amount"]` will only be executed if the condition is true. This ensures pending transactions do not affect the balance.

### `main.py`

*   **`_apply_expense_to_budget`:**
    *   A guard clause will be added at the beginning of the function to prevent pending transactions from affecting budgets.
    *   The new line will be: `if transaction.get('status') == 'pending': return`.

*   **`process_transaction_clearance` (New Function):**
    *   A new function will be created to handle the logic for clearing a pending transaction.
    *   **Steps:**
        1.  Fetch the transaction by its `transaction_id`.
        2.  Verify its status is `"pending"`. If not, raise an error or return.
        3.  Update the transaction's status to `"committed"` in the database.
        4.  Check if the transaction is linked to a budget (`budget_id` is not null).
        5.  If it is, call the robust recalculation function: `_recalculate_and_update_budget(conn, budget_id, transaction_date)`. This ensures the budget's state is recalculated from scratch, maintaining data integrity.

### `llm_parser.py`

*   **`parse_transaction_string`:**
    *   The system prompt will be updated to teach the LLM about the new capability.
    *   **New Rule:** A rule will be added: "If the user mentions 'pending', 'unconfirmed', 'not yet paid', 'waiting for', or similar terms, you MUST set `"is_pending": true`."
    *   **Schema Update:** The transaction schema within the prompt will be updated to include `"is_pending": (boolean, optional)`.
    *   **New Example:** An example will be added, such as: `User: "My friend owes me $25 for dinner, mark it as pending"` -> `{"request_type": "transaction", "type": "simple", "description": "Friend owes for dinner", "amount": 25, "account": "Cash", "is_income": true, "is_pending": true}`.

### `cli.py`

*   **New `clear` command:**
    *   A new subcommand will be added to the `ArgumentParser`: `clear`.
    *   It will take one argument: `transaction_id`.
    *   A new handler function, `handle_clear(conn, args)`, will be created. This function will call `main.process_transaction_clearance(conn, args.transaction_id)`.

### `interface.py`

*   **`view_transactions`:**
    *   The loop that builds the `rich` table will be modified.
    *   Inside the loop, a check will be performed: `if t['status'] == 'pending':`.
    *   If a transaction is pending, a specific style will be applied to the amount and running balance for that row to make it visually distinct. For example, the color could be set to grey to indicate it's not "active."
    *   **Example Logic:**
        ```python
        row_style = "dim" if t['status'] == 'pending' else ""
        amount_style = "grey50" if t['status'] == 'pending' else "yellow"
        balance_style = "grey50" if t['status'] == 'pending' else "green"

        table.add_row(
            ...,
            f"[{amount_style}]{t['amount']:.2f}[/]",
            ...,
            f"[{balance_style}]{t['running_balance']:.2f}[/]",
            style=row_style
        )
        ```

## 4. Summary of User Flow

1.  **Creation:** A user can add a transaction via the CLI using natural language, e.g., `cashflow add "pending purchase of a new monitor for 300 on Visa"`.
2.  **Viewing:** The user runs `cashflow view`. The new monitor purchase appears in the list, but its row is dimmed or greyed out. The running balance for that row and all subsequent rows is calculated as if the pending transaction does not exist.
3.  **Clearing:** Once the purchase is finalized, the user finds its ID from the view (e.g., ID `42`) and runs `cashflow clear 42`.
4.  **Result:** The system updates the transaction's status to `committed`. When `cashflow view` is run again, the transaction for the monitor will appear in the normal style, and the running balance will be correctly updated to reflect the -300 charge. If it were linked to a budget, that budget's balance would also be updated.
