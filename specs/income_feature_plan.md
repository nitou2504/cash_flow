# Plan: Implementing Income Transactions

This document outlines the detailed plan to refactor the system to support income transactions, both for one-off entries and recurring subscriptions like a salary.

## 1. Overview

The system was initially designed exclusively for expense tracking. This is reflected in the core transaction creation logic, which automatically converts all incoming amounts to negative values. This makes it impossible to log income.

This plan details the necessary changes to the database, transaction logic, and main controller to properly handle positive amounts for income while ensuring that existing expense and budget functionalities remain robust and unaffected.

## 2. Guiding Principles

-   **Safety First:** The highest priority is to ensure these changes do not introduce regressions, especially in the critical budget-tracking logic.
-   **Explicitness over Implicitness:** We will use a clear `is_income` flag rather than relying on the sign of an amount provided by a user or another system. This prevents ambiguity.
-   **Test-Driven Development:** The implementation will follow a strict TDD approach. A failing test will be created first to prove the existence of the bug, and the test will be used to validate the final solution.

## 3. Implementation Steps

### Step 1: Create a Failing Test

A new test file, `tests/test_income.py`, will be created to formally define the expected behavior and confirm the current bug.

-   **Test Case:** `test_income_subscription_creates_positive_transactions`
-   **Setup:**
    -   Create an in-memory database.
    -   Define a new subscription for a "Monthly Salary" with a `monthly_amount` of `3000`.
    -   This subscription dictionary will include a new key: `"is_income": True`.
-   **Action:**
    -   Call the `generate_forecasts` function.
-   **Assertion:**
    -   Retrieve the newly created forecast transactions.
    -   Assert that the `amount` of each transaction is `> 0`.
-   **Outcome:** This test will fail with the current codebase because all transaction amounts are forced to be negative.

### Step 2: Update the Database Schema

The `subscriptions` table needs to be able to differentiate between income and expenses.

-   **File:** `database.py`
-   **Action:** Modify the `CREATE TABLE IF NOT EXISTS subscriptions` statement.
-   **Change:** Add a new column: `is_income BOOLEAN NOT NULL DEFAULT 0`.
-   **File:** `repository.py`
-   **Action:** Update the `add_subscription` function to accept and insert the new `is_income` field.

### Step 3: Refactor Core Transaction Logic

This is the most critical part of the implementation, where the sign enforcement is corrected.

-   **File:** `transactions.py`
-   **Function:** `_create_base_transaction`
    -   **Change:** Modify the `amount` assignment from ` "amount": -abs(amount)` to `"amount": amount`. This makes the function sign-neutral; it will now trust the sign of the amount it is given.
-   **Function:** `create_single_transaction`
    -   **Change:** This function will now be responsible for enforcing the correct sign.
    -   Add a new boolean parameter: `is_income: bool = False`.
    -   Calculate the final amount: `final_amount = abs(amount) if is_income else -abs(amount)`.
    -   Pass this `final_amount` to `_create_base_transaction`.
-   **Function:** `create_recurrent_transactions`
    -   **Change:** This function will read the new `is_income` flag from the subscription object.
    -   It will then call `create_single_transaction`, passing the value of `subscription.get("is_income", False)` to the `is_income` parameter. This ensures salary forecasts are positive and Netflix forecasts are negative.
-   **Review:** `create_installment_transactions` and `create_split_transactions`.
    -   **Action:** No changes are required, as they correctly call `create_single_transaction` with the default `is_income=False`, preserving their expense-only nature.

### Step 4: Update the Main Controller

The main application logic needs to be aware of the new income type to handle it safely.

-   **File:** `main.py`
-   **Function:** `process_transaction_request`
    -   **Change:** For the `"simple"` transaction type, the function will now look for an `is_income` flag in the incoming request dictionary.
    -   This flag will be passed down to `transactions.create_single_transaction`.
-   **Function:** `_apply_expense_to_budget`
    -   **Change:** This is a critical safety measure. The entire logic of the function will be wrapped in a conditional check: `if transaction['amount'] < 0:`.
    -   **Reasoning:** This ensures that only expenses (negative amounts) can ever be deducted from a budget's balance. It prevents a positive income transaction from being accidentally "applied" to a budget, which would incorrectly increase the budget's remaining allocation.

### Step 5: Verification and Regression Testing

-   **Run New Test:** Execute `python3 -m tests.test_income` and confirm that it now passes.
-   **Run Full Test Suite:** Execute all tests in the `tests/` directory to ensure that these fundamental changes have not broken any existing functionality. This is the most important step for guaranteeing system stability.

### Step 6: Update the Manual Test Script

To provide a clear, runnable example of the new functionality for manual testing.

-   **File:** `manual_test.py`
-   **Change 1:** At the beginning of the `run_manual_test` function, add logic to check for and delete the `manual_test.db` file if it exists. This ensures a clean slate for every run.
-   **Change 2:** Add a new income subscription (e.g., "Monthly Salary") with `is_income: True`.
-   **Change 3:** Add an example of a simple income transaction using `process_transaction_request`, including `"is_income": True` in the request dictionary.
-   **Outcome:** When run, the script will now correctly display positive income in both the terminal view and the CSV export.
