# Implementation Plan: Transaction Date Change

## 1. Overview

This document outlines the plan to implement a feature allowing users to change the date of a transaction while ensuring that all cascading effects—specifically credit card payment dates and monthly budget allocations—are updated correctly and reliably.

The primary use case is to handle the natural fluctuation of credit card cut-off dates, where a transaction made on a certain day might fall into a different billing cycle than initially expected.

## 2. Guiding Principle: Atomic "Delete and Re-create"

To guarantee data integrity and prevent complex, error-prone state management, the core of this implementation will follow a **"delete and re-create"** pattern. This approach is already used successfully in the `process_transaction_conversion` function and provides several advantages:

*   **Atomicity:** The entire operation succeeds or fails as a single unit, preventing partial updates.
*   **Reliability:** It leverages the existing, tested logic for transaction creation and budget healing (`_recalculate_and_update_budget`), which is the source of truth for budget balances.
*   **Simplicity:** It avoids writing complex logic to manually "move" funds between budgets and recalculate payment dates on the fly.

## 3. Implementation Steps

### Step 1: Prerequisite - Fix Budget Recalculation Trigger

Before implementing the new feature, a minor bug in the existing `process_transaction_update` function will be corrected.

*   **Current Behavior:** The function uses `date_created` to identify which monthly budget to recalculate.
*   **Problem:** A transaction's budget allocation is determined by its `date_payed`. If a simple update changes the payment date to a new month, the old logic would recalculate the wrong budget period.
*   **Correction:** The function will be modified to use `date_payed` from both the original and updated transaction to correctly identify all affected budget periods.

### Step 2: Create a Dedicated Orchestrator Function

A new function, `process_transaction_date_update(conn, transaction_id, new_date)`, will be created in `main.py`. This function will serve as the sole entry point for this feature.

### Step 3: Implement the Core "Delete and Re-create" Logic

The new orchestrator function will execute the following sequence:

1.  **Identify Full Transaction Group:** It will use the existing `_get_transaction_group_info` helper to determine if the transaction is simple, split, or part of an installment plan, and to retrieve all sibling transactions. This is crucial for handling installment purchases where changing one date affects all future payments.

2.  **Collect Context:** It will gather all necessary data from the original transaction(s) before deletion (e.g., description, total amount, number of installments, category, budget links, account details).

3.  **Heal Original Budgets:**
    *   Identify all unique monthly budgets affected by the original transactions.
    *   Delete all original transactions from the database.
    *   Trigger a full recalculation for each affected budget using `_recalculate_and_update_budget`. This will "return" the spent amount to the original budget envelopes, restoring them to their correct state.

4.  **Re-create New Transactions:**
    *   Using the collected context and the `new_date`, it will generate a new set of transactions.
    *   The core transaction creation functions (`create_single_transaction`, `create_installment_transactions`) will automatically calculate the new, correct `date_payed` for each transaction based on the new creation date and the account's rules.

5.  **Apply to New Budgets:**
    *   The newly created transactions will be saved to the database.
    *   The system will then automatically apply these expenses to the correct new monthly budgets using the existing `_apply_expense_to_budget` logic.

## 4. Testing Strategy

A new test file, `tests/test_transaction_date_change.py`, will be created to validate the implementation. The test suite will use an in-memory database and cover the following critical scenarios:

1.  **Simple Transaction - Forward:** A simple transaction's date is changed, causing its `date_payed` to move into the next month. The test will verify that the original month's budget is restored and the new month's budget is correctly debited.

2.  **Simple Transaction - Backward:** A simple transaction's date is changed, moving its `date_payed` to the previous month.

3.  **Installment Transaction - Forward:** The date of an installment purchase is changed, causing all of its payment dates to shift forward into new billing cycles. The test will verify all affected budgets across multiple months are updated correctly.

4.  **Installment Transaction - Backward:** The date of an installment purchase is moved earlier, causing all payments to shift to previous billing cycles.
