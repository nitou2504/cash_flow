# Plan: Transaction Conversion and Retroactive Adjustments

This document outlines the detailed implementation plan for enhancing the cash flow tool to support advanced transaction editing, conversion, and retroactive adjustments.

## 1. Overview

The goal is to provide users with the flexibility to correct and modify past transactions. This includes changing a transaction's fundamental type (e.g., from a single payment to an installment plan), adding forgotten transactions to past months, and ensuring all corresponding budget allocations are updated automatically and accurately.

This functionality is critical for real-world use, where data entry errors are common and financial records need to be adjusted after the fact.

## 2. Core Challenge: Ambiguous `origin_id`

A foundational challenge is that the `origin_id` column is used to group several different types of transactions:
*   **Subscriptions:** Recurring payments (e.g., Netflix).
*   **Budgets:** Monthly allocation transactions.
*   **Split Purchases:** A single purchase split into multiple categories.
*   **Installment Plans:** A single purchase paid over multiple months.

A robust solution **must not** confuse these types. Parsing transaction descriptions is unreliable. Therefore, this plan is based on a more reliable method of inference from existing data, requiring **no changes to the database schema**.

## 3. The Identification Strategy: Inferring Group Type

We can reliably determine the type of any transaction group by observing three key pieces of data:

1.  **Is the `origin_id` a Subscription?** We can check if the `origin_id` exists as a primary key in the `subscriptions` table. This is a definitive test.
2.  **Do Siblings Share a Payment Date?** If the `origin_id` is not a subscription, we can examine the `date_payed` for all transactions sharing that ID.
    *   If all transactions have the **same `date_payed`**, it is a **Split Transaction**.
    *   If the transactions have **different `date_payed` values**, it is an **Installment Plan**.

This logic provides a clear and unambiguous way to identify any transaction group.

## 4. Phase 1: Foundational Logic - The Identifier

The first step is to build the tools to reliably identify and retrieve transaction groups.

### 4.1. New Repository Function (`repository.py`)

A new function will be added to the data layer to fetch all parts of a group.

*   **`get_transactions_by_origin_id(conn: Connection, origin_id: str) -> List[Dict[str, Any]]`**:
    *   **Purpose:** To retrieve a list of all transaction records that share a specific `origin_id`.
    *   **Logic:** Executes a simple `SELECT * FROM transactions WHERE origin_id = ?`.

### 4.2. New Central Helper Function (`main.py`)

This will be the cornerstone of the new logic, encapsulating the identification strategy.

*   **`_get_transaction_group_info(conn: Connection, transaction_id: int) -> Dict[str, Any]`**:
    *   **Purpose:** To analyze a single transaction ID and return a definitive report on its type and its sibling transactions.
    *   **Input:** A single `transaction_id`.
    *   **Output:** A dictionary object, e.g., `{ "type": "installment", "origin_id": "...", "siblings": [...] }`.
    *   **Step-by-Step Logic:**
        1.  Fetch the transaction by its `id`. If it has no `origin_id`, immediately return `{ "type": "simple", "siblings": [transaction] }`.
        2.  Use `get_transactions_by_origin_id` to fetch all sibling transactions.
        3.  Check if the `origin_id` exists in the `subscriptions` table. If yes, return `{ "type": "subscription", ... }`.
        4.  If not a subscription, create a `set` of all `date_payed` values from the sibling transactions.
        5.  If the size of the set is 1, return `{ "type": "split", ... }`.
        6.  If the size of the set is greater than 1, return `{ "type": "installment", ... }`.

## 5. Phase 2: The Controller - The Converter

With the identifier in place, we can build the main function to handle the conversion process safely.

### 5.1. New Main Function (`main.py`)

*   **`process_transaction_conversion(conn: Connection, transaction_id: int, conversion_details: Dict[str, Any])`**:
    *   **Purpose:** To orchestrate the conversion of a transaction or group of transactions from one type to another.
    *   **Parameters:**
        *   `transaction_id`: The ID of any transaction in the group to be converted.
        *   `conversion_details`: A dictionary specifying the target type and its required data (e.g., `{ "target_type": "installment", "total_amount": 90.00, "installments": 3, ... }`).
    *   **Core Workflow (The "Delete then Create" Pattern):**
        1.  **Identify:** Call `_get_transaction_group_info(transaction_id)` to get a full report on the source transaction(s).
        2.  **Validate:** Check if the requested conversion is permissible (e.g., throw an error if trying to convert a subscription).
        3.  **Delete:** Loop through every transaction in the `siblings` list from the info object and call the existing `process_transaction_deletion()` on each one. This is the most critical step, as it leverages the existing, robust budget recalculation logic to safely "heal" all affected budgets (past, present, and future).
        4.  **Create:** Based on `conversion_details['target_type']`, call the appropriate creation function (`transactions.create_single_transaction` or `transactions.create_installment_transactions`) to generate the new, correct set of transaction records.
        5.  **Apply:** Add the new transactions to the database and apply their budget impacts using the existing `_apply_expense_to_budget` logic.

### 5.2. Handling Retroactive Additions

The case of adding a forgotten transaction to a past month requires no new logic. The existing `process_transaction_request` function, combined with the `_recalculate_and_update_budget` function, already handles this correctly. A test case will be added to formally verify this behavior.

## 6. Phase 3: Test-Driven Development Plan

A new test file, `tests/test_transaction_conversion.py`, will be created to ensure the implementation is correct and robust. The following tests will be written *before* the implementation code.

1.  **`TestTransactionGroupIdentifier`**:
    *   A dedicated test class to verify that `_get_transaction_group_info` correctly identifies `'simple'`, `'split'`, `'installment'`, and `'subscription'` transactions under various conditions.

2.  **`TestTransactionConversions`**:
    *   **`test_convert_simple_to_installment()`**:
        *   Setup: Create a simple transaction in a past month. Verify the budget.
        *   Action: Convert it to a 3-month installment plan.
        *   Assert: The original month's budget is restored, and the three new months are correctly debited.
    *   **`test_convert_installment_to_simple()`**:
        *   Setup: Create a 3-month installment plan. Verify the three affected budgets.
        *   Action: Convert the plan to a single, simple transaction in the first month.
        *   Assert: The budgets for the 2nd and 3rd months are restored, and the 1st month's budget reflects the full, single payment.
    *   **`test_add_retroactive_transaction_updates_past_budget()`**:
        *   Setup: Create a budget for a past, committed month.
        *   Action: Log a new transaction with a `date_payed` in that past month.
        *   Assert: The past month's budget allocation is correctly recalculated and updated.
    *   **`test_prevent_invalid_conversions()`**:
        *   Assert that calling `process_transaction_conversion` on a subscription-linked transaction raises a `ValueError`.

This detailed plan ensures a safe, robust, and thoroughly tested implementation that builds upon the existing strengths of the application's architecture.
